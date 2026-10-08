#!/usr/bin/env python3
"""Stop, v3.2.2: a full report written while a helper or background command still runs.
No send-back: the answer is already on the screen, and a send-back only shows it again (v3.1.31). The problem is
saved for the next step, counted in the session summary ("Early reports"), and logged as live proof."""
import sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, still_running, save_fixes,
                     bump_stat, live_proof, log)

data = read_hook_input()
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records) or ""
if "📌" not in text:
    sys.exit(0)   # no closing lines: not a full report
running = still_running(records, data.get("transcript_path"))
if not running:
    sys.exit(0)
sid = data.get("session_id")
bump_stat(sid, "early_reports")
live_proof("report-early", {"still_running": running[:5]})
log("report-early", {"still_running": running[:5]})
save_fixes(sid, ["You wrote a full report while " + ", ".join(running[:3]) + " still ran. While anything runs in the "
                 "background, end each turn with the one ⏳ line only. Write one full report when the last one finished, "
                 "and give only what is new."])
sys.exit(0)
