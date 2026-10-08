#!/usr/bin/env python3
"""PreToolUse (Agent, Task, Bash), main session only, v3.2.2: one report per piece of work.
When the main session starts a helper (Claude Code runs every helper in the background) or a background command,
it is told at once: end this turn with the one ⏳ line, and write the full report only when the last one finished.
Real case (Weekly-Planner 2026-10-08): a full report while the reviewer and a GitHub run still went, then a second
full report when the reviewer finished, so the decisions and closing lines showed twice. A Stop check cannot undo
an answer that is already on the screen; only telling the session before it writes can. Never blocks a tool."""
import sys
from _common import read_hook_input, load_config, add_context, WAIT_TEXT, log
import formats as F

data = read_hook_input()
import os
if os.environ.get("HZ_REPORT_TIMING_OFF"):
    sys.exit(0)   # replay: older tests check other hooks' output alone
cfg = load_config()
if any(data.get(k) and str(data.get(k)) != str(data.get("session_id"))
       for k in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)   # a helper's own tools: the helper reports to the main session, not to me
tool = str(data.get("tool_name") or "")
inp = data.get("tool_input") or {}
if tool in ("Agent", "Task"):
    what = "the helper you are starting"
elif tool == "Bash" and inp.get("run_in_background"):
    what = "the command you are starting"
else:
    sys.exit(0)
log("report-timing", {"tool": tool})
add_context("PreToolUse", WAIT_TEXT.format(what=what, line=F.WORKING_LINE))
