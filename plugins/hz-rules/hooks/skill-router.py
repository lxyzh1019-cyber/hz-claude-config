#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministic skill invocation from keyword rules in skill-router.json."""
import json, os, re, sys
from _common import read_hook_input, add_context, log, HOOK_DIR, PLUGIN_ROOT, PLUGIN_MODE

RULES = os.path.join(HOOK_DIR, "skill-router.json")
data = read_hook_input()
prompt = (data.get("prompt") or "")
low = prompt.lower()
try:
    rules = json.load(open(RULES, encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
hits = []
for skill, spec in rules.get("skills", {}).items():
    if any(k.lower() in low for k in spec.get("keywords", [])) or \
       any(re.search(p, prompt, re.I) for p in spec.get("patterns", [])):
        hits.append((skill, spec.get("note", "")))
if not hits:
    sys.exit(0)
log("skill-router", {"hits": [h[0] for h in hits]})
prefix = rules.get("account_skill_prefix", "")
def resolve(name):
    # bundled skill: namespaced when running as a plugin, bare when installed into ~/.claude/skills (cloud)
    if os.path.isdir(os.path.join(PLUGIN_ROOT, "skills", name)):
        return ("hz-rules:" + name) if PLUGIN_MODE else name
    return prefix + name
lines = [f"- Invoke skill `{resolve(s)}`" + (f" — {n}" if n else "") for s, n in hits]
add_context("UserPromptSubmit", "[skill-router] Matched skills for this prompt:\n" + "\n".join(lines) +
            "\nIf a matched skill does not fit, say why in one line rather than silently skipping it.")
