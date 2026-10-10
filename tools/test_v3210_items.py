#!/usr/bin/env python3
"""v3.2.10 item test: the 21 problems found with 3.2.9, each tested the same way on any rules version.
Usage: python3 tools/test_v3210_items.py <central dir>   (for example central, or a copy of the 3.2.9 central folder)
Prints one line per check: item number, PASS/FAIL, what was checked and what happened. Hook checks run the real hook
scripts on scripted inputs in a temporary project; text checks read the rules, planner and reviewer files. Items 1, 2,
4, 19, 20 and 21 also have a real-program test (tools/real-harness/scenario_workflow.sh, scenario_setup_update.sh)."""
import json, os, subprocess, sys, tempfile, datetime as dt, glob, shutil
C = os.path.abspath(sys.argv[1]); H = os.path.join(C, "hooks"); ROOT = os.path.dirname(C)
V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:160]!r}"))
def run(script, inp, proj, **env):
    p = os.path.join(H, script)
    if not os.path.exists(p):
        return f"<no {script}>"
    e = dict(os.environ, CLAUDE_PROJECT_DIR=proj, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(env)
    for k in [k for k, v in e.items() if v is None]:
        e.pop(k)
    return subprocess.run(["python3", p], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=proj).stdout
def sh(cmd, cwd): subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True)
def read(*parts):
    try:
        return open(os.path.join(*parts), encoding="utf-8").read()
    except OSError:
        return ""
now = lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
RULES = read(C, "rules", "CLAUDE-rules.md"); PLANNER = read(C, "agents", "planner-instructions.md")
REVIEWER = read(C, "agents", "reviewer-instructions.md"); CFG = json.loads(read(H, "config.json") or "{}")

# ---- workflow helpers (items 1, 19, 21) -----------------------------------------------------------------------
P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state"))
base = os.path.join(V, "projects", "-p"); sid = "s10"; os.makedirs(base)
T = os.path.join(base, sid + ".jsonl"); open(T, "w").write("")
wf = os.path.join(base, sid, "subagents", "workflows", "wf_1"); os.makedirs(wf)
def record(aid, n, first="WFAGENT: run the tests"):
    rows = [{"type": "user", "timestamp": now(), "message": {"role": "user", "content": first}}]
    rows += [{"type": "assistant", "timestamp": now(), "message": {"id": f"m{i}", "role": "assistant", "content": [
        {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": "npm test"}}]}} for i in range(n)]
    open(os.path.join(wf, f"agent-{aid}.jsonl"), "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
inp = lambda aid: {"session_id": sid, "agent_id": aid, "transcript_path": T, "tool_name": "Bash",
                   "tool_input": {"command": "npm test"}, "hook_event_name": "PreToolUse"}
record("wa", 10); o = run("worker-budget.py", inp("wa"), P)
res(1, "workflow helper at 10 test runs is warned", "You ran 10 test runs" in o, o)
record("wb", 20); o = run("worker-budget.py", inp("wb"), P)
res(1, "workflow helper at 20 test runs is stopped", "Test-run limit reached (20)" in o, o)
record("wd", 20, "Task kind: test speed\nWFAGENT: faster tests"); o = run("worker-budget.py", inp("wd"), P)
res(21, "test-speed helper at 20 runs: warned, not stopped", "You ran 20" in o and "limit reached" not in o.lower(), o)
record("we", 40, "Task kind: test speed\nWFAGENT: faster tests"); o = run("worker-budget.py", inp("we"), P)
res(21, "test-speed helper at 40 runs is stopped", "Test-run limit reached (40)" in o, o)
open(os.path.join(P, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": sid, "n": 4}))
wi = {"session_id": sid, "tool_name": "Workflow", "tool_input": {"script": "await parallel([()=>agent('fix A')])"}, "transcript_path": T}
o = run("worker-guard.py", wi, P)
res(19, "workflow without role files is refused, with the fix", '"deny"' in o and "Role file:" in o, o)
o = run("worker-guard.py", wi, P)
res(19, "second try passes (never loops)", '"deny"' not in o, o)
pre = {x.get("script"): x.get("tools", "") for x in (CFG.get("dispatch") or {}).get("PreToolUse", [])}
res(19, "switchboard sends Workflow to the role check", "Workflow" in pre.get("worker-guard.py", ""), pre.get("worker-guard.py"))

# ---- wait line, hook list, setup version (items 2, 4) -----------------------------------------------------------
o = run("report-timing.py", {"session_id": sid, "tool_name": "Workflow", "tool_input": {"script": "x"}}, P)
res(2, "wait line when a workflow starts", "the workflow you are starting" in o, o)
res(2, "switchboard sends Workflow to the wait-line check", "Workflow" in pre.get("report-timing.py", ""), pre.get("report-timing.py"))
stub = json.loads(read(C, "stub-files", "settings.json") or "{}")
res(2, "app hook list covers Workflow", any("Workflow" in (g.get("matcher") or "") for g in stub.get("hooks", {}).get("PreToolUse", [])), "")
co = read(H, "_common.py")
res(4, "setup version 3.2.10 (apps get the new hook list)", '"version": "3.2.10"' in co, "")

# ---- scenario file (items 3, 20) ------------------------------------------------------------------------------------
sc = read(ROOT, "tools", "real-harness", "scenario_workflow.sh") + read(ROOT, "tools", "real-harness", "stand_in_workflow.py")
res(3, "real-program workflow scenario exists", bool(sc), "")
res(20, "scenario covers role files, edit and commit, test speed and the report",
    all(w in sc for w in ("Role file", "git commit", "Task kind: test speed", "plan_report.py")) if sc else False,
    "" if sc else "no scenario")

# ---- rules text (items 5, 6, 11, 17, 18) ---------------------------------------------------------------------------
res(5, "rules: references are exact by default", "**References are exact.**" in RULES, "")
res(5, "planner marks each reference exact or for reference only", "for reference only" in PLANNER, "")
res(5, "reviewer blocks an unconfirmed difference", "An unconfirmed difference blocks." in REVIEWER, "")
res(6, "rules: checkpoint reports in plans over 10 Build stages", "**Checkpoint reports.**" in RULES, "")
res(6, "planner adds the checkpoint report stages", "Checkpoint report <n>" in PLANNER, "")
res(11, "rules: the ⏳ line stands alone", "The ⏳ line always stands alone" in RULES, "")
res(11, "report-time notice says: no ⏳ line in the full report", "without the ⏳ line" in co, "")
res(17, "rules: one push after the review", "**One push after the review.**" in RULES, "")
res(18, "rules: wide checks run on GitHub, not in the PC loop", "**Wide checks run on GitHub.**" in RULES, "")

# ---- a real ledger: items 9, 10, 12, 14 -----------------------------------------------------------------------------
A = os.path.join(V, "app"); os.makedirs(A)
sh("git init -q --bare ../o.git && git init -q . && git config user.email t@t && git config user.name t && git remote add origin ../o.git", A)
rows = [(1, "tests", "COMPLETE", "ok"), (2, "PR 1 build · proof: smoke green", "COMPLETE", "ok"), (3, "merge PR 1 (Check)", "COMPLETE", "merged"),
        (4, "PR 2 headers · proof: measured", "PARTIAL", ""), (5, "merge PR 2 (Check)", "QUEUED — after Stage 4", ""),
        (6, "PR 3 words", "QUEUED — after Stage 5", ""), (7, "PR 4 cards", "QUEUED — after Stage 6", ""),
        (8, "merge PR 4 (Check)", "QUEUED — after Stage 7", ""), (9, "PR 5 sheets", "QUEUED — after Stage 8", "")]
open(os.path.join(A, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n\n## Where we are\n- x\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n"
    + "\n".join(f"| Pass · Stage {k} of 9 — {n} | {s} | {e} |" for k, n, s, e in rows) + "\n")
open(os.path.join(A, "index.html"), "w").write("x")
sh("git add -A && git commit -qm b && git push -q origin HEAD:main && git checkout -qb claude/x && git push -q -u origin claude/x", A)
def disp():
    return subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])"],
                          capture_output=True, text=True, cwd=H, env=dict(os.environ, CLAUDE_PROJECT_DIR=A, PYTHONDONTWRITEBYTECODE="1")).stdout
o = disp()
res(10, "Completion lines: Now, Next 3, Later count", "Now: 4 PR 2 headers" in o and "Next: 5 Check: merge PR 2 · 6 PR 3 words · 7 PR 4 cards" in o and "Later: 2 stages" in o, o)
res(10, "no proof text and no row per stage", "proof:" not in o and o.count("\n- ") == 0, o)
TR = os.path.join(V, "t.jsonl")
def turn(text, edit=True):
    R = [{"type": "user", "message": {"role": "user", "content": "go"}}]
    if edit:
        R += [{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "e1", "name": "Edit", "input": {"file_path": os.path.join(A, "app.js")}}]}},
              {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "e1", "content": "ok"}]}}]
    R.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
    open(TR, "w").write("\n".join(json.dumps(r) for r in R) + "\n")
REP = ("Header built.\nCompletion: Build 3 of 6 done (50%) · Check 1 of 3\nConfidence: Medium · Status: Checked\n\n❓ Decisions\n"
       "1. Phone week: A keep. Recommend: A.\n---\n> 📌 **Result:** Waiting on a decision.\n> 👉 **I need from you:** Answer 1.\n> ➡️ **Next:** I build it.")
turn(REP); o = run("completion-guard.py", {"transcript_path": TR, "session_id": "c1"}, A)
res(9, "a report with ❓ Decisions is not sent back (the 9 Oct duplicate)", '"block"' not in o, o)
turn(REP.replace("❓ Decisions\n1. Phone week: A keep. Recommend: A.\n", "")); o = run("completion-guard.py", {"transcript_path": TR, "session_id": "c2"}, A)
res(9, "other send-backs ask for one line, not the report again", '"block"' in o and "do not repeat the report" in o, o)
turn("Continue Pass on branch claude/x; next: Stage 4.\nConfidence: High · Status: Checked", edit=False)
sh("git commit -qam w; git push -q", A)
o = run("handoff-guard.py", {"transcript_path": TR, "session_id": "h1"}, A)
res(10, "hand-off check does not demand every queued row", "List every row" not in o, o)
o = run("plan-gate.py", {"prompt": "merged, go on", "session_id": "m1"}, A)
res(12, "after a merge the restart line goes to the record, not the reply", "restart line only in the record, not in this reply" in o, o[:200])
os.makedirs(os.path.join(A, ".claude", "state"), exist_ok=True)
open(os.path.join(A, ".claude", "state", "session-tokens.json"), "w").write(json.dumps({"long1": 98572369}))
o = run("plan-gate.py", {"prompt": "next step please", "session_id": "long1"}, A)
res(12, "a long session (98 M tokens counted, as on 9 Oct) gets no early hand-off", "This session is long" not in o, o[:200])
s = read(A, "WORKING_RECORD.md").replace("Stage 9 of 9 — PR 5 sheets", "Stage 9 of 11 — PR 5 sheets") + \
    "| Pass · Stage 10 of 11 — PR 6 | QUEUED — after Stage 9 | |\n| Pass · Stage 11 of 11 — merge (Check) | QUEUED — after Stage 10 | |\n"
open(os.path.join(A, "WORKING_RECORD.md"), "w").write(s)
o = disp(); res(14, "a changed stage total shows one line (9 → 11)", "Plan: 9 → 11 stages" in o, o)

# ---- /compact (item 13) ----------------------------------------------------------------------------------------------
def mem(tokens, s):
    m = os.path.join(V, f"mem{tokens}.jsonl")
    open(m, "w").write("\n".join(json.dumps(r) for r in [{"type": "user", "message": {"role": "user", "content": "x"}},
        {"type": "assistant", "message": {"id": "a", "role": "assistant", "usage": {"input_tokens": 5, "cache_read_input_tokens": tokens}, "content": [{"type": "text", "text": "y"}]}}]) + "\n")
    return run("plan-gate.py", {"prompt": "next", "session_id": s, "transcript_path": m}, P)
o = mem(230000, "k1"); res(13, "no /compact request at 23% context", "/compact" not in o, o[:200])
o = mem(530000, "k2"); res(13, "/compact asked at 53%, with the %", "then type /compact (context 53%)" in o, o[:200])

# ---- report delivery (item 15) ---------------------------------------------------------------------------------------
open(os.path.join(A, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "rd", "n": 2}))
os.makedirs(os.path.join(A, "docs", "reports"), exist_ok=True)
turn("Work goes on.\nConfidence: High · Status: Checked", edit=False)
run("report-delivery.py", {"transcript_path": TR, "session_id": "rd"}, A)
open(os.path.join(A, "docs", "reports", "pass-checkpoint-1.md"), "w").write("# report")
o = run("report-delivery.py", {"transcript_path": TR, "session_id": "rd"}, A)
res(15, "a new report I did not get is sent back (the 9 Oct checkpoint report)", "pass-checkpoint-1.md is written but I have not got it" in o, o)

# ---- GitHub (items 7, 16) --------------------------------------------------------------------------------------------
gi = lambda c: {"tool_name": "Bash", "tool_input": {"command": c}, "session_id": "g"}
o = run("git-guard.py", gi("gh pr create --base claude/consistency-3 --title x --body y"), A)
res(7, "pull request on a work branch: move-to-main warning", "--base main" in o and '"deny"' not in o, o)
o = run("git-guard.py", gi('git add WORKING_RECORD.md docs/reports/x.md && git commit -m "record"'), A)
res(16, "notes-only commit gets the [skip ci] hint", "[skip ci]" in o, o)
def mturn(cmds):
    R = [{"type": "user", "message": {"role": "user", "content": "go"}}]
    for i, c in enumerate(cmds):
        R += [{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"b{i}", "name": "Bash", "input": {"command": c}}]}},
              {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"b{i}", "content": "all checks pass"}]}}]
    R.append({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Green.\n---\n> 📌 **Result:** Ready.\n> 👉 **I need from you:** Merge pull request 9.\n> ➡️ **Next:** PR 5."}]}})
    open(TR, "w").write("\n".join(json.dumps(r) for r in R) + "\n")
sh("git checkout -q -- . ; echo y >> WORKING_RECORD.md && git commit -qam notes", A)
mturn(["git push", "gh pr checks 9 --watch", "git push"]); o = run("merge-guard.py", {"transcript_path": TR, "session_id": "mg1"}, A)
res(16, "notes-only last push after green code: no new 8-minute wait (the 9 Oct case)", o.strip() == "", o)

# ---- end report (items 8, 20) ----------------------------------------------------------------------------------------
S = os.path.join(V, "sess"); os.makedirs(S)
t0 = dt.datetime(2026, 10, 9, 18, 0, tzinfo=dt.timezone.utc); ts = lambda m: (t0 + dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
main = [{"type": "user", "timestamp": ts(0), "message": {"role": "user", "content": "Continue Pass plan on branch x"}},
        {"type": "assistant", "timestamp": ts(1), "message": {"id": "a1", "role": "assistant", "content": [{"type": "tool_use", "id": "toolu_gh1", "name": "Bash", "input": {"command": "timeout 1800 gh run watch 5", "run_in_background": True}}]}},
        {"type": "user", "timestamp": ts(1), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_gh1", "content": "started"}]}},
        {"type": "user", "timestamp": ts(11), "message": {"role": "user", "content": "<task-notification><task-id>x</task-id><tool-use-id>toolu_gh1</tool-use-id></task-notification>"}},
        {"type": "assistant", "timestamp": ts(60), "message": {"id": "a2", "role": "assistant", "content": [{"type": "text", "text": "done"}]}}]
open(os.path.join(S, "m.jsonl"), "w").write("\n".join(json.dumps(r) for r in main) + "\n")
def helper(path, stage, start, end, f):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(json.dumps(r) for r in [
        {"type": "user", "timestamp": ts(start), "message": {"role": "user", "content": f"Task: Stage {stage} of 9 — x"}},
        {"type": "assistant", "timestamp": ts(end), "message": {"id": f"h{stage}", "role": "assistant", "content": [{"type": "tool_use", "id": f"w{stage}", "name": "Edit", "input": {"file_path": "D:/r/" + f}}]}}]) + "\n")
helper(os.path.join(S, "m", "subagents", "agent-a1.jsonl"), 3, 2, 22, "css/app.css")
helper(os.path.join(S, "m", "subagents", "workflows", "wf_1", "agent-b2.jsonl"), 5, 23, 33, "tests/smoke.js")
o = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "Pass plan", "--dir", S], capture_output=True, text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=A)).stdout
res(8, "end report lists parallel candidates", "**Parallel candidates:** 10 min" in o, o[:300])
res(20, "end report counts workflow helpers (2 of 2)", "| Helpers started | 2 |" in o, o[:300])
res(20, "end report counts background GitHub waits (10 min)", "**waiting for GitHub**: 10 min" in o, o[:400])

shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok_items = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok_items)} of {len(items)}: {ok_items}")
