#!/usr/bin/env python3
"""PostToolUse (v3.1.31): right after a pull request opens or is marked ready for review, ask the main session to send
the owner a notice on their account (Claude Code's PushNotification tool, deferred: load it with ToolSearch). It comes
before the answer, so nothing is sent back and the answer shows once. Claude Code skips the push while the owner is
watching the session; that is fine. Workers never get it."""
import json, re, sys
from _common import read_hook_input, load_config, add_context, log

data = read_hook_input()
cfg = load_config()
if any(data.get(f) for f in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)
tool = str(data.get("tool_name") or "")
inp = data.get("tool_input") or {}
resp = json.dumps(data.get("tool_response") or "", ensure_ascii=False)[:2000].lower()
if re.search(r'"is_error":\s*true|"interrupted":\s*true|\berror\b.*\bpull request\b|could not|failed', resp):
    sys.exit(0)                                   # the pull request did not open
ready = False
if tool == "Bash":
    cmd = str(inp.get("command") or "")
    ready = bool(re.search(r"(^|[;&|\n]\s*)gh\s+pr\s+create\b", cmd) or
                 re.search(r"(^|[;&|\n]\s*)gh\s+pr\s+ready\b(?![^;&|\n]*--undo)", cmd))
elif re.match(r"^mcp__.*create_pull_request$", tool):
    ready = inp.get("draft") is not True
elif re.match(r"^mcp__.*update_pull_request$", tool):
    ready = inp.get("draft") is False
if not ready:
    sys.exit(0)
log("notice-reminder", {"tool": tool})
add_context("PostToolUse", "[notice] A pull request is now ready for review. Before your answer, send the owner one "
            "notice with the PushNotification tool (load it with ToolSearch): '<app>: pull request #<number> is ready "
            "to merge'. Do not mention the notice in the answer. If the tool is not in this session, skip it.")
