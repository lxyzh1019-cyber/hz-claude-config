#!/usr/bin/env python3
"""Merge the shared settings.json into an app repo's settings.json.
- model: the stub no longer sets one (the account default applies). A model an older stub set — "opus" or
  "fable" — is removed; any other value, which only the user can have chosen, is kept
- permissions.defaultMode: shared wins
- permissions.allow/ask/deny: union (existing order kept, shared entries appended)
- hooks: entries whose command contains the managed marker (default .claude/hooks/) are managed and replaced by the shared set;
  any other hook entries the repo has are kept
- any other keys: existing kept; shared keys added if missing
Usage: merge_settings.py <shared.json> <target.json> [managed-hook-marker]"""
import json, os, sys

shared_path, target_path = sys.argv[1], sys.argv[2]
shared = json.load(open(shared_path, encoding="utf-8"))
try:
    target = json.load(open(target_path, encoding="utf-8"))
except (OSError, ValueError):
    target = {}

MANAGED = sys.argv[3] if len(sys.argv) > 3 else ".claude/hooks/"
out = dict(target)
for k, v in shared.items():
    if k not in ("permissions", "hooks"):
        out[k] = v if k == "model" or k not in target else target[k]

STUB_SET_MODELS = ("opus", "fable")
if "model" not in shared and out.get("model") in STUB_SET_MODELS:
    out.pop("model")
# v3.1.16: the stub no longer sets an advisor; remove the one an older stub set, keep any other value
if "advisorModel" not in shared and out.get("advisorModel") == "fable":
    out.pop("advisorModel")

perm = dict(target.get("permissions", {}))
sp = shared.get("permissions", {})
if "defaultMode" in sp:
    perm["defaultMode"] = sp["defaultMode"]
for key in ("allow", "ask", "deny"):
    merged = list(perm.get(key, []))
    merged += [x for x in sp.get(key, []) if x not in merged]
    if merged:
        perm[key] = merged
out["permissions"] = perm

hooks = {}
for event, groups in target.get("hooks", {}).items():
    kept = []
    for g in groups:
        hs = [h for h in g.get("hooks", []) if MANAGED not in h.get("command", "")]
        if hs:
            kept.append({**g, "hooks": hs})
    if kept:
        hooks[event] = kept
for event, groups in shared.get("hooks", {}).items():
    hooks.setdefault(event, []).extend(groups)
out["hooks"] = hooks

os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
with open(target_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
    f.write("\n")
