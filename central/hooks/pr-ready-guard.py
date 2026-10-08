#!/usr/bin/env python3
"""Stop (v3.1.30): a final answer does not leave a pull request in draft. A session that switched its pull request
back to draft while fixing it (worker-guard asks for this) marks it ready again before the final report, which
asks the owner to merge it. Progress lines ("⏳ Working on") are exempt; one send-back per prompt."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, block, is_progress_report,
                     pr_timeline, use_round, pr_branch_state)

data = read_hook_input()
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records)
if not text or is_progress_report(text, records, cfg):
    sys.exit(0)
m = re.search(cfg["validation_line_pattern"], text)
if not m or m.group(2).split()[0] not in ("Checked", "Validated"):
    sys.exit(0)                       # not a finished answer
events, running = pr_timeline(records)
drafts = [b for b, st in pr_branch_state(data.get("session_id")).items() if st == "draft"]
if running or not drafts:
    sys.exit(0)
r = use_round("pr-ready", data.get("session_id"), 1)
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
block(f"The pull request on {', '.join(drafts)} is still a draft, so I cannot merge it. Mark it ready for review: "
      "gh pr ready <number>, or the GitHub tool's update_pull_request with draft false. Then send only one line: "
      "'#<number> is ready for review.' Do not repeat the report.", kind="work")
