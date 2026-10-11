#!/usr/bin/env python3
"""v3.2.14 item test, the same checks on any rules version. Usage: python3 tools/test_v3214_items.py <repo dir>
Items: 1 workers run in the foreground (the call is rewritten; the switchboard keeps the rewrite next to notices; no wait
line for workers) · 2 the live scorecard in the end report. The real-program proof is
tools/real-harness/scenario_wakeups.sh (3.2.13: 3 replies; 3.2.14: 1)."""
import json, os, subprocess, sys, tempfile, shutil
R = os.path.abspath(sys.argv[1]); H = os.path.join(R, "central", "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); subprocess.run("git init -q", shell=True, cwd=P)
T0 = os.path.join(V, "e.jsonl"); open(T0, "w").write(json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}) + "\n")
call = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "f", "transcript_path": T0, "tool_use_id": "x",
        "tool_input": {"subagent_type": "sonnet-worker", "run_in_background": True, "prompt": "Task: Stage 1 — Part 9\nLevel: Routine\nMap: not needed - t\nSize: S"}}
env = dict(os.environ, CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1", HZ_STAGE_TAGS_OFF="1", HZ_PLANNER_CHECK_OFF="1")
o = subprocess.run(["python3", os.path.join(H, "dispatch.py")], input=json.dumps(call), capture_output=True, text=True, env=env, cwd=P).stdout
try:
    hso = json.loads(o or "{}").get("hookSpecificOutput") or {}
except ValueError:
    hso = {}
res(1, "a main-session worker call comes out of the switchboard rewritten to the foreground",
    (hso.get("updatedInput") or {}).get("run_in_background") is False, o[:200])
res(1, "  ...and is allowed, with the rest of the call unchanged",
    hso.get("permissionDecision") == "allow" and (hso.get("updatedInput") or {}).get("subagent_type") == "sonnet-worker", o[:200])
res(1, "  ...with no '⏳ Working on' instruction for it", "Working on" not in o, o[:200])
call2 = dict(call, agent_id="w9")
o2 = subprocess.run(["python3", os.path.join(H, "dispatch.py")], input=json.dumps(call2), capture_output=True, text=True, env=env, cwd=P).stdout
res(1, "a worker's own helper call is left as it is", "updatedInput" not in o2, o2[:200])
o3 = subprocess.run(["python3", os.path.join(H, "dispatch.py")], input=json.dumps(call), capture_output=True, text=True,
                    env=dict(env, HZ_BACKGROUND_WORKERS="1"), cwd=P).stdout
res(1, "HZ_BACKGROUND_WORKERS=1 keeps background workers", "updatedInput" not in o3, o3[:200])
sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", T0], capture_output=True, text=True, env=env).stdout
res(2, "the end report has the live scorecard", "⏳ lines per round" in sc and "Sonnet share" in sc and "Report link" in sc, sc[:200])
# 3 Complex needs a reason
open(os.path.join(P, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "cx", "n": 4}))
def hv(prompt, sid="cx"):
    c = dict(call, session_id=sid, tool_input={"subagent_type": "opus-worker", "prompt": prompt})
    return subprocess.run(["python3", os.path.join(H, "worker-guard.py")], input=json.dumps(c), capture_output=True, text=True, env=env, cwd=P).stdout
base = "Task: Stage 32 — Part 6 words and numbers\nLevel: Complex\nMap: not needed - t\nSize: M\n"
o1 = hv(base); o2 = hv(base)
res(3, "a Complex hand-over without a reason is refused once, with the Routine way out", '"deny"' in o1 and "Complex because:" in o1 and "Routine" in o1, o1[:200])
res(3, "  ...the second try passes (never loops)", '"deny"' not in o2, o2[:200])
o3 = hv(base + "Complex because: unknown cause of the failing sync\n", "cx2")
res(3, "a Complex hand-over with its reason passes", '"deny"' not in o3, o3[:200])
# 4 the main session waits for GitHub in the foreground
gw = lambda bg, extra={}: subprocess.run(["python3", os.path.join(H, "wait-guard.py")], input=json.dumps(dict({"tool_name": "Bash", "session_id": "gw",
         "tool_input": {"command": "timeout 600 gh run watch 5 --exit-status", "run_in_background": bg}}, **extra)), capture_output=True, text=True, env=env, cwd=P).stdout
open(os.path.join(P, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "gw", "n": 2}))
res(4, "the main session may wait for GitHub in the foreground", '"deny"' not in gw(False), gw(False)[:200])
o = gw(True)
res(4, "a background GitHub watch by the main session is refused once, with the foreground fix", '"deny"' in o and "in the foreground" in o, o[:200])
res(4, "  ...the second try passes", '"deny"' not in gw(True), "")
# 5 report: GitHub waits only while nothing else runs; parallel pairs once
import datetime as _dt
S = os.path.join(V, "s"); os.makedirs(os.path.join(S, "m", "subagents"))
ts = lambda mi: (_dt.datetime(2026, 10, 10, 19, 0, tzinfo=_dt.timezone.utc) + _dt.timedelta(minutes=mi)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
def jl(path, rows): open(path, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
jl(os.path.join(S, "m.jsonl"), [{"type": "user", "timestamp": ts(0), "message": {"role": "user", "content": "Continue Pass plan on branch x"}},
    {"type": "assistant", "timestamp": ts(1), "message": {"id": "a1", "role": "assistant", "content": [{"type": "tool_use", "id": "toolu_g1", "name": "Bash", "input": {"command": "timeout 1800 gh run watch 5", "run_in_background": True}}]}},
    {"type": "user", "timestamp": ts(1), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_g1", "content": "started"}]}},
    {"type": "user", "timestamp": ts(21), "message": {"role": "user", "content": "<task-notification><tool-use-id>toolu_g1</tool-use-id></task-notification>"}},
    {"type": "assistant", "timestamp": ts(60), "message": {"id": "a2", "role": "assistant", "content": [{"type": "text", "text": "done"}]}}])
def helper(n, stage, a, b, f):
    jl(os.path.join(S, "m", "subagents", f"agent-h{n}.jsonl"), [{"type": "user", "timestamp": ts(a), "message": {"role": "user", "content": f"Task: Stage {stage} of 9 — x"}},
       {"type": "assistant", "timestamp": ts(b), "message": {"id": f"h{n}", "role": "assistant", "content": [{"type": "tool_use", "id": f"w{n}", "name": "Edit", "input": {"file_path": "D:/r/" + f}}]}}])
helper(1, 32, 2, 16, "a.js"); helper(2, 33, 22, 30, "b.js"); helper(3, 32, 31, 35, "c.js"); helper(4, 33, 36, 40, "d.js")
rep = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "Pass plan", "--dir", S], capture_output=True, text=True, env=env).stdout
res(5, "a GitHub wait counts only while no helper runs (20 min wait, 14 min of it beside a helper: 6 min)", "**waiting for GitHub**: 6 min" in rep, rep[:500])
res(5, "each parallel pair is listed once", rep.count("Stages 32 and 33") == 1 and "Stages 33 and 32" not in rep, rep[rep.find("Parallel"):][:300])
# 7 report delivery by content
A = os.path.join(V, "app"); os.makedirs(os.path.join(A, "docs", "reports")); os.makedirs(os.path.join(A, ".claude", "state"))
subprocess.run("git init -q", shell=True, cwd=A)
open(os.path.join(A, "docs", "reports", "pass-checkpoint-1.md"), "w").write("# r1")
TR = os.path.join(V, "t.jsonl"); jl(TR, [{"type": "user", "message": {"role": "user", "content": "go"}}, {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Work goes on.\nConfidence: High · Status: Checked"}]}}])
rd = lambda: subprocess.run(["python3", os.path.join(H, "report-delivery.py")], input=json.dumps({"transcript_path": TR, "session_id": "rd"}), capture_output=True, text=True, env=dict(env, CLAUDE_PROJECT_DIR=A), cwd=A).stdout
rd(); import time as _tm; _tm.sleep(1.1); os.utime(os.path.join(A, "docs", "reports", "pass-checkpoint-1.md"))
o = rd()
res(7, "the same report with a new file date is not reported as undelivered", o.strip() == "", o[:200])
# 8 restart line: go on at once
pg = subprocess.run(["python3", os.path.join(H, "plan-gate.py")], input=json.dumps({"prompt": "Continue Pass plan on branch main; next: Stage 3 of 9 — Part 6.", "session_id": "rs"}),
                    capture_output=True, text=True, env=env, cwd=P).stdout
res(8, "after a restart line the session starts the next stage at once", "start that stage at once" in pg and "Wait for my OK" not in pg, pg[:300])
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
