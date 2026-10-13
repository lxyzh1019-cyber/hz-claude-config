#!/usr/bin/env python3
"""PreToolUse on AskUserQuestion (v3.2.17). Owner, 12 Oct: "the stop for questions sends no reminder, I have no clue
that decisions wait for me" and "be clear which answer will trigger less future conversation".
Before tappable questions reach me:
- a phone notice went out in this turn (PushNotification) that names the questions, so I know something waits;
- every option says what follows it: "ends here" or "brings back: <what>";
- the recommended option comes first and its label ends with "(Recommended)".
All problems go back in one message, once per prompt; the second try always passes (never a loop). Workers never ask."""
import json, re, sys
from _common import read_hook_input, read_transcript, last_turn, deny_tool, use_round, log, load_config

data = read_hook_input()
cfg = load_config()
if any(data.get(f) for f in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)
qs = (data.get("tool_input") or {}).get("questions") or []
if not isinstance(qs, list) or not qs:
    sys.exit(0)
turn = last_turn(read_transcript(data.get("transcript_path")))
pushes = [str((b.get("input") or {}).get("message") or "")
          for r in turn if r.get("type") == "assistant"
          for b in (((r.get("message") or {}).get("content")) or []) if isinstance(b, dict)
          and b.get("type") == "tool_use" and b.get("name") == "PushNotification"]
problems = []
# v3.3.1: a notice only when I may be away: 5 minutes or more since my last message. HZ_Trout_Map 13 Oct: the greeting
# question right after my first message was refused for a missing notice.
_away = True
try:
    from datetime import datetime as _d, timezone as _tz
    _t0 = next((r.get("timestamp") for r in turn if r.get("timestamp")), None)
    if _t0:
        _age = (_d.now(_tz.utc) - _d.fromisoformat(str(_t0).replace("Z", "+00:00"))).total_seconds() / 60
        _away = _age >= float(cfg.get("ask_notice_after_minutes", 5))
except Exception:
    pass
if _away and not any(re.search(r"(?i)\b(question|decision|answer|choose|choice)s?\b", p) for p in pushes):
    problems.append(f"First send me one phone notice with the PushNotification tool (load it with ToolSearch) that "
                    f"names what waits, for example '<app>: {len(qs)} question{'s' if len(qs) != 1 else ''} waiting "
                    f"for you'.")
FOLLOW = re.compile(r"(?i)\bends here\b|\bbrings back\b")
no_follow, no_rec = [], []
for q in qs:
    opts = [o for o in (q.get("options") or []) if isinstance(o, dict)]
    head = str(q.get("header") or q.get("question") or "")[:30]
    if any(not FOLLOW.search(str(o.get("label") or "") + " " + str(o.get("description") or "")) for o in opts):
        no_follow.append(head)
    if opts and not re.search(r"\(Recommended\)\s*$", str(opts[0].get("label") or "")):
        no_rec.append(head)
if no_follow:
    problems.append("End each option's description with what follows it: 'Ends here.' or 'Brings back: <what we must "
                    "talk about again>'. Missing in: " + "; ".join(no_follow[:4]) + ".")
if no_rec:
    problems.append("Put your recommended option first, its label ending with '(Recommended)'. Prefer the option that "
                    "ends here. Missing in: " + "; ".join(no_rec[:4]) + ".")
if not problems:
    sys.exit(0)
r = use_round("ask-guard", data.get("session_id"), 1)
if r is not None and not r[1]:
    log("ask-guard", {"passed_after_one_try": len(problems)})
    sys.exit(0)
log("ask-guard", {"sent_back": len(problems)})
try:
    from _common import live_proof
    live_proof("ask-guard", {"sent_back": len(problems)})
except ImportError:
    pass
deny_tool("Before these questions reach me: " + " ".join(problems) + " Fix all of it, then ask again.")
