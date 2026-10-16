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
# v3.3.0: the 9 PM reminder comes at the next step after 9 PM Edmonton time, not only at a new message from me
# (12 Oct: one turn ran from 14:03 to 22:54 without a message, so the reminder never came)
try:
    import os as _os
    from _common import edmonton_hour, STATE_DIR as _SD
    from datetime import datetime as _d
    _ev = _d.now().strftime("%Y-%m-%d")
    _np = _os.path.join(_SD, "evening-reminder.json")
    try:
        _done = json.load(open(_np, encoding="utf-8")).get("day")
    except (OSError, ValueError):
        _done = None
    if edmonton_hour() >= int(cfg.get("evening_hour", 21)) and _done != _ev and not ready:
        _os.makedirs(_SD, exist_ok=True)
        json.dump({"day": _ev}, open(_np, "w", encoding="utf-8"))
        log("notice-reminder", {"evening": True})
        add_context("PostToolUse", "[evening] It is after 9 PM in Edmonton. In your next final answer, add one sentence "
                    "to the 'I need from you' line: \"Before you sleep, type 'night check'.\"")
except Exception:
    pass
if not ready:
    sys.exit(0)
log("notice-reminder", {"tool": tool})
try:
    from _common import live_proof
    live_proof("notice-reminder", {"tool": tool})
except ImportError:
    pass
# v3.2.17: the notice names everything that waits (11-12 Oct: "ready to merge" while 10 and 6 questions also waited)
# v3.3.3 (owner, 15 Oct): the summary report and the time and tokens by task and by model, measured here (a hook may
# read the session file; the session itself may not in a cloud session). The chat summary stays short, with one link.
_rep = ""
try:
    from _common import session_table
    _tab = session_table(data.get("transcript_path"))
    if _tab:
        _rep = ("\n[report] Put the report into the pull request text (gh pr edit <number> --body-file): what was done; "
                "decisions and the option used; differences from the plan; tests and review results; what to improve or "
                "drop; the approved plan in a <details> section; and this measured table:\n" + _tab +
                "\nYour final answer starts with at most 3 short lines: ✅ Done: <what> · <tests> · <review>; "
                "Time <n> min · tokens <n> M (by model); Plan Rev <n> · Report: <the pull request link>.")
except Exception:
    pass
add_context("PostToolUse", "[notice] A pull request is now ready for review. Right before your final answer, send me "
            "one notice with the PushNotification tool (load it with ToolSearch) that names everything in your 'I need "
            "from you' line, for example '<app>: 6 questions + merge #<number> waiting' or '<app>: merge #<number> "
            "waiting'. Do not mention the notice in the answer. If the tool is not in this session, skip it." + _rep)
