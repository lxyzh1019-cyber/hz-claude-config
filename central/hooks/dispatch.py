#!/usr/bin/env python3
"""Central switchboard. The repository stub registers only this script for each hook event it forwards
(UserPromptSubmit, PreToolUse, Stop). Which check scripts run for which event and
tool is decided here, from "dispatch" in config.json, so adding or removing a check never needs Step B.

Scripts run one after another with the same input. Combining their answers:
- Stop and SubagentStop: every check runs, and all block reasons go back in one message, with any notices for me
  (the session summary) kept beside them; every Stop is logged to .claude/state/dispatch.jsonl;
- other events: a block or deny (PreToolUse "permissionDecision": "deny" or "ask"; UserPromptSubmit "decision":
  "block"; exit code 2) wins at once and later scripts do not run;
- added context (UserPromptSubmit and others) from every script is joined into one answer."""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import load_config, bump_stat, log  # noqa: E402

raw = sys.stdin.buffer.read()
try:
    data = json.loads(raw or b"{}")
except ValueError:
    data = {}
event = data.get("hook_event_name", "")
tool = data.get("tool_name", "") or ""
cfg = load_config()
entries = (cfg.get("dispatch") or {}).get(event, [])

JOIN_BLOCKS = event in ("Stop", "SubagentStop")   # every check runs; all reasons go back in one message
contexts, passthrough, reasons, notes = [], None, [], []
sid = data.get("session_id")
for e in entries:
    if isinstance(e, str):
        e = {"script": e}
    pattern = e.get("tools")
    if pattern and not re.fullmatch(pattern, tool):
        continue
    path = os.path.join(HERE, e["script"])
    if not os.path.isfile(path):
        continue
    r = subprocess.run([sys.executable, "-B", path], input=raw, capture_output=True, env=os.environ)
    if r.stderr:
        sys.stderr.buffer.write(r.stderr)
    if r.returncode == 2:
        sys.exit(2)
    out = r.stdout.decode("utf-8", "replace").strip()
    if not out:
        continue
    try:
        obj = json.loads(out)
    except ValueError:
        contexts.append(out)          # plain stdout counts as added context
        continue
    hso = obj.get("hookSpecificOutput") or {}
    if obj.get("systemMessage"):
        notes.append(obj.pop("systemMessage"))   # shown to the user by Claude Code; costs no AI turn
    if JOIN_BLOCKS and obj.get("decision") == "block":
        reasons.append(obj.get("reason", "").strip())
        continue
    if obj.get("decision") == "block" or hso.get("permissionDecision") in ("deny", "ask"):
        bump_stat(sid, "refused:" + e["script"].replace(".py", ""))
        if notes:
            obj["systemMessage"] = "\n".join(notes)
        print(json.dumps(obj))
        sys.exit(0)
    if hso.get("additionalContext"):
        contexts.append(hso["additionalContext"])
    elif passthrough is None:
        passthrough = obj

if reasons:
    body = reasons[0] if len(reasons) == 1 else "Fix all of these in one reply:\n" + "\n".join(
        f"{i}. {r}" for i, r in enumerate(reasons, 1))
    bump_stat(sid, "sendbacks")
    out = {"decision": "block", "reason": body}
    # v3.1.23: a send-back keeps the notices; v3.1.24: only the version line, so the summary shows once, at the end
    notes = [n.split("\n")[0] if n.startswith("Rules v") else n for n in notes]
    if notes:
        out["systemMessage"] = "\n".join(notes)
    log("dispatch", {"event": event, "sent_back": len(reasons), "notices": len(notes)})
    print(json.dumps(out))
    sys.exit(0)
out = {}
if contexts:
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n\n".join(contexts)}}
elif passthrough is not None:
    out = passthrough
if notes:
    out["systemMessage"] = "\n".join(notes)
if event == "Stop":
    log("dispatch", {"event": event, "sent_back": 0, "notices": len(notes)})
if out:
    print(json.dumps(out))
sys.exit(0)
