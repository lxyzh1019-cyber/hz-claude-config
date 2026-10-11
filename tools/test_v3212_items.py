#!/usr/bin/env python3
"""v3.2.12 item test, the same checks on any rules version. Usage: python3 tools/test_v3212_items.py <repo dir>
Items: 1 Windows packages rule · 3 Part n and #number · 4 hz-change-guard v18 copy · 5 revision record and gate ·
6 one ⏳ line per round, '…' after it, no text before tool steps, the pushing worker waits for GitHub ·
7 the report no longer says 'run long tests in the background'. Item 2 (plan marks round) stays open: see the record."""
import json, re, os, subprocess, sys, tempfile, shutil
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    ok = bool(ok); results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""
def run(script, inp, proj, **env):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(env)
    for k in [k for k, v in e.items() if v is None]:
        e.pop(k)
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=proj).stdout
def jl(path, rows): open(path, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
RULES = read(C, "rules", "CLAUDE-rules.md")
P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); subprocess.run("git init -q", shell=True, cwd=P)
# 1
res(1, "CLAUDE.md: Windows line endings and a Windows-style dry-run for every package", "Windows line endings (CRLF)" in read(R, "CLAUDE.md"), "")
res(1, "README Step E: stop when GitHub Desktop lists more files than the chat said", "lists more files than the chat said" in read(R, "README.md"), "")
# 3
res(3, "rules: 'Part n' for work packages, '#number' for pull requests", "**Part and #number.**" in RULES and 'Never write "PR 5" for a Part' in RULES, "")
res(3, "planner: never 'PR n' for a Part", "Never \"PR n\" for a Part" in read(C, "agents", "planner-instructions.md"), "")
# 4
res(4, "repo copy of hz-change-guard has the revision gate", os.path.exists(os.path.join(C, "skills", "hz-change-guard", "scripts", "revision_gate.py")), "")
res(4, "  ...and the revision-record format", os.path.exists(os.path.join(C, "skills", "hz-change-guard", "references", "revision-record.md")), "")
# 5
rec = read(R, "revision-record.md")
res(5, "revision-record.md: version, base, owner, features, open problems, fixes",
    all(x in rec for x in ("Version: ", "Built on: ", "Owner: ", "## Features", "## Open problems", "## Fixed", "proof:")), "")
# 6
M = os.path.join(V, "m.jsonl")
jl(M, [{"type": "user", "message": {"role": "user", "content": "go"}},
       {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: s", "run_in_background": True}}]}},
       {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a1", "content": "Async agent launched successfully. agentId: w1"}]}},
       {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "a2", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: t", "run_in_background": True}}]}},
       {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a2", "content": "Async agent launched successfully. agentId: w2"}]}}])
note = lambda n: f"<task-notification><task-id>bx{n}</task-id><status>completed</status><summary>Background command {n} finished</summary></task-notification>"
pg = lambda prompt, sid="r6": run("plan-gate.py", {"prompt": prompt, "session_id": sid, "transcript_path": M}, P, HZ_REPORT_TIMING_OFF=None)
o1 = pg(note(1)); o2 = pg(note(2))
res(6, "first wake-up of a round: the ⏳ line", "Still running" in o1, o1[:160])
res(6, "a later wake-up with different work: one character, not a new ⏳ line", "one character only" in o2, o2[:160])
pg("Please go on with the next stage")
o3 = pg(note(3))
res(6, "my message starts a new round: the ⏳ line once more", "Still running" in o3, o3[:160])
rt = lambda sid: run("report-timing.py", {"session_id": sid, "tool_name": "Agent", "tool_input": {"subagent_type": "reviewer", "prompt": "x", "run_in_background": True}}, P, HZ_REPORT_TIMING_OFF=None,
                     HZ_BACKGROUND_WORKERS="1")   # v3.2.14: workers run in the foreground unless this is set
pg("next", "r7"); o4 = rt("r7"); o5 = rt("r7")
res(6, "a helper started later in the same round gets '…', not a second ⏳ line", "Working on" in o4 and "one character only" in o5, (o4[:80], o5[:120]))
res(6, "the wait notice says: no text before tool steps", "no text before tool steps" in read(H, "_common.py"), "")
gw = lambda extra: run("wait-guard.py", dict({"tool_name": "Bash", "session_id": "w", "tool_input": {"command": "timeout 600 gh run watch 5 --exit-status"}}, **extra), P)
o6 = gw({"agent_id": "w1"}); o7 = run("wait-guard.py", {"tool_name": "Bash", "session_id": "w", "tool_input": {"command": "timeout 600 gh run watch 5 --exit-status"}}, P, HZ_BACKGROUND_WORKERS="1")   # v3.2.14: with foreground workers the main session may wait
res(6, "the pushing worker may wait for its GitHub run in the foreground", '"deny"' not in o6, o6[:160])
res(6, "  ...the main session may not, and is told to give the wait to the worker", '"deny"' in o7 and "worker that pushed" in o7, o7[:160])
# 8 lean main session
A = os.path.join(V, "app"); os.makedirs(os.path.join(A, ".claude", "state"))
subprocess.run("git init -q", shell=True, cwd=A)
open(os.path.join(A, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "lm", "n": 3}))
rg = lambda extra: run("routing-guard.py", dict({"tool_name": "Edit", "session_id": "lm", "tool_input": {"file_path": os.path.join(A, "WORKING_RECORD.md")}}, **extra), A)
o1 = rg({}); o2 = rg({}); o3 = rg({"agent_id": "w1"})
res(8, "the main session editing the record gets the lean-main notice", "[lean main]" in o1 and '"deny"' not in o1, o1[:160])
res(8, "  ...once per prompt", "[lean main]" not in o2, o2[:160])
res(8, "  ...a worker editing the record gets none", "[lean main]" not in o3, o3[:160])
res(8, "rules: the lean main session rule", "**Lean main session (Hook).**" in RULES, "")
# 9 one review per pull request
T0 = os.path.join(V, "e.jsonl"); jl(T0, [{"type": "user", "message": {"role": "user", "content": "go"}}])
rv = lambda t: run("worker-guard.py", {"tool_name": "Agent", "session_id": "rv", "transcript_path": T0, "tool_use_id": "x",
                   "tool_input": {"subagent_type": "reviewer", "prompt": f"Task: {t}\nLevel: Complex\nMap: not needed - t\nSize: S"}}, A,
                   HZ_STAGE_TAGS_OFF="1", HZ_PLANNER_CHECK_OFF="1")
r1 = rv("Stage 30 — Part 5 parent headers"); r2 = rv("Stage 30 — Part 5 parent headers (re-check)"); r3 = rv("Stage 30 — Part 5 parent headers (final pass)")
res(9, "the first and second review get no notice", "[one review]" not in r1 + r2, (r1 + r2)[:160])
res(9, "the third review for the same task gets the one-review notice", "[one review]" in r3 and '"deny"' not in r3, r3[:200])
res(9, "reviewer role file: every finding in one pass", "list every finding at once" in read(C, "agents", "reviewer-instructions.md"), "")
# 10 pictures before the first push
res(10, "rules and worker role file: pictures and Proof line before the first push",
    "**Pictures before the first push.**" in RULES and "Before the first push" in read(C, "agents", "opus-worker-instructions.md"), "")
# 11 report link in the first Completion line; saved fix when missing
L = os.path.join(V, "wl"); os.makedirs(os.path.join(L, "docs", "reports")); os.makedirs(os.path.join(L, ".claude", "state"))
subprocess.run("git init -q && git config user.email t@t && git config user.name t && git remote add origin https://github.com/o/Weekly-Planner.git", shell=True, cwd=L)
rows = [f"| Long plan · Stage {k} of 24 — {'merge (Check)' if k % 2 == 0 else 'part ' + str(k)} | {'COMPLETE' if k < 13 else 'QUEUED'} | {'ok' if k < 13 else ''} |" for k in range(1, 25)]
open(os.path.join(L, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n" + "\n".join(rows) + "\n")
open(os.path.join(L, "docs", "reports", "long-plan-checkpoint-1.md"), "w").write("# r")
subprocess.run("git add -A && git commit -qm a && git checkout -qb claude/x", shell=True, cwd=L)
dsp = subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])"],
                     capture_output=True, text=True, cwd=H, env=dict(os.environ, CLAUDE_PROJECT_DIR=L, PYTHONDONTWRITEBYTECODE="1")).stdout
first = dsp.splitlines()[0] if dsp else ""
res(11, "the report link is in the first Completion line", re.search(r"Report:\**\s*\[long-plan-checkpoint-1\.md\]", dsp), first[:200])
TR = os.path.join(V, "t.jsonl")
jl(TR, [{"type": "user", "message": {"role": "user", "content": "go"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "e1", "name": "Edit", "input": {"file_path": os.path.join(L, "a.js")}}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "e1", "content": "ok"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done.\nCompletion: Build 6 of 12 done (50%) · Check 6 of 12\nConfidence: High · Status: Checked\n\n❓ Decisions\n1. x. Recommend: A.\n---\n> 📌 **Result:** Waiting.\n> 👉 **I need from you:** Answer.\n> ➡️ **Next:** Go."}]}}])
run("completion-guard.py", {"transcript_path": TR, "session_id": "cg"}, L)
pf = read(L, ".claude", "state", "pending-fixes.json")
res(11, "a reply without the link gets a saved fix for the next step (no send-back)", "report link" in pf, pf[:200])
# 12 checkpoint report at a check stop of a long plan
s = read(L, "WORKING_RECORD.md").replace("| Long plan · Stage 13 of 24 — part 13 | QUEUED |", "| Long plan · Stage 13 of 24 — part 13 | COMPLETE | ok |")
open(os.path.join(L, "WORKING_RECORD.md"), "w").write(s.replace("| COMPLETE | ok | |", "| COMPLETE | ok |"))
cpd = lambda: subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(checkpoint_due(load_config()))"],
                             capture_output=True, text=True, cwd=H, env=dict(os.environ, CLAUDE_PROJECT_DIR=L, PYTHONDONTWRITEBYTECODE="1")).stdout
c1 = cpd(); c2 = cpd()
res(12, "at a check stop of a long plan, a new checkpoint report is asked for", "checkpoint report 2" in c1 and "long-plan-checkpoint-2.md" in c1, c1[:200])
res(12, "  ...once per stop", c2.strip() == "", c2[:120])
res(12, "the finish notice carries it (plan-gate)", "checkpoint_due" in read(H, "plan-gate.py"), "")
# 7
res(7, "report fix text: workers run tests in the foreground", "run long tests in the background" not in read(H, "plan_report.py"), "")
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
