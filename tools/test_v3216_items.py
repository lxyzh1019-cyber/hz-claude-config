#!/usr/bin/env python3
"""v3.2.16 item test. Usage: python3 tools/test_v3216_items.py <repo dir> [session folder for the scorecard]
Items: 1 one pull request per stop · 2 only necessary stops (rules, planner, soft plan notice, scorecard) · 3 setup commits
carry [skip ci] (the real-program proof is tools/real-harness/scenario_setup_update.sh)."""
import json, os, subprocess, sys, tempfile, shutil
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    ok = bool(ok); results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""
RULES = read(C, "rules", "CLAUDE-rules.md"); PLANNER = read(C, "agents", "planner-instructions.md")
res(1, "rules: one pull request per stop, a separate one only for a stated reason", "**One pull request per stop.**" in RULES, "")
res(1, "planner: group every Part that reaches the owner at the same stop", "One pull request per stop (v3.2.16)" in PLANNER, "")
res(2, "rules: only necessary stops, each with its reason", "**Only necessary stops.**" in RULES and "stop: decision" in RULES, "")
res(2, "planner: only necessary stops", "Stops (v3.2.16)" in PLANNER, "")
P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); subprocess.run("git init -q", shell=True, cwd=P)
plan = ("# Plan v12 — Pass — Awaiting approval\n\n**Quick read** · 40 words · about 1 min\n\n**Summary**\n- Goal: kit.\n- Done: 2 of 6.\n- I need from you: approve.\n\n"
        "**What changed since v11**\n- Fewer stops.\n\n**Decisions:** None open.\n\n**Next steps**\n- Stage 3.\n\nStages to finish\n4 stages: 2 builds and 2 checks by you.\n"
        "3. Kit 1.1 · Claude · Build · proof: tests green · size: S\n4. iPad read and merge Kit 1.1 · You · Check · stop: merge\n5. Part 11 · Claude · Build · proof: tests green · size: S\n6. Look at the Part 11 page · You · Check\n\nTechnical details\n- none\n")
e = dict(os.environ, CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1", HZ_PLAN_ROUNDS_OFF="1", HZ_PLANNER_CHECK_OFF="1")
o = subprocess.run(["python3", os.path.join(H, "plan-guard.py")], input=json.dumps({"tool_name": "ExitPlanMode", "session_id": "x", "tool_input": {"plan": plan}}),
                   capture_output=True, text=True, env=e, cwd=P).stdout
res(2, "a stop row with no reason gets a notice (not a send-back)", "[stops]" in o and "Look at the Part 11 page" in o and '"deny"' not in o, o[:300])
res(2, "  ...a stop row with its reason is not named", "iPad read and merge Kit 1.1" not in o.split("No reason yet:")[-1] if "No reason yet:" in o else False, o[-200:])
ses = sys.argv[2] if len(sys.argv) > 2 else ""
if ses:
    sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", ses], capture_output=True, text=True).stdout
    res(2, "the scorecard counts stops and pull requests per merge stop", "Stops for you" in sc and "Pull requests per merge stop" in sc, sc[:300])
su = read(H, "stubupdate.py")
res(3, "the automatic setup commit message carries [skip ci]", "[skip ci] The hook list changes only .claude/" in su, "")
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
