#!/usr/bin/env python3
"""v3.3.0 item test (lead playbook). Usage: python3 tools/test_v330_items.py <repo dir>
 1 rules are the lead playbook (Rule 0, payoff score, lead, hand-overs, checks once, stops, feedback loop)
 2 plan window shows what you approve (1A): sent text without marks -> show the file's marked text once; then it passes
 3 a Rev is not sent to the planner (2A); points of an earlier approved plan are not demanded
 4 one change list with the colour line under "What changed since"
 5 refusals that cost more than they save are gone: sleep 5; runs, rules read by shell allowed, [skip ci] added,
   "Worktree: none" passes, the test-run notice is advice
 6 the lead's hand-over carries Files with lines, Test and Steps; Steps sets the worker's budget
 7 workers do not wait for GitHub; the lead may
 8 send-backs: one instruction ending in 'Done: …', and 'Done: …' passes; merge check remembers a green commit
 9 retired: hotspot counter, report-timing, pr-ready-guard; the 9 PM reminder comes at the next step
10 scorecard: one session by default, lead rows; end report has rule rows"""
import json, os, re, subprocess, sys, tempfile, shutil, time
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
results = []
SQ = "🟦🟩🟧🟪"


def res(i, name, ok, detail=""):
    ok = bool(ok); results.append((i, ok))
    print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))


def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""


def proj(name, planner=False):
    P = os.path.join(V, name); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
    os.makedirs(os.path.join(P, ".claude", "agents"))
    if planner:
        open(os.path.join(P, ".claude", "agents", "planner.md"), "w").write("x")
    subprocess.run("git init -q && git config user.email t@t && git config user.name t", shell=True, cwd=P)
    return P


def env(P, **kw):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(kw); return e


def hook(script, P, inp, **kw):
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True,
                          env=env(P, **kw), cwd=P).stdout


def tx(path, recs):
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def user(t, ts="2026-10-13T10:00:00Z"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": t}}


def asst(*b, ts="2026-10-13T10:00:05Z"):
    return {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": list(b)}}


def tool(n, i, id_="t1"):
    return {"type": "tool_use", "id": id_, "name": n, "input": i}


def text(t):
    return {"type": "text", "text": t}


def plan(title, extra=""):
    return (f"# {title} — Pass — Awaiting approval\n\n**Quick read** · 40 words · about 1 min\n\n**Summary**\n- Goal: kit.\n"
            "- Done: 2 of 6.\n- I need from you: approve.\n\n**What changed since Rev 3**\n- Fewer stops.\n" + extra +
            "\n**Decisions:** None open.\n\n**Stops**\n- Round 1: merge.\n\nStages to finish\n2 stages: 1 build and 1 check by you.\n"
            "3. Kit 1.1 · Claude · Build · proof: tests green · size: S\n4. Merge Kit 1.1 · You · Check · stop: merge\n\n"
            "Technical details\n- none\n")


# 1 rules
RU = read(C, "rules", "CLAUDE-rules.md")
for ph in ("**Rule 0.**", "Value = 0.6 × time saved + 0.4 × tokens saved", "The main session is the lead",
           "copy it byte to byte at the start", "**Find all, fix all, check once**", "Workers do not wait for GitHub",
           "at most 2 jobs, under 5 minutes", "A rule with no measured gain in 2 reports is removed"):
    res(1, f"rules: {ph[:50]}", ph in RU)
res(1, "rules are about a quarter of the old size or less (words)", 0 < len(RU.split()) < 2500, len(RU.split()))

# 2-4 plan
P = proj("plan", planner=True)
open(os.path.join(P, "plans", "pass-v11-rev3.md"), "w", encoding="utf-8").write(plan("Plan v11 Rev 3"))
open(os.path.join(P, "WORKING_RECORD.md"), "w", encoding="utf-8").write(
    "## Design decisions\n- [agreed] [in v7] Old night check — search: Plan v7 in the morning\n- [agreed] [in v11] Kit first — search: Kit 1.1 everywhere\n\n## Next\n")
pf = os.path.join(P, "plans", "cur.md")
sent = plan("Plan v11 Rev 4", "- One pull request per round.\n")
open(pf, "w", encoding="utf-8").write(sent)
T = tx(os.path.join(V, "t.jsonl"), [user("show the Rev")])
o = hook("plan-guard.py", P, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T,
                               "tool_input": {"plan": sent, "planFilePath": pf}})
body = read(pf)
res(2, "the sent text has no marks: the session is asked to show the file's marked text", '"deny"' in o and
    "Read that file and show the plan again with exactly its text" in o, o[:250])
res(2, "  ...and the file holds the marks", any(s in body for s in SQ), body[:200])
o2 = hook("plan-guard.py", P, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T,
                                "tool_input": {"plan": body, "planFilePath": pf}})
res(2, "the marked text shown again passes (what you see = what you approve)", '"deny"' not in o2, o2[:250])
res(3, "a Rev is not sent to the planner", "planner helper writes" not in o + o2, (o + o2)[:200])
res(3, "points of an earlier approved plan ([in vN]) are not demanded", "Plan v7 in the morning" not in o + o2, o[:200])
res(4, "one colour line under 'What changed since'", re.search(r"(?m)^🎨 [🟦🟩🟧🟪] \*\*Rev 4\*\* marks \d+ changed lines?", body), body[:400])
res(4, "no change block made by the check in a Quick read plan", "Changes in this version" not in body, body[:300])

# 5 refusals that cost more than they save
P5 = proj("ref"); T5 = tx(os.path.join(V, "t5.jsonl"), [user("go")])
def bash(cmd, P=P5, agent=None, **kw):
    inp = {"tool_name": "Bash", "session_id": "r", "transcript_path": T5, "tool_input": {"command": cmd}}
    if agent:
        inp["agent_id"] = agent
    return hook("dispatch.py", P, dict(inp, hook_event_name="PreToolUse"), **kw)
res(5, "'sleep 5; cat x' runs", '"deny"' not in bash("sleep 5; cat x"), bash("sleep 5; cat x")[:200])
res(5, "'sleep 45' is still refused", '"deny"' in bash("sleep 45 && cat x"))
o = bash("grep -n Plan ~/.cache/hz-rules/CLAUDE-rules.md")
res(5, "a read-only shell read of the rules is allowed, not refused", '"deny"' not in o and '"allow"' in o, o[:200])
o = bash("git add WORKING_RECORD.md && git commit -m \"record notes\"")
res(5, "a notes-only commit gets [skip ci] added instead of a refusal", '"deny"' not in o and "record notes [skip ci]" in o, o[:250])
hv = {"subagent_type": "opus-worker", "prompt": "Task: x\nSize: M\nLevel: Complex\nComplex because: data model\nMap: not needed - t\n"
      "Worktree: none — main folder\nFiles: app.js:10-40\nTest: npm run test:failed\nSteps: 60"}
o = hook("worker-guard.py", P5, {"tool_name": "Agent", "session_id": "r", "transcript_path": T5, "tool_input": hv})
res(5, "'Worktree: none' is not refused", "needs no worktree" not in o, o[:200])
# a worker's full test run becomes its hand-over's fast test command (no refusal, no 8.3 minutes)
P5b = proj("full"); json.dump({"slowest_full_minutes": 8.3, "latest_full_minutes": 8.3}, open(os.path.join(P5b, ".claude", "state", "test-speed.json"), "w"))
open(os.path.join(P5b, "package.json"), "w").write('{"scripts":{"test":"node t.js"}}')
TW = tx(os.path.join(V, "tw.jsonl"), [user("Task: x\nFiles: app.js:10\nTest: npm run test:failed\nSteps: 60")])
o = hook("wait-guard.py", P5b, {"tool_name": "Bash", "session_id": "w", "agent_id": "w1", "transcript_path": TW,
                                 "tool_input": {"command": 'cd "D:/app" && npm test'}})
res(5, "a worker's full test run becomes its fast test command, not a refusal", '"deny"' not in o and
    'cd \\"D:/app\\" && npm run test:failed' in o, o[:250])
json.dump({"slowest_full_minutes": 8.3, "latest_full_minutes": 3.9}, open(os.path.join(P5b, ".claude", "state", "test-speed.json"), "w"))
o = hook("wait-guard.py", P5b, {"tool_name": "Bash", "session_id": "w", "transcript_path": TW, "tool_input": {"command": "npm test"}})
res(5, "once the latest full run is fast, full runs are not refused any more", '"deny"' not in o and "updatedInput" not in o, o[:200])
res(5, "the test-run notice is advice, not a refusal", 'deny_tool(f"You ran {tests} test runs' not in read(H, "worker-budget.py"))

# 6 hand-overs
o = hook("worker-guard.py", P5, {"tool_name": "Agent", "session_id": "r", "transcript_path": T5,
                                  "tool_input": {"subagent_type": "opus-worker", "prompt": "Task: x\nSize: M\nLevel: Complex\nComplex because: data model\nMap: not needed - t"}})
res(6, "a hand-over without Files lines, Test and Steps is refused", '"deny"' in o and "Files:" in o and "Test:" in o and "Steps:" in o, o[:250])
o = hook("worker-guard.py", P5, {"tool_name": "Agent", "session_id": "r", "transcript_path": T5, "tool_input": hv})
res(6, "a full hand-over passes", '"deny"' not in o, o[:250])
res(6, "the worker's step budget comes from its hand-over", "Steps:" in read(H, "worker-budget.py") and "warn = int(_sb.group(1))" in read(H, "worker-budget.py"))

# 7 GitHub waits
o = bash("timeout 600 gh run watch 123 --exit-status", agent="w1")
res(7, "a worker's GitHub wait is refused: hand back now", '"deny"' in o and "Do not wait for GitHub" in o, o[:200])
o = bash("timeout 600 gh run watch 123 --exit-status")
res(7, "the lead may read the run at the stop", "Do not wait for GitHub" not in o, o[:200])

# 8 send-backs
P8 = proj("stop"); subprocess.run("git add -A; git commit -qm code --allow-empty", shell=True, cwd=P8)
WAIT = ("Ready.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Waiting on your decision. Round 1 is built.\n"
        "> 👉 **I need from you:** Merge #1.\n> ➡️ **Next:** Round 2.")
T8 = tx(os.path.join(V, "t8.jsonl"), [user("go"), asst(tool("Bash", {"command": "git push origin claude/x"}, "p1")),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "p1", "content": "ok"}]}},
        asst(text(WAIT))])
o = hook("dispatch.py", P8, {"hook_event_name": "Stop", "session_id": "d", "transcript_path": T8})
res(8, "a send-back of missing actions asks for one line 'Done: …', not a second answer", '"block"' in o and "Done:" in o
    and "Do not write your answer again" in o, o[:300])
T8b = tx(os.path.join(V, "t8b.jsonl"), [user("go"), asst(text(WAIT)), user("Stop hook feedback: do it"),
         asst(tool("Bash", {"command": "gh pr checks 1"}, "c1")), asst(text("Done: checks read, green; notice sent."))])
o = hook("dispatch.py", P8, {"hook_event_name": "Stop", "session_id": "d2", "transcript_path": T8b, "stop_hook_active": True})
res(8, "'Done: …' passes the end-of-answer checks", '"block"' not in o, o[:250])
res(8, "the merge check remembers the last commit read green", "checks-read.json" in read(H, "merge-guard.py"))

# 9 retired and night
cfg = json.loads(read(H, "config.json"))
names = [x if isinstance(x, str) else x.get("script") for v in cfg["dispatch"].values() for x in v]
res(9, "report-timing and pr-ready-guard are retired", "report-timing.py" not in names and "pr-ready-guard.py" not in names)
o = hook("plan-gate.py", P5, {"session_id": "h", "prompt": "the timer is broken again"})
res(9, "the hotspot counter is gone", "hotspot" not in o and "+1 fix round" not in o, o[:200])
res(9, "the 9 PM reminder comes at the next step", "[evening]" in read(H, "notice-reminder.py"))

# 10 scorecard
S = os.path.join(V, "sc"); os.makedirs(S)
tx(os.path.join(S, "old.jsonl"), [user("old"), asst(text(WAIT))]); time.sleep(0.05)
tx(os.path.join(S, "new.jsonl"), [user("new"), asst(text(WAIT))])
sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", S], capture_output=True, text=True,
                    env=env(P5)).stdout
res(10, "the scorecard measures one session by default", "1 rounds" in sc or "in 1 rounds" in sc or "1 stops in 1" in sc, sc[:300])
res(10, "lead rows: reads, loops, GitHub waits, pushes, refused steps", all(x in sc for x in (
    "Worker steps that only read", "test → fix → test loops", "Workers waiting for GitHub", "Code pushes", "Refused steps")), sc[-300:])
res(10, "the end report carries rule rows (feedback loop)", "## Rule rows (feedback loop)" in read(H, "plan_report.py"))

shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
