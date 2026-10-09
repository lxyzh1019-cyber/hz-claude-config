#!/usr/bin/env python3
"""Stop, v3.2.8: ask me to merge a pull request only after GitHub tested its last change.
Weekly-Planner 8 Oct: the tests on GitHub had failed since PR 1 (a hint cut off by about 3 pixels), and I was still asked
to merge. When the reply asks me to merge and the session pushed or opened a pull request this turn, it must have read
the checks after its last push (gh pr checks, gh run watch or gh run view). If it did not, or they failed and the reply
does not say so, one reminder. A setup pull request (hz-setup-update-*) is left out. No reminder after a refusal by the
safety check."""
import json, re, sys
from _common import (read_hook_input, read_transcript, last_turn, last_assistant_text, block, use_round,
                     refused_by_safety_check)

data = read_hook_input()
records = read_transcript(data.get("transcript_path"))
turn = last_turn(records)
text = last_assistant_text(records) or ""
m = re.search(r"I need from you:?\**:?(.*)", text)
if not m or not re.search(r"\bmerge\b", m.group(1), re.I):
    sys.exit(0)
PUSH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b|\bgh\s+pr\s+create\b")
CHECKS = re.compile(r"\bgh\s+pr\s+checks\b|\bgh\s+run\s+(?:watch|view)\b")
last_push, checks, setup = None, [], False
results = {}
for r in turn:
    c = (r.get("message") or {}).get("content")
    for b in c if isinstance(c, list) else []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use" and b.get("name") == "Bash":
            cmd = str((b.get("input") or {}).get("command") or "")
            if PUSH.search(cmd):
                last_push, checks = b.get("id"), []
                setup = "hz-setup-update" in cmd
            elif CHECKS.search(cmd) and last_push:
                checks.append(b.get("id"))
        elif b.get("type") == "tool_result":
            results[b.get("tool_use_id")] = json.dumps(b.get("content"), ensure_ascii=False)
if not last_push or setup or refused_by_safety_check(turn):
    sys.exit(0)
failed = any(re.search(r"\bfail(?:ed|ing|ure)?\b|\bX\s", results.get(i, ""), re.I) for i in checks)
says_red = re.search(r"\b(red|fail(?:ed|ing|s)?)\b", text, re.I)
if checks and (not failed or says_red):
    sys.exit(0)
r = use_round("merge-checks", data.get("session_id"), 1)
if (r[1] if r is not None else not data.get("stop_hook_active")):
    block(("The checks of your last push failed. Fix them first, or say plainly in the reply that they are red and why "
           "I should merge anyway." if checks else
           "Before you ask me to merge, read the checks of your last push: gh pr checks <number> --watch (or gh run "
           "watch). Then answer again with the result."), kind="work")
