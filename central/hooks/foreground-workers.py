#!/usr/bin/env python3
"""PreToolUse Agent|Task, main session only (v3.2.14): workers run in the foreground.
A background worker wakes the main session when it finishes, sends a message, or when one of its own background runs
ends; every wake-up is a new turn, and every turn shows a line (Weekly-Planner 10-11 Oct: up to 11 '⏳ Working on' lines
in one round; text rules could not stop them, because the model writes something each turn). In the foreground the
worker's result comes back inside the same turn: no wake-ups, no lines in between. Several workers started in one
message still run at the same time. The hook rewrites the call (updatedInput), so it does not depend on the model.
HZ_BACKGROUND_WORKERS=1 keeps background workers."""
import json, os, sys
from _common import read_hook_input, log

data = read_hook_input()
inp = dict(data.get("tool_input") or {})
if data.get("agent_id") or not inp.get("run_in_background") or os.environ.get("HZ_BACKGROUND_WORKERS"):
    sys.exit(0)
inp["run_in_background"] = False
log("foreground-workers", {"tool": data.get("tool_name"), "type": inp.get("subagent_type")})
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                         "updatedInput": inp}}))
