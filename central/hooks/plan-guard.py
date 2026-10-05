#!/usr/bin/env python3
"""PreToolUse hook on ExitPlanMode (the plan's Approve step): send a plan back before I see it when it
- contains colour code (HTML such as <span style=…>), which the plan window shows as raw text;
- has a "Rev N" label without its colour square in front (🟦 Rev 1 · 🟩 Rev 2 · 🟧 Rev 3 · 🟪 Rev 4, then repeat);
- does not open with a framed Summary (a one-column table headed "Summary") in everyday words;
- has Rev labels but no "Changes in this version" diff block listing every changed line;
- has no "Stages to finish" list with an owner (Claude or You) on each stage, and a count line ("14 stages: …").
When the plan passes and the session plans on Fable, the user is reminded (systemMessage) that switching back to
Opus after approval costs less.
The plan text is taken from the tool input, or from a plan file the input names, or from the newest plan file."""
import glob, os, re, time
import json
from _common import read_hook_input, deny_tool, log, read_transcript, PROJECT_DIR, PLAN_TEMPLATE, load_config
cfg_ = load_config()

data = read_hook_input()
inp = data.get("tool_input") or {}

# v3.1.28: a big or risky plan (the plan gate's strong signals) is checked by the reviewer before I see it
try:
    from _common import STATE_DIR, prompt_number, last_turn
    _st = json.load(open(os.path.join(STATE_DIR, "plan-review.json"), encoding="utf-8"))
    _sid = str(data.get("session_id") or "")
    if _st.get("session") == _sid and _st.get("n") == prompt_number(_sid):
        _turn = last_turn(read_transcript(data.get("transcript_path")))
        _reviewed = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                        and str((b.get("input") or {}).get("subagent_type") or "") == "reviewer"
                        for r in _turn if r.get("type") == "assistant"
                        for b in (((r.get("message") or {}).get("content")) or [])
                        if isinstance(((r.get("message") or {}).get("content")), list))
        if not _reviewed:
            deny_tool("This is a big or risky plan (" + str(_st.get("why") or "strong signals") + "). Before I see "
                      "it, send the reviewer (subagent 'reviewer', moment: Before a plan) with the draft plan and the "
                      "area's ledger and hotspot rows; fix what it finds, then present the plan again.")
except (OSError, ValueError, ImportError):
    pass


def plan_text():
    for v in inp.values():
        if isinstance(v, str) and len(v) > 200:
            return v
    for v in inp.values():
        if isinstance(v, str) and v.endswith(".md") and os.path.isfile(v):
            return open(v, encoding="utf-8", errors="replace").read()
    home = os.path.expanduser("~")
    # v3.1.24: the stub's plansDirectory writes plan files into the repository's plans/ (since v3.1.23)
    files = sorted(glob.glob(os.path.join(PROJECT_DIR, "plans", "*.md")) +
                   glob.glob(os.path.join(home, ".claude", "plans", "*.md")), key=os.path.getmtime, reverse=True)
    if files and time.time() - os.path.getmtime(files[0]) < 1800:
        return open(files[0], encoding="utf-8", errors="replace").read()
    return ""


text = plan_text()
if not text:
    log("plan-guard", {"skipped": "no plan text found", "input_keys": sorted(inp)})
    raise SystemExit(0)

SQUARES = {1: "🟦", 2: "🟩", 3: "🟧", 0: "🟪"}
problems = []
if re.search(r"<\s*(span|font|div|mark|b|i|u|p)\b[^>]*>|style\s*=\s*[\"']", text, re.I):
    problems.append("It contains colour code (HTML such as <span style=…>); the plan window shows that as raw text. "
                    "Remove all HTML.")
bad = []
# v3.1.26: squares are needed on Rev labels (a line, bullet, bold label or diff line that starts with "Rev N"), not
# on every mention of "Rev 2" inside a sentence — that strictness made sessions run scripts to patch plans
for m in re.finditer(r"(?m)^[ \t]*(?:[-*•+]|\d+[.)]|\|)?[ \t]*(?:\*\*|__)?[ \t]*([^\sA-Za-z0-9*_<]{0,2})?[ \t]*"
                     r"(?:\*\*|__)?[ \t]*(?:<[^>]+>)?[ \t]*Rev\s*(\d+)\b", text):
    n = int(m.group(2))
    if SQUARES[n % 4] not in (m.group(1) or ""):
        bad.append(f"Rev {n}")
# v3.1.27: coverage — every agreed design decision in the working record must appear in the plan
try:
    _rec = open(os.path.join(PROJECT_DIR, "WORKING_RECORD.md"), encoding="utf-8", errors="replace").read()
except OSError:
    _rec = ""
_sec = re.search(r"(?ms)^##\s*Design decisions\b.*?(?=^##\s|\Z)", _rec)
if _sec:
    _norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    _plan_n = _norm(text)
    _missing = []
    for _line in _sec.group(0).splitlines():
        _m = re.match(r"^\s*[-*]\s*\[agreed\]\s*(.+?)\s*(?:—|-{1,2})\s*search:\s*(.+?)\s*$", _line, re.I)
        if _m and _norm(_m.group(2).strip("`\"'")) not in _plan_n:
            _missing.append(_m.group(1)[:60] + " (search: " + _m.group(2).strip("`\"'") + ")")
    if _missing:
        problems.append("These agreed design decisions are missing from the plan — add each one (its search phrase must "
                        "appear), or mark it open in the record if it is not agreed after all: " + "; ".join(_missing[:8])
                        + (f" (+{len(_missing) - 8} more)" if len(_missing) > 8 else "") + ".")
# v3.1.27: the Rev number is the plan version (Plan v9 marks its changes Rev 9; earlier changes are unmarked)
_ver = re.search(r"\bPlan v(\d+)\b", text)
if _ver:
    _labels = {int(m.group(2)) for m in re.finditer(
        r"(?m)^[ \t]*(?:[-*•+]|\d+[.)]|\|)?[ \t]*(?:\*\*|__)?[ \t]*([^\sA-Za-z0-9*_<]{0,2})?[ \t]*(?:\*\*|__)?[ \t]*"
        r"(?:<[^>]+>)?[ \t]*Rev\s*(\d+)\b", text)}
    _wrong = sorted(n for n in _labels if n != int(_ver.group(1)))
    if _wrong:
        problems.append(f"The Rev number is the plan version: this is Plan v{_ver.group(1)}, so its changes are marked "
                        f"Rev {_ver.group(1)} with its square; earlier changes are unmarked. Found: "
                        + ", ".join(f"Rev {n}" for n in _wrong) + ".")
if bad:
    problems.append("Each 'Rev N' label needs its colour square right in front of it: 🟦 Rev 1 · 🟩 Rev 2 · 🟧 Rev 3 · "
                    "🟪 Rev 4, then repeat (Rev 5 = 🟦). Missing on: " + ", ".join(sorted(set(bad))[:6]) + ".")
raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
lines = [l.lstrip("#>*-• ").strip().lower() for l in raw_lines]
if not any(re.match(r"^\|\s*\**summary\**\s*\|", l, re.I) for l in raw_lines[:15]):
    problems.append("Start the plan (right under its title) with the Summary in a one-column table, so it shows in a "
                    "frame: a header row '| Summary |', a '|---|' row, then one row each for what this plan does, what "
                    "changed from the last version and why, and what I need to do — everyday words, no file names, "
                    "codes or commands.")
if re.search(r"\bRev\s*\d+\b", text) and "```diff" not in text:   # v3.1.26: reported together with the rest
    problems.append("This plan has Rev labels, so put a 'Changes in this version' block right under the Summary, "
                    "written as a ```diff code block listing every changed line ('+ ' added or changed, '- ' removed), "
                    "each with its square and Rev label.")
if not any(l.startswith("stages to finish") for l in lines):
    problems.append("Add 'Stages to finish': every stage to the real goal (build, test, merge, deploy, device check, "
                    "pilot — whatever applies), one per line, each marked 'Claude' or 'You'.")
elif not re.search(r"\b\d+\s+stages?\b", text, re.I):
    problems.append("Under 'Stages to finish', add one everyday line that explains the count, for example "
                    "'14 stages: 6 build steps (each in both apps), 6 merges by you, a final check and your iPad check'.")
# v3.1.25: the plan body is in everyday words; file names, line numbers, commit codes and code go under
# "Technical details" (everything from that heading or label on is exempt)
cut = re.search(r"^[#>*\s]*technical details\b", text, re.I | re.M)
body = re.sub(r"```.*?```", " ", text[:cut.start()] if cut else text, flags=re.S)
jargon = []
jargon += re.findall(r"\b[\w./-]*\w\.(?:js|jsx|ts|tsx|css|html|py|json|sh|sql|yml|yaml)\b", body)
jargon += re.findall(r"\blines?\s+\d+(?:\s*[-–]\s*\d+)?\b", body, re.I)
jargon += [h for h in re.findall(r"\b[0-9a-f]{7,40}\b", body) if re.search(r"\d", h) and re.search(r"[a-f]", h)]
jargon += re.findall(r"\b[A-Za-z_][\w.]*\(\)", body)
# v3.1.26: the everyday part (above Technical details) is at most about 2 pages; detail moves, it is not deleted
cap = int(cfg_.get("plan_everyday_max_chars", 6000))
everyday = text[:cut.start()] if cut else text
if len(everyday) > cap:
    problems.append(f"The everyday part of the plan (everything above 'Technical details') is {len(everyday):,} "
                    f"characters; keep it under about {cap:,} (about 2 pages). Move the detail — lists of screens, "
                    "fields, cases, tests — under 'Technical details' at the end; do not delete it.")
if jargon:
    problems.append("Write the plan in everyday words; file names, line numbers, commit codes and code go under "
                    "'Technical details' at the end. Found above it: " + ", ".join(dict.fromkeys(jargon))[:200] + ".")
# v3.1.24: every stage says Build (the work) or Check (confirming it), so the two are counted apart
if any(l.startswith("stages to finish") for l in lines):
    start = [i for i, l in enumerate(lines) if l.startswith("stages to finish")][0]
    stage_lines = []
    for raw in raw_lines[start + 1:]:
        low_l = raw.lower()
        if raw.startswith(("#", "|", "```")):
            break
        if re.match(r"^(\d+[.)]|[-*•])\s", raw):
            if re.search(r"\b(claude|you)\b", low_l):
                stage_lines.append(low_l)
        elif stage_lines:
            break
    unmarked = [l for l in stage_lines if not re.search(r"\b(build|check)\b", l)]
    if unmarked:
        problems.append("Mark every stage under 'Stages to finish' as Build (the work Claude changes and proves) or "
                        "Check (merges, live-site check, device check), next to Claude or You — "
                        f"{len(unmarked)} stage(s) have neither.")
if problems:
    log("plan-guard", {"sent_back": len(problems)})
    deny_tool("Plan sent back before approval: " + " ".join(problems) + " Fix all of it in one go and present the plan "
              "again. The shape that passes:\n" + PLAN_TEMPLATE)
model = ""
for rec in reversed(read_transcript(data.get("transcript_path"))):
    if rec.get("type") == "assistant" and not rec.get("isSidechain"):
        model = str((rec.get("message") or {}).get("model") or "")
        break
# v3.1.26: the plan's size is shown to me (no send-back): the everyday part keeps everything I must see
pages = max(1, round(len(body) / 3000))
size_note = f"Plan size: about {pages} page{'s' if pages != 1 else ''} above Technical details."
if "fable" in model.lower():
    size_note += (" Tip: this plan was written on Fable. After you approve it, type /model opus — Opus does the checking "
                  "just as well while the work runs, and costs less.")
print(json.dumps({"systemMessage": size_note}))
