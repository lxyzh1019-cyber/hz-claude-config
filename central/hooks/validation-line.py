#!/usr/bin/env python3
"""Stop hook: a final answer ends with the validation line; a progress report (workers still running)
ends with the Progress line instead. The Progress line is accepted only if the session dispatched a worker."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, block,
                     is_progress_report)

data = read_hook_input()
if data.get("stop_hook_active"):
    sys.exit(0)  # already continuing because of a stop hook; never loop
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records)
if not text:
    sys.exit(0)
if re.search(cfg["validation_line_pattern"], text):
    sys.exit(0)
if is_progress_report(text, records, cfg):
    sys.exit(0)
if re.search(cfg["progress_line_pattern"], text):
    block("A Progress line is only for reports while dispatched workers are still running, and no worker was "
          "dispatched in this session. If the work is finished, end with the validation line instead: "
          "'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|Uncertain'.")
block("This reply is missing its closing line. If any worker is still running, this is a progress report: open with "
      "'In progress — not done', drop any regression table and Confidence/Status line, and end with "
      "'Progress: <n> of <total> done · Running: <names>'. Otherwise it is a final answer: end with "
      "'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|Uncertain' with honest values.")
