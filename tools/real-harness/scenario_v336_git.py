#!/usr/bin/env python3
"""v3.3.6 (G1): the real Claude Code program, a scripted stand-in model, the real checks as hooks. On a work branch the
session runs "git add … && git commit … && git push" (to a local bare origin). Default permission mode: does Claude Code
ask me? Usage: python3 scenario_v336_git.py <central dir>   (needs CLAUDE_BIN; pexpect pyte)"""
import sys, os, random, subprocess
sys.argv = [sys.argv[0], sys.argv[1], "none"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_v3217.py"), encoding="utf-8").read()
exec(src[src.index("import json, os, re, shutil"):src.index('if "window" in WANT:')])
BASE = os.environ.get("HARNESS_DIR", "/tmp/hz-harness-336"); PORT[0] = 9000 + random.randint(0, 800)
for label, env_extra in (("git-before", {"HZ_GIT_ALLOW_OFF": "1"}), ("git-336", None)):
    B = setup(label, dispatch_hooks({"UserPromptSubmit": None, "PreToolUse": "Bash"}), {"a.txt": "x"})
    subprocess.run(f"git config user.email t@t && git config user.name t && git init -q --bare {B}/origin.git && git remote add origin {B}/origin.git && git push -q origin HEAD:main "
                   "&& git switch -qc Test-336 && echo y >> a.txt", shell=True, cwd=B + "/proj")
    cmd = 'git add a.txt && git commit -q -m "Build: one line" && git push -q -u origin Test-336'
    r = Run(B, [{"text": "Commit.", "tools": [{"id": "g1", "name": "Bash", "input": {"command": cmd, "description": "commit and push"}}]},
                {"text": "END"}], mode="default", env_extra=env_extra)
    s = r.type("commit and push", 25)
    asked = "Do you want to proceed" in s or "Allow" in s and "Deny" in s or "requires approval" in r.all
    if asked:
        s = r.key("\x1b", 5)
    r.close()
    pushed = "Test-336" in subprocess.run(["git", "branch"], cwd=B + "/origin.git", capture_output=True, text=True).stdout
    print(f"      {label}: permission asked = {asked} · pushed = {pushed}")
    if label == "git-before":
        say("git, 3.3.5 way: add + commit + push on the work branch asks me", asked, s[-400:])
    else:
        say("git, 3.3.6: approved by the check, no question, the branch is pushed", not asked and pushed, s[-400:])
print(f"\n{sum(ok_all)} of {len(ok_all)} passed")
