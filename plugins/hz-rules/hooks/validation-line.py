#!/usr/bin/env python3
"""Stop hook: the final answer must end with the validation line."""
import re, sys
from _common import read_hook_input, load_config, read_transcript, last_assistant_text, block

data = read_hook_input()
if data.get("stop_hook_active"):
    sys.exit(0)  # already continuing because of a stop hook; never loop
cfg = load_config()
text = last_assistant_text(read_transcript(data.get("transcript_path")))
if not text:
    sys.exit(0)
if re.search(cfg["validation_line_pattern"], text):
    sys.exit(0)
block("Final answer is missing the required validation line. Append exactly one closing line in the form "
      "'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|Uncertain' "
      "with honest values; name mixed results and untested scope before it.")
