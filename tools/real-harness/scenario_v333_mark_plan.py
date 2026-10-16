#!/usr/bin/env python3
"""v3.3.3 ("C", owner 16 Oct): marks before showing, in the real Claude Code program with a scripted stand-in model
and the real checks as hooks. Usage: python3 scenario_v333_mark_plan.py <central dir>   (needs CLAUDE_BIN; pexpect pyte)
Rev 2 of an approved Plan v1: the session writes the plan file with Write and shows it.
  before - HZ_PLAN_WRITE_MARKS_OFF=1 (3.3.3 as uploaded): the check asks for one extra showing
  C      - the marks go into the text when it is written: the first showing holds them and passes
Prints PASS/FAIL lines and the number of extra showings asked for in each run."""
import sys, os, random
sys.argv = [sys.argv[0], sys.argv[1], "none"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenario_v3217.py"), encoding="utf-8").read()
exec(src[src.index("import json, os, re, shutil"):src.index('if "window" in WANT:')])   # setup, Run, PLAN1, PLAN2
BASE = os.environ.get("HARNESS_DIR", "/tmp/hz-harness-333mp"); PORT[0] = 9000 + random.randint(0, 800)


def run(label, env_extra=None):
    B = setup(label, dispatch_hooks({"UserPromptSubmit": None, "PreToolUse": "ExitPlanMode|AskUserQuestion|Write|Edit"}),
              {"plans/test-v1.md": PLAN1})
    r = Run(B, [{"text": "Writing.", "tools": [{"id": "w1", "name": "Write", "input": {"file_path": "PLANPATH", "content": PLAN2}}]},
                {"text": "Here is Rev 2.", "tools": [{"id": "p1", "name": "ExitPlanMode", "input": {}}]},
                {"text": "Showing the marked plan.", "tools": [{"id": "p2", "name": "ExitPlanMode", "input": {}}]},
                {"text": "Showing it a third time.", "tools": [{"id": "p3", "name": "ExitPlanMode", "input": {}}]},
                {"text": "END"}], env_extra=env_extra)
    s = r.type("show me the change as a Rev", 30)
    for _ in range(3):
        if "Enter to continue" in s:
            s = r.key("\r", 12)
    tr = r.transcript(); r.close()
    asks = len({b.get("tool_use_id") for x in tr for b in (((x.get("message") or {}).get("content")) or [])
                if isinstance(b, dict) and b.get("type") == "tool_result" and "show the plan again" in json.dumps(b.get("content"))})
    written = [x.get("toolUseResult") for x in tr if isinstance(x.get("toolUseResult"), dict) and "content" in x["toolUseResult"]]
    return s, asks, written


s, asks, _ = run("before", {"HZ_PLAN_WRITE_MARKS_OFF": "1"})
print(f"      before: extra showings asked for = {asks}")
say("before: the plan written as is costs one extra showing", asks == 1, s[-300:])
s, asks, written = run("C")
print(f"      C: extra showings asked for = {asks}")
say("C: the plan file was written with the marks", written and "🟩" in str(written[-1].get("content")), str(written)[:300])
say("C: the first showing passes: no extra showing", asks == 0, s[-300:])
say("C: the window shows the coloured Rev 2 mark and waits for the owner",
    re.search(r"Rev 2\*{0,2} — Stage 2: LINE-B, now green", s) and "Would you like to proceed?" in s, s[-800:])
print(f"\n{sum(ok_all)} of {len(ok_all)} passed")
