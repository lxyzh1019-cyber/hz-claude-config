#!/usr/bin/env python3
"""PreToolUse hook on ExitPlanMode (the plan's Approve step): send a plan back before I see it when it
- contains colour code (HTML such as <span style=…>), which the plan window shows as raw text;
- has a "Rev N" label without its colour square in front (🟦 Rev 1 · 🟩 Rev 2 · 🟧 Rev 3 · 🟪 Rev 4, then repeat);
- does not open with a "Summary" in everyday words within its first lines;
- has no "Stages to finish" list with an owner (Claude or You) on each stage.
The plan text is taken from the tool input, or from a plan file the input names, or from the newest plan file."""
import glob, os, re, time
from _common import read_hook_input, deny_tool, log

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
lines = [l.strip().lstrip("#>*-• ").strip().lower() for l in text.splitlines() if l.strip()]
if not any(l.startswith("summary") for l in lines[:12]):
    problems.append("Start the plan (right under its title) with 'Summary' in everyday words, no file names, codes or "
                    "commands: what this plan does, what changed from the last version and why, and what I need to do.")
if not any(l.startswith("stages to finish") for l in lines):
    problems.append("Add 'Stages to finish': every stage to the real goal (build, test, merge, deploy, device check, "
                    "pilot — whatever applies), one per line, each marked 'Claude' or 'You'.")
if problems:
    log("plan-guard", {"sent_back": len(problems)})
    deny_tool("Plan sent back before approval: " + " ".join(problems) + " Fix it and present the plan again.")
