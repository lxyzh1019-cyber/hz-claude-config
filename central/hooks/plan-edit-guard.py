#!/usr/bin/env python3
"""PreToolUse hook on Edit/Write/MultiEdit (v3.2.0): an approved plan file is not edited. A change after my Approve
is the next Plan vN, shown in plan mode. Allowed: edits to plans not yet approved, an edit that moves the file to a
higher version number, and an edit that changes only the title's approval words.
Cause: in the Weekly-Planner consistency pass the session wrote three decisions into the approved Plan v1 file
directly, so no new version and no change view followed."""
import os
from _common import (read_hook_input, deny_tool, log, read_transcript, plan_store_load, plan_mark_approved,
                     plan_norm, plan_version_of, plan_name_of, live_proof)
from planmarks import strip_marks as strip_change_block

data = read_hook_input()
inp = data.get("tool_input") or {}
path = str(inp.get("file_path") or "")
if not (path.replace("\\", "/").lower().endswith(".md") and "/plans/" in path.replace("\\", "/").lower()) \
        or not os.path.isfile(path):
    raise SystemExit(0)
try:
    old = open(path, encoding="utf-8", errors="replace").read()
except OSError:
    raise SystemExit(0)
ver, name = plan_version_of(old), plan_name_of(old)
if ver is None or not name:
    raise SystemExit(0)
store = plan_mark_approved(plan_store_load(), read_transcript(data.get("transcript_path")))
entry = store["plans"].get(name) or {}
if not (entry.get("approved") and entry.get("version") == ver):
    raise SystemExit(0)
new = old
if data.get("tool_name") == "Write" and "content" in inp:
    new = str(inp.get("content") or "")
else:
    for e in (inp.get("edits") if isinstance(inp.get("edits"), list) else [inp]):
        a, b = str(e.get("old_string") or ""), str(e.get("new_string") or "")
        if a:
            new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
nv = plan_version_of(new)
if nv is not None and nv > ver:
    raise SystemExit(0)
if plan_norm(strip_change_block(new)) == plan_norm(strip_change_block(old)):
    raise SystemExit(0)
log("plan-edit-guard", {"refused": os.path.basename(path), "version": ver})
live_proof("plan-edit-guard", {"refused": os.path.basename(path), "version": ver})
deny_tool(f"Plan v{ver} is approved. Do not edit its file. Change the title to Plan v{ver + 1}, make the change, and "
          "show it in plan mode for my Approve. The plan check adds the coloured marks by itself.")
