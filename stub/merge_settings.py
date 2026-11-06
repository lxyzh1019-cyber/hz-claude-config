#!/usr/bin/env python3
"""Merge the shared settings.json into an app repo's settings.json.
- model: the stub no longer sets one (the account default applies). A model an older stub set — "opus" or
  "fable" — is removed; any other value, which only the user can have chosen, is kept
- permissions.defaultMode: shared wins
- permissions.allow/ask/deny: union (existing order kept, shared entries appended)
- v3.3.7: after the union, every "ask" entry listed in retired-permissions.json (next to this script; a built-in copy
  when the file is missing) is removed, except the deploy asks (owner: keep deploy asks). An ask rule makes Claude Code
  ask even when an allow rule matches, also in auto mode (Builds 2-4: 10 git questions). "deny" is never touched.
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
# v3.3.7 (X48 G1 reopened): remove the retired ask rules; keep the deploy asks
RETIRED_ASK = ["Bash(git commit:*)", "Bash(git push:*)", "Bash(git merge:*)", "Bash(gh pr merge:*)"]
KEEP_ASK = ("Bash(firebase deploy:*)", "Bash(npm run deploy:*)")
try:
    RETIRED_ASK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "retired-permissions.json"),
                                 encoding="utf-8")).get("ask", RETIRED_ASK)
except (OSError, ValueError, AttributeError):
    pass
if perm.get("ask"):
    perm["ask"] = [x for x in perm["ask"] if x in KEEP_ASK or x not in RETIRED_ASK]
    if not perm["ask"]:
        perm.pop("ask")
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
