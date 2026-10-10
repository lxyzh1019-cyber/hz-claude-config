#!/usr/bin/env python3
"""v3.2.11 item test: the problems found in the Weekly-Planner sessions of 9 and 10 Oct, each tested the same way on any
rules version. Usage: python3 tools/test_v3211_items.py <central dir>
Items: 1 Routine = known answer · 2 short test output · 4 lanes without a fixed cap · 5 workers test in the foreground,
no repeated ⏳ line, ✅ line · 6 Sonnet's named change in .github/ · 7 plan check (Quick read, quoted finds) · 8 token
report (reading apart from planning, real helper totals) · 9 report link in the Completion lines. Item 3 (hand-back at
150 k) is not built: see the record."""
import json, os, subprocess, sys, tempfile, shutil, datetime as dt
C = os.path.abspath(sys.argv[1]); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
def run(script, inp, proj, **env):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1",
             HZ_STAGE_TAGS_OFF="1", HZ_PLANNER_CHECK_OFF="1", HZ_QUESTIONS_CHECK_OFF="1", HZ_PLAN_ROUNDS_OFF="1"); e.update(env)
    for k in [k for k, v in e.items() if v is None]:
        e.pop(k)
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=proj).stdout
def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""
def sh(cmd, cwd): subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True)
def jl(path, rows): open(path, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); sh("git init -q", P)
RULES = read(C, "rules", "CLAUDE-rules.md"); WORKER = read(C, "agents", "opus-worker-instructions.md")
T0 = os.path.join(V, "empty.jsonl"); jl(T0, [{"type": "user", "message": {"role": "user", "content": "go"}}])
def hand(prompt, sub="sonnet-worker", tp=T0, sid="h"):
    return run("worker-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": sid, "tool_use_id": "tnew",
                                   "transcript_path": tp, "tool_input": {"subagent_type": sub, "prompt": prompt}}, P)
# 1 Routine = known answer
o = hand("Task: PR 7 Today\nLevel: Routine\nSize: M\nMove the Today screen to the .ui-* classes from the exact table: a refactor with a known answer. Delete the old classes.")
res(1, "a known-answer refactor goes to Sonnet (the word 'refactor' no longer refuses it)", '"deny"' not in o, o)
o = hand("Task: x\nSize: S\nfix it")
res(1, "the hand-over check explains Routine by 'must the worker find or decide something?'", "find or decide" in o, o)
# 2 short test output
res(2, "worker role file: summary only (tail -20), full output only on failure", "tail -20" in WORKER, "")
# 4 lanes
three = os.path.join(V, "par3.jsonl")
jl(three, [{"type": "user", "message": {"role": "user", "content": "go"}}] + [{"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": f"w{i}", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: s\nLevel: Complex"}}]}} for i in range(3)])
o = hand("Task: stage D\nLevel: Complex\nMap: not needed - t\nSize: M\nWorktree: ../app-d\nFiles: d.js\nGroup: A", "opus-worker", three)
res(4, "a fourth lane may start when it names its own files", '"deny"' not in o, o)
o = hand("Task: stage E\nLevel: Complex\nMap: not needed - t\nSize: M\nWorktree: ../app-e\nGroup: A", "opus-worker", three)
res(4, "a lane without 'Files:' is refused while others run", '"deny"' in o and "Files:" in o, o)
six = os.path.join(V, "par6.jsonl")
jl(six, [{"type": "user", "message": {"role": "user", "content": "go"}}] + [{"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": f"w{i}", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: s\nLevel: Complex"}}]}} for i in range(5)])
o = hand("Task: stage F\nLevel: Complex\nMap: not needed - t\nSize: M\nWorktree: ../app-f\nFiles: f.js\nGroup: A", "opus-worker", six)
res(4, "a sixth lane gets the usage-limit notice", "[lanes]" in o and '"deny"' not in o, o)
# 5 foreground tests, no repeated ⏳ line, ✅ line
base = os.path.join(V, "projects"); sid = "s5"; os.makedirs(os.path.join(base, sid, "subagents"))
TP = os.path.join(base, sid + ".jsonl"); jl(TP, [{"type": "user", "message": {"role": "user", "content": "go"}}])
jl(os.path.join(base, sid, "subagents", "agent-w1.jsonl"), [{"type": "user", "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "message": {"role": "user", "content": "Task: x"}}])
bi = {"session_id": sid, "agent_id": "w1", "transcript_path": TP, "tool_name": "Bash", "hook_event_name": "PreToolUse",
      "tool_input": {"command": "npm run test:smoke", "run_in_background": True}}
o = run("worker-budget.py", bi, P)
res(5, "a worker's background test run is refused once, with the foreground fix", '"deny"' in o and "600000" in o, o)
o = run("worker-budget.py", bi, P)
res(5, "  ...the second try passes (never loops)", '"deny"' not in o, o)
res(5, "the rules no longer tell workers to run tests in the background", "run a long test in the background while you read code" not in RULES, "")
M = os.path.join(V, "m.jsonl")
jl(M, [{"type": "user", "message": {"role": "user", "content": "go"}},
       {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: s", "run_in_background": True}}]}},
       {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a1", "content": "Async agent launched successfully. agentId: w1"}]}},
       {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "a2", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: t", "run_in_background": True}}]}},
       {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a2", "content": "Async agent launched successfully. agentId: w2"}]}}])
note = "<task-notification><task-id>bx1</task-id><status>completed</status><summary>Background command finished</summary></task-notification>"
o1 = run("plan-gate.py", {"prompt": note, "session_id": "n5", "transcript_path": M}, P, HZ_REPORT_TIMING_OFF=None)
o2 = run("plan-gate.py", {"prompt": note, "session_id": "n5", "transcript_path": M}, P, HZ_REPORT_TIMING_OFF=None)
res(5, "first wake-up with work running: the ⏳ line", "Still running" in o1, o1[:200])
res(5, "next wake-up, nothing changed: one character, not the ⏳ line again", "Nothing changed" in o2 and "one character" in o2, o2[:200])
res(5, "the report-time notice asks for the ✅ Completed line", "✅ Completed:" in read(H, "_common.py"), "")
# 6 Sonnet's named change in .github/
def sedit(prompt, f):
    s6 = "s6" + str(abs(hash(prompt)) % 1000); os.makedirs(os.path.join(base, s6, "subagents"), exist_ok=True)
    tp6 = os.path.join(base, s6 + ".jsonl"); jl(tp6, [{"type": "user", "message": {"role": "user", "content": "go"}}])
    jl(os.path.join(base, s6, "subagents", "agent-g1.jsonl"), [{"type": "user", "message": {"role": "user", "content": prompt}}])
    return run("routing-guard.py", {"session_id": s6, "agent_id": "g1", "agent_type": "sonnet-worker", "transcript_path": tp6,
                                    "tool_name": "Edit", "tool_input": {"file_path": os.path.join(P, f)}}, P)
o = sedit("Task: CI trigger\nNamed change: .github/workflows/ci.yml — add claude/** to the push trigger", ".github/workflows/ci.yml")
res(6, "Sonnet may make the change its hand-over names in .github/", '"deny"' not in o, o)
o = sedit("Task: CI\nmake the jobs faster", ".github/workflows/ci.yml")
res(6, "  ...without a named change it is still refused", '"deny"' in o, o)
o = sedit("Task: x\nNamed change: .github/workflows/ci.yml — y", "firestore.rules")
res(6, "  ...and the other protected files stay refused", '"deny"' in o, o)
# 7 plan check
pg = lambda path: run("plan-guard.py", {"tool_name": "ExitPlanMode", "session_id": "pg", "tool_input": {"plan": open(path).read()}}, P)
QR = ("# Plan v2 — Headers — Awaiting approval\n\n**Quick read** · 60 words · about 1 min\n\n**Summary**\n- Goal: one header.\n- Done: 3 of 8.\n"
      "- I need from you: approve.\n\n**What changed since v1**\n- Phone header taller.\n\n**Decisions:** None open.\n\n**Next steps**\n- PR 4.\n\n"
      "Stages to finish\n2 stages: 1 build and 1 check by you.\n1. PR 4 headers · Claude · Build\n2. Merge PR 4 · You · Check\n\nThe header test on line 149 must pass.\n\n"
      "Technical details\n- js/47-header.js\n")
open(os.path.join(V, "qr.md"), "w").write(QR); o = pg(os.path.join(V, "qr.md"))
res(7, "a Quick read plan is not asked for the old Summary table", "Summary table" not in o and "Quick read" not in o.split("shape that passes")[0][-400:] if o else True, o[:300])
res(7, "a find above 'Technical details' is quoted with its plan line and the words around it", "plan line" in o and "header test on line 149" in o, o[:400])
# 8 token report labels and helper totals
S = os.path.join(V, "st"); os.makedirs(os.path.join(S, ".claude", "state"))
tp8 = os.path.join(V, "ss.jsonl"); sd8 = os.path.join(V, "ss", "subagents"); os.makedirs(sd8)
ts = lambda m: (dt.datetime(2026, 10, 10, 13, 0) + dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
jl(tp8, [{"type": "user", "timestamp": ts(0), "message": {"role": "user", "content": "go"}},
         {"type": "assistant", "timestamp": ts(1), "message": {"id": "m1", "role": "assistant", "usage": {"input_tokens": 1000}, "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: s1", "run_in_background": True}}]}},
         {"type": "user", "timestamp": ts(1), "toolUseResult": {"status": "async_launched"}, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a1", "content": "Async agent launched"}]}},
         {"type": "assistant", "timestamp": ts(30), "message": {"id": "m2", "role": "assistant", "usage": {"input_tokens": 1000}, "content": [{"type": "text", "text": "Done.\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Ready.\n> 👉 **I need from you:** Nothing.\n> ➡️ **Next:** Stop."}]}}])
jl(os.path.join(sd8, "agent-w1.jsonl"), [{"type": "user", "timestamp": ts(2), "message": {"role": "user", "content": "Task: s1"}}] +
   [{"type": "assistant", "timestamp": ts(3 + i), "message": {"id": f"h{i}", "role": "assistant", "usage": {"input_tokens": 100000}, "content": [{"type": "tool_use", "id": f"r{i}", "name": "Read", "input": {"file_path": "a.js"}}]}} for i in range(5)])
json.dump({"agentType": "opus-worker"}, open(os.path.join(sd8, "agent-w1.meta.json"), "w"))
run("stats.py", {"transcript_path": tp8, "session_id": "ss", "hook_event_name": "Stop"}, S, HZ_STATS_FORCE="1")
try:
    st = json.loads(open(os.path.join(S, ".claude", "state", "stats.jsonl")).read().strip().splitlines()[-1])
except Exception as e:
    st = {"error": str(e)}
res(8, "a worker reading files counts as 'reading', not 'planning'", (st.get("activity") or {}).get("reading", 0) >= 500000 and (st.get("activity") or {}).get("planning", 0) < 100000, st.get("activity"))
res(8, "the worker's tokens show under its role (not 0)", (st.get("by_helper") or {}).get("opus-worker", 0) >= 500000, st.get("by_helper"))
# 9 report link
A = os.path.join(V, "app"); os.makedirs(os.path.join(A, "docs", "reports"))
sh("git init -q && git config user.email t@t && git config user.name t && git remote add origin https://github.com/o/Weekly-Planner.git", A)
open(os.path.join(A, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n"
    "| Pass plan · Stage 1 of 3 — a | COMPLETE | ok |\n| Pass plan · Stage 2 of 3 — b | PARTIAL | |\n| Pass plan · Stage 3 of 3 — c (Check) | QUEUED | |\n")
open(os.path.join(A, "docs", "reports", "pass-plan-checkpoint-1.md"), "w").write("# r")
sh("git add -A && git commit -qm a && git checkout -qb claude/x", A)
o = subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])"],
                   capture_output=True, text=True, cwd=H, env=dict(os.environ, CLAUDE_PROJECT_DIR=A, PYTHONDONTWRITEBYTECODE="1")).stdout
res(9, "the Completion lines carry the report link", "Report: [pass-plan-checkpoint-1.md](https://github.com/o/Weekly-Planner/blob/claude/x/docs/reports/pass-plan-checkpoint-1.md)" in o, o)
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
