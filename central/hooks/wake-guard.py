#!/usr/bin/env python3
"""PreToolUse on ScheduleWakeup (v3.3.1). A stop ends the turn: the main session does not schedule its own re-check.
HZ_Trout_Map 13 Oct: after asking me to merge the setup pull request, the session scheduled "check it again at 4:51 PM",
woke twice and wrote two more full answers ("nothing is left to merge"). My next message, or the next session start,
reads whether a pull request merged. Workers never schedule wake-ups either."""
import sys
from _common import read_hook_input, deny_tool, log

data = read_hook_input()
log("wake-guard", {"refused": "ScheduleWakeup", "worker": bool(data.get("agent_id"))})
try:
    from _common import live_proof
    live_proof("wake-guard", {"refused": "ScheduleWakeup"})
except ImportError:
    pass
deny_tool("Do not schedule a re-check. A stop ends the turn: my next message, or the next session start, reads whether "
          "the pull request merged. End your turn now.")
