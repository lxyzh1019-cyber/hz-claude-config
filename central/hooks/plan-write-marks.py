#!/usr/bin/env python3
"""PreToolUse hook on Write, Edit and MultiEdit (v3.3.3, owner 16 Oct: "C", marks before showing). When the session
writes or edits a plan file (plans/*.md with a "Plan vN" title), the plan check runs on the text the file will hold
(HZ_PLAN_PREVIEW) and the coloured Rev marks, the change list in words and the green and red lines go into that text.
The text the session sends at the showing then holds the marks, so every surface shows them and the plan check needs
no extra showing. Cause (12 Oct): the desktop app shows the text the session sends; the check used to add the marks
only at the showing. v3.3.4 (P1): an Edit or MultiEdit of a plan file is rewritten into one edit that writes the whole
marked text (16 Oct: both 3.3.3 runs changed Rev 2 with Edit, so the showing was refused once). A first showing or a
plan with nothing changed passes unchanged; the showing check stays the backup."""
import json, os, re, subprocess, sys
from _common import read_hook_input, log

data = read_hook_input()
inp = data.get("tool_input") or {}
tool = str(data.get("tool_name") or "")
path = str(inp.get("file_path") or "").replace("\\", "/")
if not (path.lower().endswith(".md") and "/plans/" in path.lower()) or os.environ.get("HZ_PLAN_WRITE_MARKS_OFF"):
    raise SystemExit(0)
current = None
if tool == "Write":
    content = inp.get("content")
else:
    try:
        current = open(inp.get("file_path"), encoding="utf-8").read()
    except (OSError, TypeError):
        raise SystemExit(0)
    content = current
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    for e in edits or []:
        o, n = str(e.get("old_string") or ""), str(e.get("new_string") or "")
        if not o or o not in content:
            raise SystemExit(0)          # the edit will fail on its own; leave it to Claude Code
        content = content.replace(o, n) if e.get("replace_all") else content.replace(o, n, 1)
if not (isinstance(content, str) and re.search(r"(?m)^#*\s*Plan v\d+", content)):
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
log("plan-write-marks", {"file": os.path.basename(path), "tool": tool, "added_chars": len(final) - len(content)})
if tool == "Write":
    new_inp = dict(inp, content=final)
else:   # one edit that replaces the whole file with the marked text
    new_inp = {"file_path": inp.get("file_path"), "old_string": current, "new_string": final, "replace_all": False}
    if tool == "MultiEdit":
        new_inp = {"file_path": inp.get("file_path"), "edits": [{"old_string": current, "new_string": final}]}
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                         "permissionDecisionReason": "plan marks added when written",
                                         "updatedInput": new_inp}}))
