#!/usr/bin/env python3
"""Stop (v3.2.17): when a final answer waits on me, a phone notice in this turn names everything that waits.
Weekly-Planner 11-12 Oct: two answers waited on 10 and 6 questions, but the notices said only "pull request #149 is ready
to merge"; I had no clue that decisions waited. The 'I need from you' line asks me to act -> a PushNotification in this
turn; when the answer also holds questions, the notice names them ("question", "decision" or "answer"). If not: one
send-back per prompt, and the session then sends the notice and ends with the single line 'Notice sent.' (the
switchboard lets that line pass, so the answer is not shown twice)."""
import json, re, sys
from _common import (read_hook_input, read_transcript, last_turn, last_assistant_text, block, use_round, log,
                     refused_by_safety_check)

import os
if os.environ.get("HZ_NOTICE_CHECK_OFF"):   # test switch only (older fixtures have no notice)
    sys.exit(0)
data = read_hook_input()
records = read_transcript(data.get("transcript_path"))
# the Stop input carries the final text; the session file can lag behind it (real program, 12 Oct harness)
text = str(data.get("last_assistant_message") or "") or last_assistant_text(records) or ""
m = re.search(r"I need from you:?\**:?\s*(.+)", text)
if not m:
    sys.exit(0)
need = m.group(1).strip()
if re.match(r"(?i)\W*(nothing|none|no action)\b", need):
    sys.exit(0)
turn = last_turn(records)
if refused_by_safety_check(turn):
    sys.exit(0)
pushes = [str((b.get("input") or {}).get("message") or "")
          for r in turn if r.get("type") == "assistant"
          for b in (((r.get("message") or {}).get("content")) or []) if isinstance(b, dict)
          and b.get("type") == "tool_use" and b.get("name") == "PushNotification"]
dec = re.search(r"❓\s*\**\s*Decisions\**\s*\n(.*?)(?:\n\s*---\s*\n|\Z)", text, re.S)
n_q = len([l for l in (dec.group(1).splitlines() if dec else []) if re.match(r"^\s*(\d+[.)]|[-*•])\s+\S", l)])
asks_answers = bool(n_q) or bool(re.search(r"(?i)\b(answer|decide|choose|pick)\b|\bquestions?\b", need))
QWORDS = re.compile(r"(?i)\b(question|decision|answer|choose|choice)s?\b")
if pushes and (not asks_answers or any(QWORDS.search(p) for p in pushes)):
    sys.exit(0)
r = use_round("notice-guard", data.get("session_id"), 1)
if (r[1] if r is not None else not data.get("stop_hook_active")) is False:
    sys.exit(0)
what = (f"{n_q} question{'s' if n_q != 1 else ''}" if n_q else "the questions") if asks_answers else "what you need"
why = ("Your notice did not name the questions that wait." if pushes else "No phone notice went out for this stop.")
log("notice-guard", {"pushes": len(pushes), "questions": n_q, "asks_answers": asks_answers})
try:
    from _common import live_proof
    live_proof("notice-guard", {"sent_back": why})
except ImportError:
    pass
block(f"{why} Send me one phone notice now with the PushNotification tool (load it with ToolSearch). Name everything in "
      f"your 'I need from you' line, for example '<app>: {what} + merge #<number> waiting'.", kind="work")
