#!/usr/bin/env python3
"""Stop hook (QC2): a reply that tells the user to delete, empty, reset, force-push or wipe things is sent back
unless it uses the separate-confirmation form: every item named, and "needs your separate yes"."""
import re, sys
from _common import read_hook_input, load_config, read_transcript, last_assistant_text, block, use_round

data = read_hook_input()
cfg = load_config()
text = last_assistant_text(read_transcript(data.get("transcript_path")))
if not text:
    sys.exit(0)
low = text.lower()
hits = [p for p in cfg.get("destructive_phrases", []) if re.search(p, low)]
if not hits or "needs your separate yes" in low:
    sys.exit(0)
r = use_round("qc", data.get("session_id"), int(cfg.get("auto_fix_max_rounds", 1)))
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
block("QC2: this reply tells me to do something destructive (" + ", ".join(h.strip("\\b") for h in hits[:3]) + "). Remove "
      "that step. Or put it in its own message: name every item, say why, and say what I will see after. End that "
      "message with 'This needs your separate yes.' Send only that corrected part.", kind="work")   # v3.1.31: safety
