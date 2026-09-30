#!/usr/bin/env python3
"""Replace a rules-v2 CLAUDE.md with the pointer, keeping any section that is not part of the v2 rules
(for example a repo's own "## This Repository ..." section). Prints the kept headings.
Usage: split_claude_md.py <CLAUDE.md> <pointer.md>"""
import re, sys

V2_HEADINGS = {
    "My Environment", "Enforcement Layers", "Reliability and Current State", "Design Mode", "Approval and Scope",
    "Plans and Revision Colors", "Plans and Revision Markers", "Fable → Opus Routing", "Mandatory Fable → Opus Routing",
    "Execution and Records", "Verification, Completion, and Handoff", "Required Validation Line",
    "Git and File Safety", "Model Guidance Sources",
}
path, pointer = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().splitlines()
sections, current = [], None
for line in lines[1:]:                       # line 0 is "# Global Working Rules ..."
    m = re.match(r"^(#{1,2})\s+(.*)$", line)
    if m:
        heading = re.sub(r"[🟦🟩🟧🟪]\s*\*\*Rev \d+\*\*\s*", "", m.group(2)).strip()
        current = {"heading": heading, "lines": [line]}
        sections.append(current)
    elif current is not None:
        current["lines"].append(line)
kept = [s for s in sections if s["heading"] not in V2_HEADINGS]
out = open(pointer, encoding="utf-8").read().rstrip("\n") + "\n"
for s in kept:
    out += "\n" + "\n".join(s["lines"]).rstrip("\n") + "\n"
open(path, "w", encoding="utf-8").write(out)
for s in kept:
    print(s["heading"])
