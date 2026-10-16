#!/usr/bin/env python3
"""PreToolUse hook on Write (v3.3.3, owner 16 Oct: "C", marks before showing). When the session writes a plan file
(plans/*.md with a "Plan vN" title), the plan check runs on the text about to be written (HZ_PLAN_PREVIEW) and the
coloured Rev marks, the change list in words and the green and red lines go into that text. The text the session
sends at the showing then holds the marks, so every surface shows them and the plan check needs no extra showing.
Cause (12 Oct): the desktop app shows the text the session sends; the check used to add the marks only at the showing.
A first showing, a plan with nothing changed, or an Edit of the plan file passes unchanged (the showing check stays
the backup)."""
import json, os, re, subprocess, sys
from _common import read_hook_input, log

data = read_hook_input()
inp = data.get("tool_input") or {}
path = str(inp.get("file_path") or "").replace("\\", "/")
content = inp.get("content")
if not (isinstance(content, str) and path.lower().endswith(".md") and "/plans/" in path.lower()
        and re.search(r"(?m)^#*\s*Plan v\d+", content)) or os.environ.get("HZ_PLAN_WRITE_MARKS_OFF"):
    raise SystemExit(0)
here = os.path.dirname(os.path.abspath(__file__))
probe = dict(data, hook_event_name="PreToolUse", tool_name="ExitPlanMode",
             tool_input={"plan": content, "planFilePath": inp.get("file_path")})
r = subprocess.run([sys.executable, "-B", os.path.join(here, "plan-guard.py")], input=json.dumps(probe), capture_output=True,
                   text=True, encoding="utf-8", env=dict(os.environ, HZ_PLAN_PREVIEW="1"))
final = None
for line in (r.stdout or "").splitlines():
    try:
        final = json.loads(line).get("hz_preview_final", final)
    except ValueError:
        continue
if not final or final == content:
    raise SystemExit(0)
log("plan-write-marks", {"file": os.path.basename(path), "added_chars": len(final) - len(content)})
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                         "permissionDecisionReason": "plan marks added when written",
                                         "updatedInput": dict(inp, content=final)}}))
