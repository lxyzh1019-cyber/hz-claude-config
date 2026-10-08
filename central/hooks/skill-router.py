#!/usr/bin/env python3
"""UserPromptSubmit hook: deterministic skill invocation from keyword rules in skill-router.json."""
import json, os, re, sys
from _common import read_hook_input, add_context, log, HOOK_DIR, SKILLS_DIR, is_notice_text

RULES = os.path.join(HOOK_DIR, "skill-router.json")
data = read_hook_input()
prompt = (data.get("prompt") or "")
low = prompt.lower()
if is_notice_text(prompt):   # v3.1.30: a notice, not a request (v3.2.5: also a helper's hand-back message)
    sys.exit(0)
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
def describe(name):
    """Bundled central skill: point at its file in the loader cache. Otherwise: an account skill."""
    path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if os.path.isfile(path):
        return f"`{name}` — read {path}"
    return f"`{prefix}{name}`"
lines = [f"- Use skill {describe(s)}" + (f" ({n})" if n else "") for s, n in hits]
add_context("UserPromptSubmit", "[skill-router] Matched skills for this prompt:\n" + "\n".join(lines) +
            "\nIf a matched skill does not fit, say why in one line rather than silently skipping it.")
