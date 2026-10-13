#!/usr/bin/env python3
"""PreToolUse (Bash), v3.1.26: a shell command that only reads the local copy of the central rules (the hz-rules
cache: rules, worker instructions, skills) is refused before Claude Code shows an "Allow…?" prompt, with the exact
path to read with the Read tool instead (the stub allows Read on that folder without a prompt)."""
import re
from _common import read_hook_input, deny_tool, SKILLS_DIR, RULES_PATH

data = read_hook_input()
cmd = str((data.get("tool_input") or {}).get("command") or "")
if re.search(r"\bpython[0-9.]*(\.exe)?\b[^|;&]*(plan_report|change_list)\.py", cmd):
    raise SystemExit(0)   # v3.2.15: running the report tool is not reading the rules (10-11 Oct: 13 refusals, no measured part)
# v3.3.0: a read-only command on the rules folder is allowed without a prompt instead of refused (17 refusals, 11-12 Oct)
if "hz-rules" in cmd and re.search(r"(^|[\s;&|(])(cat|head|tail|sed|less|more|type|Get-Content|awk|grep)\b", cmd) \
        and not re.search(r">|\bsed\s+-i|\btee\b|\brm\b|\bmv\b|\bcp\b|\bchmod\b|`|\$\(|\bgit\s+(pull|push|commit|add|checkout|reset|merge|rebase|switch)\b",
                          re.sub(r"\d?>\s*/dev/null|2>&1", "", cmd)):   # v3.3.0: error redirections are read-only too
    import json as _j
    print(_j.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                           "permissionDecisionReason": "read-only command on the central rules"}}))
    raise SystemExit(0)
if "hz-rules" in cmd and re.search(r"(^|[\s;&|(])(cat|head|tail|sed|less|more|type|Get-Content|awk|grep)\b", cmd):
    want = re.search(r"skills/([\w.-]+)/SKILL\.md", cmd)
    path = f"{SKILLS_DIR}/{want.group(1)}/SKILL.md" if want else (SKILLS_DIR if "skills" in cmd else RULES_PATH)
    deny_tool(f"Read the central rules with the Read tool, not a shell command (that asks the user for permission): "
              f"read {path}")
