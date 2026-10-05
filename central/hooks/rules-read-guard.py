#!/usr/bin/env python3
"""PreToolUse (Bash), v3.1.26: a shell command that only reads the local copy of the central rules (the hz-rules
cache: rules, worker instructions, skills) is refused before Claude Code shows an "Allow…?" prompt, with the exact
path to read with the Read tool instead (the stub allows Read on that folder without a prompt)."""
import re
from _common import read_hook_input, deny_tool, SKILLS_DIR, RULES_PATH

data = read_hook_input()
cmd = str((data.get("tool_input") or {}).get("command") or "")
if "hz-rules" in cmd and re.search(r"(^|[\s;&|(])(cat|head|tail|sed|less|more|type|Get-Content|awk|grep)\b", cmd):
    want = re.search(r"skills/([\w.-]+)/SKILL\.md", cmd)
    path = f"{SKILLS_DIR}/{want.group(1)}/SKILL.md" if want else (SKILLS_DIR if "skills" in cmd else RULES_PATH)
    deny_tool(f"Read the central rules with the Read tool, not a shell command (that asks the user for permission): "
              f"read {path}")
