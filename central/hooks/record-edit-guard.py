#!/usr/bin/env python3
"""PreToolUse (Edit/Write/MultiEdit on the working record), v3.1.26: a ledger row set to COMPLETE needs its
Evidence in the same edit. Refusing the edit now costs one small step; finding it at the end costs a whole
re-sent report."""
import re
from _common import read_hook_input, deny_tool, load_config

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
if not str(inp.get("file_path") or "").replace("\\", "/").endswith(cfg["record_file"]):
    raise SystemExit(0)
texts = [str(inp.get(k) or "") for k in ("new_string", "content")]
texts += [str(e.get("new_string") or "") for e in (inp.get("edits") or []) if isinstance(e, dict)]
bad = []
for line in "\n".join(texts).splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
    if len(cells) >= 3 and re.match(r"(?i)^(✅\s*)?complete\b", cells[1]) and not cells[2].strip(" -—"):
        bad.append(cells[0][:80])
if bad:
    deny_tool("A row set to COMPLETE needs its Evidence in the same edit (what ran and its result): " +
              "; ".join(bad[:4]) + ". Add the evidence and make the edit again.")
