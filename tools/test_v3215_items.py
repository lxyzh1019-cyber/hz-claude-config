#!/usr/bin/env python3
"""v3.2.15 item test: one or more checks per solution S1–S25 (S16 is app work). Usage: python3 tools/test_v3215_items.py <repo dir>
Real session files are used where given: HZ_SESSION_11OCT=<folder of session 5a9d21fb>."""
import json, os, re, subprocess, sys, tempfile, shutil, glob
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    ok = bool(ok); results.append((item, ok)); print(f"{item:>4} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1", HZ_STAGE_TAGS_OFF="1", HZ_PLANNER_CHECK_OFF="1", HZ_COMPLEX_REASON_OFF="1")
for k in ("HZ_SKIP_CI_SOFT", "HZ_PLAN_MARKS_ROUND", "HZ_BACKGROUND_WORKERS"):
    ENV.pop(k, None)
def run(script, inp, proj, **env):
    e = dict(ENV, CLAUDE_PROJECT_DIR=proj); e.update(env)
    e = {k: v for k, v in e.items() if v is not None}
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=proj).stdout
def sh(c, cwd): subprocess.run(c, shell=True, cwd=cwd, capture_output=True)
def jl(path, rows): open(path, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
RULES = read(C, "rules", "CLAUDE-rules.md"); WORKER = read(C, "agents", "opus-worker-instructions.md")
A = os.path.join(V, "app"); os.makedirs(os.path.join(A, ".claude", "state")); sh("git init -q && git config user.email t@t && git config user.name t", A)
open(os.path.join(A, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "s", "n": 2}))
# S1
stub = json.loads(read(C, "stub-files", "settings.json") or "{}")
m = " ".join(g.get("matcher") or "" for g in stub.get("hooks", {}).get("PreToolUse", []))
res("S1", "Read, Grep and Glob no longer start the checks", "Read" not in m.split("|") and "Grep" not in m and "Glob" not in m and "Edit" in m, m)
T = os.path.join(V, "t.jsonl")
jl(T, [{"type": "user", "message": {"role": "user", "content": "go"}},
       {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/x/.cache/hz-rules/3.2.15/rules/CLAUDE-rules.md"}}]}}])
o = run("rules-first-guard.py", {"tool_name": "Edit", "session_id": "rf", "transcript_path": T, "tool_input": {"file_path": os.path.join(A, "a.js")}}, A, HZ_RULES_FIRST_OFF=None)
res("S1", "  ...the rules-first check finds the rules Read in the session file", '"deny"' not in o, o[:160])
# S2
s11 = os.environ.get("HZ_SESSION_11OCT")
if s11:
    sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", s11], capture_output=True, text=True).stdout
    res("S2", "the scorecard measures check time (11 Oct session)", re.search(r"Check time .*about \d+ min", sc), sc[:200])
else:
    res("S2", "the scorecard has a check-time line", "Check time (goal" in read(H, "plan_report.py"), "")
# S3
open(os.path.join(A, ".claude", "hz-off"), "w").write("")
o = subprocess.run(["python3", os.path.join(H, "dispatch.py")], input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "x", "tool_input": {"command": "git push origin main"}}),
                   capture_output=True, text=True, env=dict(ENV, CLAUDE_PROJECT_DIR=A), cwd=A).stdout
res("S3", "with .claude/hz-off every check is off (even a push to main passes the checks)", o.strip() == "", o[:160])
os.remove(os.path.join(A, ".claude", "hz-off"))
o = subprocess.run(["python3", os.path.join(H, "dispatch.py")], input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "x", "tool_input": {"command": "git push origin main"}}),
                   capture_output=True, text=True, env=dict(ENV, CLAUDE_PROJECT_DIR=A), cwd=A).stdout
res("S3", "  ...and on again without it", '"deny"' in o, o[:160])
# S4
pg = read(H, "plan-guard.py")
# v3.2.17: the way changed (the real program shows the plan file and an 'allow' approves without the owner): the marks
# go into the plan file with no send-back; HZ_PLAN_MARKS_ROUND=1 keeps the old round. Either way passes this item.
res("S4", "a revised plan goes on with its marks, no send-back; HZ_PLAN_MARKS_ROUND=1 keeps the old round",
    (("_UPD = dict(" in pg and '"updatedInput": _UPD' in pg) or ('_cur["via"] = "file"' in pg and '"updatedInput"' not in pg))
    and "HZ_PLAN_MARKS_ROUND" in pg, "")
# S5
T0 = os.path.join(V, "e.jsonl"); jl(T0, [{"type": "user", "message": {"role": "user", "content": "go"}}])
hv = lambda p, sid: run("worker-guard.py", {"tool_name": "Agent", "session_id": sid, "transcript_path": T0, "tool_use_id": "x", "tool_input": {"subagent_type": "opus-worker", "prompt": p}}, A)
o = hv("Task: Stage 35 — Part 7 Today\nLevel: Complex\nComplex because: design choice\nMap: not needed - t\nSize: M\nWorktree: ../app-lane-a\nFiles: js/31-today.js\nGroup: L", "l1")
res("S5", "the first lane of a round (Group and Files) may use its worktree", '"deny"' not in o, o[:160])
o = hv("Task: Stage 35 — Part 7 Today\nLevel: Complex\nComplex because: design choice\nMap: not needed - t\nSize: M\nWorktree: ../app-x", "l2")
res("S5", "  ...a single worker without a lane is still refused a worktree", '"deny"' in o, o[:160])
# S6
G = os.path.join(V, "g"); os.makedirs(G); sh("git init -q && git config user.email t@t && git config user.name t && printf 'a\\nb\\nc\\nd\\n' > x.js && git add -A && git commit -qm a && git branch base", G)
sh("printf 'a\\nB\\nc\\nd\\ne\\n' > x.js && printf 'n\\n' > y.css && git add -A && git commit -qm b", G)
o = subprocess.run(["python3", os.path.join(H, "change_list.py"), "base"], capture_output=True, text=True, cwd=G).stdout
res("S6", "the change list gives each file with line ranges", "`x.js` |" in o and "changed 2" in o and "added 5" in o and "`y.css` | new file" in o, o)
# S7 S8 S9
L = os.path.join(V, "wl"); os.makedirs(os.path.join(L, "plans")); os.makedirs(os.path.join(L, "docs", "reports")); os.makedirs(os.path.join(L, ".claude", "state"))
sh("git init -q && git config user.email t@t && git config user.name t && git remote add origin https://github.com/o/App.git", L)
rows = [(33, "Part 6 files", "Build", "32", 1), (34, "iPad read (Check)", "Check", "33, 38", 1), (35, "Part 7 Today", "Build", "34", 1), (38, "Merge Parts 7, 8, 10 (Check)", "Check", "35", 0),
        (40, "Merge Part 9 (Check)", "Check", "38", 0), (41, "Part 11 Sister Sync", "Build", "54", 0), (49, "Kit 1.1 dark mode", "Build", "34, 38, 40", 0), (54, "Merge Kit 1.1 (Check)", "Check", "49", 0)]
open(os.path.join(L, "plans", "plan-v11.md"), "w").write("# Plan v11 — Pass\n\n" + "\n".join(f"{k}. {n} · {'You' if t == 'Check' else 'Claude'} · {t} · after: {a}" for k, n, t, a, d in rows) + "\n")
open(os.path.join(L, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n" +
    "\n".join(f"| Pass · Stage {k} of 56 — {n} | {'COMPLETE' if d else 'QUEUED'} | {'ok' if d else ''} |" for k, n, t, a, d in rows) + "\n")
open(os.path.join(L, "docs", "reports", "pass-checkpoint-3.md"), "w").write("3"); open(os.path.join(L, "docs", "reports", "pass-checkpoint-2.md"), "w").write("2")
sh("git add -A && git commit -qm a && git checkout -qb claude/x", L)
dsp = subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])"],
                     capture_output=True, text=True, cwd=H, env=dict(ENV, CLAUDE_PROJECT_DIR=L)).stdout
res("S7", "Completion lines are bold, with every stage as **Stage n**", dsp.startswith("**Completion:") and "**Stage 38**" in dsp, dsp[:200])
res("S7", "  ...the stop that waits on you comes first (Stages 38 and 40), apart from the work", "**Waiting on you (one stop):** **Stage 38** Merge Parts 7, 8, 10 · **Stage 40** Merge Part 9" in dsp, dsp[:400])
res("S7", "  ...in run order: Kit 1.1 (Stage 49, 54) before Part 11 (Stage 41)", dsp.find("**Stage 49**") < dsp.find("**Stage 54**") < dsp.find("**Stage 41**"), dsp)
res("S8", "a link to the current plan", "**Plan:** [plan-v11.md](https://github.com/o/App/blob/claude/x/plans/plan-v11.md)" in dsp, dsp[-300:])
res("S9", "the report link is the highest report number, not the newest file date", "[pass-checkpoint-3.md]" in dsp, dsp[-300:])
# S10–S14, S17, S20, S22, S23, S25 (rules and role files)
res("S10", "worker self-check with the reviewer's checklist", "**Self-check before the hand-back.**" in RULES and "Self-check (v3.2.15)" in WORKER, "")
res("S11", "reviewer: one complete pass; a re-check only confirms", "**One complete review.**" in RULES and "A re-check (v3.2.15)" in read(C, "agents", "reviewer-instructions.md"), "")
res("S12", "exact Proof-line template", "**Proof-line template.**" in RULES, "")
res("S13", "gaps listed at the map step", "**Gaps at the map step.**" in RULES and "Map step (v3.2.15)" in read(C, "agents", "planner-instructions.md"), "")
res("S14", "review fixes go to Sonnet as Routine", "Review fixes go to sonnet-worker as Routine" in RULES, "")
res("S17", "big plans start with the planner and the reviewer", "**Big plans start with the planner.**" in RULES, "")
res("S20", "plan rows say Part n, never PR n", 'A plan row says "Part n", never "PR n"' in RULES, "")
res("S22", "format changes: find the old form in every test", "**Format changes.**" in RULES and "A format change" in WORKER, "")
res("S23", "workers commit and push their own work", "**Workers commit.**" in RULES and "Commit and push your own work" in WORKER, "")
res("S25", "lanes meet in one round branch; other pull requests updated after each merge", "**Lanes meet before me.**" in RULES, "")
# S15
K = os.path.join(V, "k"); os.makedirs(os.path.join(K, ".claude", "state")); os.makedirs(os.path.join(K, ".claude", "agents"))
open(os.path.join(K, ".claude", "agents", "reviewer.md"), "w").write("---\nname: reviewer\n---\n"); sh("git init -q && git config user.email t@t && git config user.name t && echo a > a.js && git add -A && GIT_COMMITTER_DATE='2026-10-11T15:00:00Z' git commit -qm a --date='2026-10-11T15:00:00Z'", K)
TR = os.path.join(V, "pr.jsonl")
jl(TR, [{"type": "user", "timestamp": "2026-10-11T16:00:00.000Z", "message": {"role": "user", "content": "go"}},
        {"type": "assistant", "timestamp": "2026-10-11T16:01:00.000Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "w1", "name": "Agent", "input": {"subagent_type": "opus-worker", "prompt": "Task: build"}}]}},
        {"type": "user", "timestamp": "2026-10-11T16:20:00.000Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "w1", "content": "done"}]}},
        {"type": "assistant", "timestamp": "2026-10-11T16:21:00.000Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "v1", "name": "Agent", "input": {"subagent_type": "reviewer", "prompt": "review"}}]}},
        {"type": "user", "timestamp": "2026-10-11T16:30:00.000Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "v1", "content": "ok"}]}},
        {"type": "assistant", "timestamp": "2026-10-11T16:31:00.000Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "w2", "name": "Agent", "input": {"subagent_type": "sonnet-worker", "prompt": "Task: Proof line"}}]}},
        {"type": "user", "timestamp": "2026-10-11T16:35:00.000Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "w2", "content": "done"}]}}])
sh("git checkout -qb claude/p && echo n >> WORKING_RECORD.md && git add -A && GIT_COMMITTER_DATE='2026-10-11T16:33:00Z' git commit -qm notes --date='2026-10-11T16:33:00Z'", K)
o = run("git-guard.py", {"tool_name": "Bash", "session_id": "pr", "transcript_path": TR, "tool_input": {"command": "gh pr create --base main --title x --body y"}}, K)
res("S15", "a notes-only commit after the review needs no new review before the pull request", "Send the reviewer first" not in o, o[:200])
sh("echo b >> a.js && git add -A && GIT_COMMITTER_DATE='2026-10-11T16:34:00Z' git commit -qm code --date='2026-10-11T16:34:00Z'", K)
o = run("git-guard.py", {"tool_name": "Bash", "session_id": "pr", "transcript_path": TR, "tool_input": {"command": "gh pr create --base main --title x --body y"}}, K)
res("S15", "  ...a code commit after the review still needs one", "Send the reviewer first" in o, o[:200])
# S18
o = run("rules-read-guard.py", {"tool_name": "Bash", "tool_input": {"command": 'python3 "C:/Users/x/.cache/hz-rules/3.2.15/hooks/plan_report.py" "Pass" --dir . | head -40'}}, A)
res("S18", "running the report tool is allowed (even piped into head)", '"deny"' not in o, o[:160])
o = run("rules-read-guard.py", {"tool_name": "Bash", "tool_input": {"command": 'cat "C:/Users/x/.cache/hz-rules/3.2.15/rules/CLAUDE-rules.md"'}}, A)
res("S18", "  ...reading the rules with a shell command is still refused", '"deny"' in o, o[:160])
# S19 S21
if s11:
    rep = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "Weekly-Planner consistency pass", "--dir", s11], capture_output=True, text=True, env=dict(ENV, CLAUDE_PROJECT_DIR=A)).stdout
    m19 = re.search(r"\*\*other commands\*\*: (\d+) min", rep)
    res("S19", "worker time is not counted again as 'other commands' (11 Oct: was 134 min)", (int(m19.group(1)) if m19 else 0) < 60, (m19.group(0) if m19 else "not in top 3"))
    sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", s11], capture_output=True, text=True).stdout
    m21 = re.search(r"Reviews per pull request.*?max (\d+)", sc)
    res("S21", "reviews counted per stage (11 Oct: was 12 for all together)", m21 and int(m21.group(1)) < 12, sc[:300])
# S24
o = run("git-guard.py", {"tool_name": "Bash", "session_id": "sk", "tool_input": {"command": 'git add WORKING_RECORD.md && git commit -m "record"'}}, A)
res("S24", "a notes-only commit without [skip ci] is refused once", '"deny"' in o and "[skip ci]" in o, o[:160])
o = run("git-guard.py", {"tool_name": "Bash", "session_id": "sk", "tool_input": {"command": 'git add WORKING_RECORD.md && git commit -m "record"'}}, A)
res("S24", "  ...the second try passes", '"deny"' not in o, o[:160])
# S26 S27 S28 S29 (added to 3.2.15 on 11 Oct): failed checks first; gh run rerun --failed; the notice; the harness lanes
res("S26", "rules and worker role file: failed checks first, full suite once at the end", "**Failed checks first (Hook).**" in RULES and "re-run only the failed checks first" in WORKER, "")
res("S27", "a GitHub failure without a code change: gh run rerun <id> --failed", "gh run rerun <id> --failed" in RULES, "")
import datetime as _dt
base = os.path.join(V, "projects"); sid = "ff"; os.makedirs(os.path.join(base, sid, "subagents"))
TP = os.path.join(base, sid + ".jsonl"); jl(TP, [{"type": "user", "message": {"role": "user", "content": "go"}}])
now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
def wrec(result):
    jl(os.path.join(base, sid, "subagents", "agent-w1.jsonl"), [
        {"type": "user", "timestamp": now, "message": {"role": "user", "content": "Task: fix"}},
        {"type": "assistant", "timestamp": now, "message": {"id": "m1", "role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "npm run test:smoke"}}]}},
        {"type": "user", "timestamp": now, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": result}]}}])
call = lambda c: run("worker-budget.py", {"session_id": sid, "agent_id": "w1", "transcript_path": TP, "tool_name": "Bash", "hook_event_name": "PreToolUse", "tool_input": {"command": c}}, A)
wrec("Exit code 1\n2 failed: todayRow, weekHead")
o = call("npm run test:smoke")
res("S28", "after a failed run, starting the full suite again gets the 'failed checks first' notice", "[failed first]" in o and '"deny"' not in o, o[:200])
o = call("npm run test:smoke")
res("S28", "  ...once per worker", "[failed first]" not in o, o[:160])
wrec("Exit code 1\n1 failed: x")
o = run("worker-budget.py", {"session_id": sid, "agent_id": "w1", "transcript_path": TP, "tool_name": "Bash", "hook_event_name": "PreToolUse", "tool_input": {"command": "SMOKE_ONLY=x npm run test:smoke"}}, A)
res("S28", "  ...re-running only the failed checks gets no notice", "[failed first]" not in o, o[:160])
res("S29", "the end-to-end test lanes are in the harness", "if a == 'F':" in read(R, "tools", "real-harness", "stand_in_workflow.py"), "")
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · solutions fully passing {len(ok)} of {len(items)}")
