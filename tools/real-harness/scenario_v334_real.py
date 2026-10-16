#!/usr/bin/env python3
"""v3.3.4: the real Claude Code program, a scripted stand-in model, the real checks as hooks.
Usage: python3 scenario_v334_real.py <central dir>   (needs CLAUDE_BIN; pexpect pyte)
  edit - P1: Rev 2 of an approved plan is changed with Edit; counts the extra showings and looks at the window
  cd   - P7: "cd <this folder>/ && git status" in the default permission mode: asked for permission, or ran"""
import sys, os, random, subprocess
sys.argv = [sys.argv[0], sys.argv[1], "none"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_v3217.py"), encoding="utf-8").read()
exec(src[src.index("import json, os, re, shutil"):src.index('if "window" in WANT:')])   # setup, Run, PLAN1, PLAN2
BASE = os.environ.get("HARNESS_DIR", "/tmp/hz-harness-334"); PORT[0] = 9000 + random.randint(0, 800)
HOOKS = {"UserPromptSubmit": None, "PreToolUse": "ExitPlanMode|AskUserQuestion|Write|Edit|MultiEdit|Bash"}
REV2_SAME = PLAN1.replace("# Plan v1 — Test — Approved", "# Plan v1 Rev 2 — Test — Awaiting approval")


def extra(tr):
    return len({b.get("tool_use_id") for x in tr for b in (((x.get("message") or {}).get("content")) or [])
                if isinstance(b, dict) and b.get("type") == "tool_result" and "show the plan again" in json.dumps(b.get("content"))})


for label, env_extra in (() if os.environ.get("ONLY_CD") else (("edit-before", {"HZ_PLAN_WRITE_MARKS_OFF": "1"}), ("edit-334", None))):
    B = setup(label, dispatch_hooks(HOOKS), {"plans/test-v1.md": PLAN1})
    r = Run(B, [{"text": "Writing.", "tools": [{"id": "w1", "name": "Write", "input": {"file_path": "PLANPATH", "content": REV2_SAME}}]},
                {"text": "Changing.", "tools": [{"id": "e1", "name": "Edit", "input": {"file_path": "PLANPATH",
                 "old_string": "- Stage 2: LINE-B.", "new_string": "- Stage 2: LINE-B, now green."}}]},
                {"text": "Here is Rev 2.", "tools": [{"id": "p1", "name": "ExitPlanMode", "input": {}}]},
                {"text": "Showing again.", "tools": [{"id": "p2", "name": "ExitPlanMode", "input": {}}]},
                {"text": "END"}], env_extra=env_extra)
    s = r.type("change stage 2", 30)
    tr = r.transcript(); r.close()
    n = extra(tr)
    print(f"      {label}: extra showings = {n}")
    if label == "edit-before":
        say("edit, 3.3.3 way: a plan changed with Edit costs one extra showing", n == 1, s[-300:])
    else:
        say("edit, 3.3.4: no extra showing", n == 0, s[-300:])
        say("edit, 3.3.4: the window shows the coloured Rev 2 line and waits for me",
            re.search(r"Rev 2\*{0,2} — Stage 2: LINE-B, now green", s) and "Would you like to proceed?" in s, s[-800:])

for label, env_extra in (("cd-before", {"HZ_CD_GIT_OFF": "1"}), ("cd-334", None)):
    # the real cause (16 Oct): an earlier "cd scripts" for the tests moved the shell's folder; the later
    # "cd <repo> && git ..." then made Claude Code ask. 3.3.4 refuses that step once; the session moves back alone.
    B = setup(label, dispatch_hooks(HOOKS), {"scripts/x.txt": "x"})
    root = f"{B}/proj"
    r = Run(B, [{"text": "Tests.", "tools": [{"id": "c1", "name": "Bash", "input": {"command": "cd scripts", "description": "tests folder"}}]},
                {"text": "Commit.", "tools": [{"id": "c2", "name": "Bash", "input": {"command": f'cd "{root}" && git status --short', "description": "status"}}]},
                {"text": "Back first.", "tools": [{"id": "c3", "name": "Bash", "input": {"command": f'cd "{root}"', "description": "back"}}]},
                {"text": "Now git.", "tools": [{"id": "c4", "name": "Bash", "input": {"command": "git status --short", "description": "status"}}]},
                {"text": "END"}], mode="default", env_extra=env_extra)
    s = r.type("commit it", 25)
    asked = "changes directory before running a version-control command" in s or "Do you want to proceed" in s
    if asked:
        s = r.key("\x1b", 5)
    r.close()
    print(f"      {label}: permission asked = {asked}")
    if label == "cd-before":
        say("cd, 3.3.3 way: after 'cd scripts', 'cd <repo> && git status' asks me for permission", asked, s[-400:])
    else:
        say("cd, 3.3.4: refused once, the session moves back alone, git runs, no permission question",
            not asked and "END" in r.all, s[-400:])
print(f"\n{sum(ok_all)} of {len(ok_all)} passed")
