#!/usr/bin/env python3
"""Remove the per-repo managed entries left by rules v2 (hooks pointing into .claude/hooks/, model fable,
plan-mode default, the managed ask/deny list). Keeps anything else the repo has; deletes the file if empty.
Usage: unmerge_settings.py <target.json> <v2-managed-settings.json>"""
import json, os, sys

target, managed_path = sys.argv[1], sys.argv[2]
try:
    s = json.load(open(target, encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
m = json.load(open(managed_path, encoding="utf-8"))
if s.get("model") == m.get("model"):
    s.pop("model")
perm = s.get("permissions", {})
if perm.get("defaultMode") == m["permissions"].get("defaultMode"):
    perm.pop("defaultMode")
for key in ("allow", "ask", "deny"):
    if key in perm:
        perm[key] = [x for x in perm[key] if x not in m["permissions"].get(key, [])]
        if not perm[key]:
            perm.pop(key)
if perm:
    s["permissions"] = perm
else:
    s.pop("permissions", None)
hooks = {}
for event, groups in s.get("hooks", {}).items():
    kept = []
    for g in groups:
        hs = [h for h in g.get("hooks", []) if ".claude/hooks/" not in h.get("command", "")]
        if hs:
            kept.append({**g, "hooks": hs})
    if kept:
        hooks[event] = kept
if hooks:
    s["hooks"] = hooks
else:
    s.pop("hooks", None)
if s:
    json.dump(s, open(target, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
else:
    os.remove(target)
