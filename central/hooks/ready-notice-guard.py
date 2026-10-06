#!/usr/bin/env python3
"""Stop (v3.1.30): when a finished answer asks the owner to merge, the owner gets a notice on their account — the
session sends one with Claude Code's PushNotification tool (a deferred tool: load it with ToolSearch first). One
send-back per prompt; a session without the tool says so in one line and is not asked again."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, last_turn, block,
                     is_progress_report, use_round, tool_uses, plain_lines)

data = read_hook_input()
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records)
if not text or is_progress_report(text, records, cfg):
    sys.exit(0)
m = re.search(cfg["validation_line_pattern"], text)
if not m or m.group(2).split()[0] not in ("Checked", "Validated"):
    sys.exit(0)                                       # not a finished answer
need = [l for l in plain_lines(text) if re.sub(r"^\W+", "", l).lower().startswith("i need from you")]
if not need or not re.search(r"\bmerge|合并", need[-1], re.I):
    sys.exit(0)                                       # nothing to merge
turn = last_turn(records)
names = [str(b.get("name") or "") for b in tool_uses(turn)]
if any("pushnotification" in n.lower() for n in names):
    sys.exit(0)
if re.search(r"no notice tool in this session", "\n".join(
        str(b.get("text") or "") for r in records if r.get("type") == "assistant"
        for b in ((r.get("message") or {}).get("content") or []) if isinstance(b, dict)), re.I):
    sys.exit(0)                                       # said once: the tool is not here
r = use_round("ready-notice", data.get("session_id"), 1)
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
block("This answer asks the owner to merge, so send a notice to their account first: load the PushNotification tool "
      "with ToolSearch, then send one short notice — '<app>: pull request #<number> is ready to merge'. Then send only "
      "one line: 'Notice sent.' If this session has no PushNotification tool, send only: 'No notice tool in this "
      "session.' Do not repeat the report.")
