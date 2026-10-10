#!/usr/bin/env python3
"""PreToolUse hook on ExitPlanMode (the plan's Approve step).
v3.2.0: the plan check makes the change view itself. It saves each plan it shows, per plan name. At the next showing
it compares the two texts and puts "Changed since last time" right under the title: only the changed lines, with the
round's square. The model writes no change list and no Rev markers.
- A plan keeps its number while we discuss it; each changed showing is a new round.
- My Approve closes the version. A changed text with the same number after Approve is sent back: it is the next version.
- The planner helper writes the first showing of each version; later rounds of the same version may come from the
  main session.
It also sends a plan back before I see it when it has HTML, no framed Summary, no "Stages to finish" with owners,
Build/Check marks and a count line, file names or code above Technical details, a new plan (Plan v1 Rev 1) with more
than 7,200 characters above Technical details, or misses an agreed design decision. All problems go back in one message.
The plan text is taken from the tool input, or from a plan file the input names, or from the newest plan file."""
import glob, os, re, time
import json
from _common import read_hook_input, deny_tool, log, read_transcript, PROJECT_DIR, PLAN_TEMPLATE, load_config, last_turn
cfg_ = load_config()

data = read_hook_input()
inp = data.get("tool_input") or {}

# v3.1.28: a big or risky plan (the plan gate's strong signals) is checked by the reviewer before I see it
try:
    from _common import STATE_DIR, prompt_number, last_turn
    from _common import sess_get as _sg7
    _sid = str(data.get("session_id") or "")
    _st = _sg7("plan-review.json", _sid) or {}
    if isinstance(_st, dict) and _st.get("n") == prompt_number(_sid):
        _turn = last_turn(read_transcript(data.get("transcript_path")))
        _reviewed = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                        and str((b.get("input") or {}).get("subagent_type") or "") in ("reviewer", "reviewer-light")
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
    """(text, file). Claude Code fills the tool input from the plan file (planFilePath; the model writes about 31
    tokens to call the tool), so the file is read first: the check can then write the change marks into it."""
    f = str(inp.get("planFilePath") or "")
    if f and os.path.isfile(f):
        return open(f, encoding="utf-8", errors="replace").read(), f
    for v in inp.values():
        if isinstance(v, str) and len(v) > 200:
            return v, ""
    for v in inp.values():
        if isinstance(v, str) and v.endswith(".md") and os.path.isfile(v):
            return open(v, encoding="utf-8", errors="replace").read(), v
    home = os.path.expanduser("~")
    files = sorted(glob.glob(os.path.join(PROJECT_DIR, "plans", "*.md")) +
                   glob.glob(os.path.join(home, ".claude", "plans", "*.md")), key=os.path.getmtime, reverse=True)
    if files and time.time() - os.path.getmtime(files[0]) < 1800:
        return open(files[0], encoding="utf-8", errors="replace").read(), files[0]
    return "", ""


text, plan_file = plan_text()
if not text:
    log("plan-guard", {"skipped": "no plan text found", "input_keys": sorted(inp)})
    raise SystemExit(0)

from _common import (plan_store_load, plan_store_save, plan_mark_approved, plan_name_of, plan_version_of,
                     live_proof, plan_norm)
import planmarks
shown_text = text                       # what the tool would show now (may hold marks and a change list)
text = planmarks.strip_marks(text)      # the plan itself, without any marks
problems = []
reasons = []                            # v3.2.0: each send-back reason by name, for the log
if re.search(r"<\s*(span|font|div|mark|b|i|u|p)\b[^>]*>|style\s*=\s*[\"']", text, re.I):
    problems.append("It contains colour code (HTML such as <span style=…>); the plan window shows that as raw text. "
                    "Remove all HTML.")
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
        problems.append("These agreed design decisions are not in the plan. Add each one with its search phrase. If one "
                        "is not agreed after all, mark it open in the record. Missing: " + "; ".join(_missing[:8])
                        + (f" (+{len(_missing) - 8} more)" if len(_missing) > 8 else "") + ".")
raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
lines = [l.lstrip("#>*-• ").strip().lower() for l in raw_lines]
# v3.2.11: the Quick read (v3.2.9) is the plan's opening; the older Summary table also passes. Weekly-Planner 10 Oct:
# this check still asked for the table while the shape it showed was the Quick read, so the plan went back 3 times.
if not any(re.match(r"^\|\s*\**summary\**\s*\|", l, re.I) or re.match(r"^\**summary\**\s*$", l, re.I)
           for l in raw_lines[:15]):
    problems.append("Start the plan right under its title with the Quick read, as in the shape below: Quick read, "
                    "Summary, What changed, Decisions, Next steps. Use everyday words, with no file names or code.")
if not any(l.startswith("stages to finish") for l in lines):
    problems.append("Add 'Stages to finish' with every stage to the real goal, one per line. Examples: build, test, "
                    "merge, deploy, device check. Mark each stage 'Claude' or 'You'.")
elif not re.search(r"\b\d+\s+stages?\b", text, re.I):
    problems.append("Under 'Stages to finish', add one everyday line that explains the count. Example: '14 stages: "
                    "6 build steps, 6 merges by you, a final check and your iPad check'.")
# v3.1.25: the plan body is in everyday words; file names, line numbers, commit codes and code go under
# "Technical details" (everything from that heading or label on is exempt)
cut = re.search(r"^[#>*\s]*technical details\b", text, re.I | re.M)
body = re.sub(r"```.*?```", " ", text[:cut.start()] if cut else text, flags=re.S)
jargon = []
jargon += re.findall(r"\b[\w./-]*\w\.(?:js|jsx|ts|tsx|css|html|py|json|sh|sql|yml|yaml)\b", body)
jargon += re.findall(r"\blines?\s+\d+(?:\s*[-–]\s*\d+)?\b", body, re.I)
jargon += [h for h in re.findall(r"\b[0-9a-f]{7,40}\b", body) if re.search(r"\d", h) and re.search(r"[a-f]", h)]
jargon += re.findall(r"\b[A-Za-z_][\w.]*\(\)", body)
everyday = text[:cut.start()] if cut else text
if jargon:
    # v3.2.11: quote each find with the words around it and its line, so it is found in one go. 10 Oct: "Found above
    # it: line 149" was read as a line number of the file, and the plan went back three times.
    _q = []
    for _j in list(dict.fromkeys(jargon))[:4]:
        _at = body.find(_j)
        _ln = body.count("\n", 0, _at) + 1 if _at >= 0 else 0
        _ctx = re.sub(r"\s+", " ", body[max(0, _at - 30):_at + len(_j) + 30]).strip() if _at >= 0 else _j
        _q.append(f"'{_j}' in plan line {_ln}: …{_ctx}…")
    problems.append("Write the plan in everyday words; file names, line numbers, commit codes and code go under "
                    "'Technical details' at the end. Found above it: " + "; ".join(_q) + ".")
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
        problems.append("Mark every stage under 'Stages to finish' as Build or Check, next to Claude or You. Build is "
                        "what Claude changes and proves. Check is a merge, a live-site check or a device check. "
                        f"{len(unmarked)} stage(s) have no mark.")
    # v3.2.0: every Build stage by Claude names its proof and its size (S, M or L), so "done" is shown, not said,
    # and the summary can compare the actual time with the estimate
    _build = [l for l in stage_lines if re.search(r"\bclaude\b", l) and re.search(r"\bbuild\b", l)]
    _noproof = [l for l in _build if not re.search(r"\bproof:\s*\S", l)]
    _nosize = [l for l in _build if not re.search(r"\bsize:\s*[sml]\b", l)]
    if (_noproof or _nosize) and not os.environ.get("HZ_STAGE_TAGS_OFF"):   # test switch only
        problems.append("Each Build stage by Claude names 'proof: <tests, pictures or figures that show it is right>' "
                        "and 'size: S|M|L' (S about 15 min, M about 45, L about 90). "
                        f"Missing proof: {len(_noproof)} stage(s); missing size: {len(_nosize)}.")
        reasons.append("no proof or size per stage")
# v3.2.1: questions before the plan. A plan reaches me with no open questions: the session asks them in chat first,
# then shows the plan once with my answers written in (real case: Plan v4 Rev 1 asked two questions inside the plan,
# I answered instead of approving, and Rev 2 only wrote the answers in).
_dec = re.search(r"(?ims)^#*\s*❓\s*Decisions\s*$(.*?)(?=^#+\s|\Z)", text)
_open_q = []
if _dec:
    for _l in _dec.group(1).splitlines():
        _s = _l.strip().lstrip("-*• ").strip()
        _s2 = re.sub(r"^\d+[.)]\s*", "", _s)
        _s2 = re.sub(r"^[" + "🟦🟩🟧🟪" + r"]\s*\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*", "", _s2)
        if _s2 and not re.match(r"(?i)\**(decided|none open|checked against|removes|no open)", _s2) and \
                (re.search(r"\?", _s2) or re.search(r"(?i)\brecommended\s*:", _s2)):
            _open_q.append(_s2[:80])
if _open_q and not os.environ.get("HZ_QUESTIONS_CHECK_OFF"):   # test switch only
    problems.append("This plan still holds open questions: " + "; ".join(_open_q[:3]) + ". Ask them in chat first, all "
                    "at once, numbered, each with your recommendation. After my answers, show the plan with them "
                    "written in as decided, so I only approve it.")
    reasons.append("open questions in the plan")
# v3.2.0: versions and Revs. Version = approvals; Rev = each showing inside a version, from Rev 1.
_store = plan_mark_approved(plan_store_load(), read_transcript(data.get("transcript_path")))
_name, _ver = plan_name_of(text), plan_version_of(text)
_entry = (_store["plans"].get(_name) if _name else None) or None
# v3.2.0: a new session (or the first session on 3.2.0) has no saved plan yet. The newest committed plan file with the
# same plan name and a lower version (an approved one: approved plans are committed in plans/) becomes the base, so
# the first change in the new session still gets its coloured marks.
if _name and _ver is not None and not _entry and not os.environ.get("HZ_PLAN_ROUNDS_OFF"):
    _best = None
    for _f in glob.glob(os.path.join(PROJECT_DIR, "plans", "*.md")):
        if plan_file and os.path.normcase(os.path.abspath(_f)) == os.path.normcase(os.path.abspath(plan_file)):
            continue
        try:
            _ft = planmarks.strip_marks(open(_f, encoding="utf-8", errors="replace").read())
        except OSError:
            continue
        _fv = plan_version_of(_ft)
        if plan_name_of(_ft) == _name and _fv is not None and _fv < _ver and (not _best or _fv > _best[0]):
            _best = (_fv, _ft)
    if _best:
        _entry = {"version": _best[0], "rev": 1, "text": _best[1], "approved": True, "history": []}
        live_proof("plan-guard", {"base": f"committed Plan v{_best[0]} from plans/"})
_rounds_on = not os.environ.get("HZ_PLAN_ROUNDS_OFF")       # test switch only
_base, _rev, _since, _hist = None, 1, "", []
if _name and _ver is not None and _rounds_on and _entry:
    _ev = int(_entry.get("version") or 0)
    _same = plan_norm(_entry.get("text")) == plan_norm(text)
    if _ver == _ev and _entry.get("approved") and not _same:
        problems.append(f"Plan v{_ver} is approved, so this change is the next version. Change the title to "
                        f"Plan v{_ver + 1} and show it again.")
        reasons.append("changed after approval")
    elif _ver < _ev:                     # numbering started again (seen in the money session: v19, then v1):
        _base, _rev, _since, _hist = _entry.get("text"), 1, f"Plan v{_ev}", []   # no send-back; still compared
        live_proof("plan-guard", {"note": f"version went from v{_ev} to v{_ver}"})
    elif _ver == _ev and _same:          # shown again unchanged (for example after the marks were added)
        _base, _rev, _since, _hist = _entry.get("base"), int(_entry.get("rev") or 1), _entry.get("since") or "", \
            _entry.get("history") or []
    elif _ver == _ev:                    # a new showing of the same version
        _base, _rev, _since = _entry.get("text"), int(_entry.get("rev") or 1) + 1, "you last looked"
        _hist = (_entry.get("history") or []) + [_entry.get("cur") or {"rev": int(_entry.get("rev") or 1), "n": 0}]
    elif _ver > _ev:                     # the next version: Rev 1, compared with the last version shown
        _base, _rev, _since, _hist = _entry.get("text"), 1, f"Plan v{_ev}", []
_first_showing = _ver is not None and (not _entry or not _rounds_on)
# v3.2.0: the size limit applies only to the first showing of a new plan (Plan v1 Rev 1): 7,200 (6,000 + 20%, owner)
# v3.2.9: no size send-back any more (owner, 9 Oct: soft goals; a send-back costs more time and tokens than it saves).
# The Quick read's word count is shown to the owner with the plan size below.
# v3.2.0: the planner helper writes the first showing of a new plan, and big changes (the plan gate's strong
# signals); the main session writes later Revs and versions
_big = False
try:
    from _common import STATE_DIR as _SD, prompt_number as _pn
    from _common import sess_get as _sg7b
    _pr = _sg7b("plan-review.json", data.get("session_id")) or {}
    _big = isinstance(_pr, dict) and _pr.get("n") == _pn(data.get("session_id"))
except (OSError, ValueError, ImportError):
    pass
from _common import agent_on_pc as _aop
if (re.search(r"(?m)^#*\s*Plan v\d+", text) and (_first_showing or _big)
        and any(_aop(x) for x in (cfg_.get("planner_helpers") or ["planner", "planner-opus"]))   # v3.2.7: only if it exists here
        and not os.environ.get("HZ_PLANNER_CHECK_OFF")):   # test switch only
    _planners = cfg_.get("planner_helpers") or ["planner", "planner-opus"]
    _turn = last_turn(read_transcript(data.get("transcript_path")))
    _planned = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                   and str((b.get("input") or {}).get("subagent_type") or "") in _planners
                   for r in _turn if r.get("type") == "assistant"
                   for b in ((r.get("message") or {}).get("content") or [])
                   if isinstance((r.get("message") or {}).get("content"), list))
    if not _planned:
        problems.append(f"The planner helper writes a new plan and big changes. Send '{_planners[0]}' with the planner "
                        "file, the plan shape and the agreed points. Save the plan it returns in one step. Only if its "
                        f"model is not available, send '{_planners[-1]}' with 'Fallback: <the error>'.")
        reasons.append("planner not used")
# v3.2.0: no send-back for a "What changed" line that still says "First version": the change list made by code
# already shows what changed, and a send-back costs one main-session step.
if problems:
    _names = reasons + [r for r in ("html", "agreed point missing", "no summary", "no stages", "no count line",
                                    "file names above technical details", "no build/check mark")
                        if any(k in " ".join(problems).lower() for k in {
                            "html": ["html"], "agreed point missing": ["agreed design decisions"],
                            "no summary": ["summary table"], "no stages": ["add 'stages to finish'"],
                            "no count line": ["explains the count"],
                            "file names above technical details": ["found above it"],
                            "no build/check mark": ["as build or check"]}[r])]
    log("plan-guard", {"sent_back": len(problems), "reasons": _names})
    live_proof("plan-guard", {"sent_back": _names})
    deny_tool("Plan sent back before I see it: " + " ".join(problems) + " Fix all of it in one go, then show the plan "
              "again. The shape that passes:\n" + PLAN_TEMPLATE)
# v3.2.0: the coloured marks and the change list, made by code
_cur = {"rev": _rev, "n": 0, "since": _since if _rev == 1 and _base is not None else ""}
_final = text
if _base is not None:
    _final, (_n, _g) = planmarks.apply(text, _base, _ver, _rev, _hist, _since)
    _cur = {"rev": _rev, "n": _n, "gist": _g}
if _base is not None and plan_norm(shown_text) != plan_norm(_final):
    if plan_file:
        try:
            with open(plan_file, "w", encoding="utf-8") as _f:
                _f.write(_final)
            live_proof("plan-guard", {"marks": "written into the plan file", "version": _ver, "rev": _rev})
            deny_tool(f"The plan check added the coloured change marks (Plan v{_ver} · Rev {_rev}) to the plan file. "
                      "Show the plan again now. Change nothing.")
        except OSError:
            pass
    live_proof("plan-guard", {"marks": "asked to paste", "version": _ver, "rev": _rev})
    deny_tool("Replace the plan with this text, exactly as given, then show it again. It has the coloured change "
              "marks.\n\n" + _final)
if _name and _ver is not None and _rounds_on:
    _store["plans"][_name] = {"version": _ver, "rev": _rev, "text": text, "base": _base, "since": _since,
                              "history": _hist, "cur": _cur, "approved": False, "file": plan_file}
    _store["last"] = _name
    plan_store_save(_store)
live_proof("plan-guard", {"shown": f"Plan v{_ver} Rev {_rev}", "file": bool(plan_file)})
model = ""
for rec in reversed(read_transcript(data.get("transcript_path"))):
    if rec.get("type") == "assistant" and not rec.get("isSidechain"):
        model = str((rec.get("message") or {}).get("model") or "")
        break
# v3.1.26: the plan's size is shown to me (no send-back): the everyday part keeps everything I must see
pages = max(1, round(len(body) / 3000))
size_note = f"Plan size: about {pages} page{'s' if pages != 1 else ''} above Technical details."
try:   # v3.2.9: the Quick read against its goal (a note, never a send-back)
    import formats as _F9
    _qr = _F9.quick_read_words(text)
    if _qr is not None:
        size_note += (f" Quick read: {_qr} words, about {max(1, -(-_qr // 200))} min"
                      + (f" (goal about {_F9.QUICK_READ_GOAL_WORDS})." if _qr > _F9.QUICK_READ_GOAL_WORDS else "."))
except Exception:
    pass
_main = cfg_.get("main_session_model") or {}
if model and _main.get("id") and _main["id"] not in model:   # v3.1.30: the planner helper plans; the session runs on Opus
    size_note += (f" This session runs on {model}; the work after approval needs only {_main.get('name')}: type "
                  f"{_main.get('switch')} — the planner helper still plans on the first-choice model.")
print(json.dumps({"systemMessage": size_note}))
