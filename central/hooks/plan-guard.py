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
from _common import read_hook_input, deny_tool, log, read_transcript

data = read_hook_input()
inp = data.get("tool_input") or {}


def plan_text():
    for v in inp.values():
        if isinstance(v, str) and len(v) > 200:
            return v
    for v in inp.values():
        if isinstance(v, str) and v.endswith(".md") and os.path.isfile(v):
            return open(v, encoding="utf-8", errors="replace").read()
    home = os.path.expanduser("~")
    files = sorted(glob.glob(os.path.join(home, ".claude", "plans", "*.md")), key=os.path.getmtime, reverse=True)
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
for m in re.finditer(r"\bRev\s*(\d+)\b", text):
    n = int(m.group(1))
    before = text[max(0, m.start() - 4):m.start()]
    if SQUARES[n % 4] not in before:
        bad.append(f"Rev {n}")
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
if bad == [] and re.search(r"\bRev\s*\d+\b", text) and "```diff" not in text:
    problems.append("This plan has Rev labels, so put a 'Changes in this version' block right under the Summary, "
                    "written as a ```diff code block listing every changed line ('+ ' added or changed, '- ' removed), "
                    "each with its square and Rev label.")
if not any(l.startswith("stages to finish") for l in lines):
    problems.append("Add 'Stages to finish': every stage to the real goal (build, test, merge, deploy, device check, "
                    "pilot — whatever applies), one per line, each marked 'Claude' or 'You'.")
elif not re.search(r"\b\d+\s+stages?\b", text, re.I):
    problems.append("Under 'Stages to finish', add one everyday line that explains the count, for example "
                    "'14 stages: 6 build steps (each in both apps), 6 merges by you, a final check and your iPad check'.")
if problems:
    log("plan-guard", {"sent_back": len(problems)})
    deny_tool("Plan sent back before approval: " + " ".join(problems) + " Fix it and present the plan again.")
model = ""
for rec in reversed(read_transcript(data.get("transcript_path"))):
    if rec.get("type") == "assistant" and not rec.get("isSidechain"):
        model = str((rec.get("message") or {}).get("model") or "")
        break
if "fable" in model.lower():
    print(json.dumps({"systemMessage": "Tip: this plan was written on Fable. After you approve it, type /model opus — "
                                       "Opus does the checking just as well while the work runs, and costs less."}))
