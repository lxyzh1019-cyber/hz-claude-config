#!/usr/bin/env python3
"""PreToolUse (every tool), v3.1.29: the session start no longer carries the rules (Claude Code cuts hook text over
10,000 characters to a 2,000-character preview), so the main session reads the rules file first. Until it does,
tools that change or run something are refused with the exact path; reading and searching stay allowed. Workers
(subagents) are never stopped: they have their own instructions. The session start clears the mark, so every new
start or /compact reads the rules again."""
import json, os, sys
from _common import read_hook_input, load_config, deny_tool, log, STATE_DIR, RULES_PATH

if os.environ.get("HZ_RULES_FIRST_OFF"):   # test suite only: older tests run as if the rules were read
    sys.exit(0)
data = read_hook_input()
cfg = load_config()
if any(data.get(f) for f in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)                       # a worker
if not os.path.exists(RULES_PATH):
    sys.exit(0)                       # nothing to read: session start already said "NOT loaded"
sid = str(data.get("session_id") or "")
from _common import sess_get, sess_set   # v3.2.7: one mark per session (two sessions in one folder blocked each other)
if sess_get("rules-read.json", sid):
    sys.exit(0)
tool = str(data.get("tool_name") or "")
inp = data.get("tool_input") or {}
path = str(inp.get("file_path") or inp.get("path") or "").replace("\\", "/").lower()
own = RULES_PATH.replace("\\", "/").lower()
if tool == "Read" and (path == own or ("hz-rules" in path and path.endswith("rules/claude-rules.md"))):
    sess_set("rules-read.json", sid, True)
    log("rules-first-guard", {"rules_read": True})
    sys.exit(0)
if tool in set(cfg.get("rules_first_allowed_tools") or ["Read", "Glob", "Grep", "LS", "TodoWrite"]):
    sys.exit(0)
# v3.2.15: Read, Grep and Glob no longer start the checks (12% of a session's time on Windows), so the Read of the rules
# is found in the session file at the next checked step.
try:
    from _common import read_transcript as _rt
    for _r in _rt(data.get("transcript_path")):
        for _b in ((_r.get("message") or {}).get("content") or []) if isinstance((_r.get("message") or {}).get("content"), list) else []:
            if isinstance(_b, dict) and _b.get("type") == "tool_use" and _b.get("name") == "Read":
                _p = str((_b.get("input") or {}).get("file_path") or "").replace("\\", "/").lower()
                if _p == own or ("hz-rules" in _p and _p.endswith("rules/claude-rules.md")):
                    sess_set("rules-read.json", sid, True)
                    sys.exit(0)
except SystemExit:
    raise
except Exception:
    pass
log("rules-first-guard", {"refused": tool})
deny_tool(f"Read the working rules first, with the Read tool: {RULES_PATH} — then do this step again.")
