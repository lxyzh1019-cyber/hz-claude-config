#!/usr/bin/env python3
"""v3.3.2 item test ("default first", owner 13 Oct). Usage: python3 tools/test_v332_items.py <repo dir>
 1 the switchboard runs only the kept checks; HZ_FULL_RULES=1 brings the old method back for tests
 2 the session may build itself: editing app code and handing over without the old format pass
 3 plans: no shape, coverage or planner send-back; colour marks and the marked-text showing stay; colour code is caught
 4 waits: sleeps, polling and GitHub waits pass; only the slow full suite is still handled
 5 the closing block is checked only after real work
 6 the prompt check adds no plan tier, planner or reviewer demand; night words still work
 7 the rules: default first, small job, bigger job, one review pass, design file first"""
import json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
results = []
SQ = "🟦🟩🟧🟪"


def res(i, n, ok, d=""):
    results.append((i, bool(ok))); print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {n}" + ("" if ok else f"  -> {str(d)[:200]!r}"))


def proj(name):
    P = os.path.join(V, name); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
    subprocess.run("git init -q && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c && git switch -qc claude/x", shell=True, cwd=P)
    return P


def env(P, **kw):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(kw); return e


def hook(s, P, inp, **kw):
    return subprocess.run(["python3", os.path.join(H, s)], input=json.dumps(inp), capture_output=True, text=True, env=env(P, **kw), cwd=P).stdout


def tx(p, recs):
    open(p, "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)); return p


def ts(m):
    return (datetime.now(timezone.utc) - timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ")


def user(t, m=1):
    return {"type": "user", "timestamp": ts(m), "message": {"role": "user", "content": t}}


def asst(*b, m=0):
    return {"type": "assistant", "timestamp": ts(m), "message": {"role": "assistant", "content": list(b)}}


def tool(n, i, id_="t1"):
    return {"type": "tool_use", "id": id_, "name": n, "input": i}


def text(t):
    return {"type": "text", "text": t}


cfg = json.load(open(os.path.join(H, "config.json"), encoding="utf-8"))
names = [x if isinstance(x, str) else x.get("script") for v in cfg["dispatch"].values() for x in v]
gone = ("routing-guard.py", "worker-guard.py", "worker-budget.py", "record-guard.py", "record-edit-guard.py",
        "completion-guard.py", "handoff-guard.py", "report-early.py")
res(1, "the 8 removed checks are not run by default", not any(g in names for g in gone), [g for g in gone if g in names])
res(1, "the kept checks still run (git, plan, questions, wake-ups, merge, safety, notice)", all(k in names for k in (
    "git-guard.py", "plan-guard.py", "ask-guard.py", "wake-guard.py", "merge-guard.py", "qc-guard.py", "notice-guard.py")))
res(1, "HZ_FULL_RULES=1 brings the old method back", "dispatch_full" in cfg and "routing-guard.py" in json.dumps(cfg["dispatch_full"]))

P = proj("a"); T = tx(os.path.join(V, "t.jsonl"), [user("build the 9 items")])
def pre(tool_name, inp, P=P, T=T, **kw):
    return hook("dispatch.py", P, {"hook_event_name": "PreToolUse", "session_id": "s", "transcript_path": T, "tool_name": tool_name, "tool_input": inp}, **kw)
o = pre("Edit", {"file_path": os.path.join(P, "index.html"), "old_string": "a", "new_string": "b"})
res(2, "the session may edit app code itself", '"deny"' not in o, o[:200])
o = pre("Agent", {"subagent_type": "opus-worker", "prompt": "Do stage 1."})
res(2, "a hand-over in plain words is not refused", '"deny"' not in o, o[:200])
o = pre("Edit", {"file_path": os.path.join(P, "index.html"), "old_string": "a", "new_string": "b"}, HZ_FULL_RULES="1")
res(1, "  ...and with HZ_FULL_RULES=1 the old 'lead never edits' rule is back", '"deny"' in o, o[:150])

PLAN0 = "# Plan v1 — Pass — Approved\n\nSummary: goal kit.\n\n- Stage 1: LINE-A.\n- Stage 2: LINE-B.\n"
open(os.path.join(P, "plans", "pass-v1.md"), "w", encoding="utf-8").write(PLAN0)
pf = os.path.join(P, "plans", "cur.md")
sent = PLAN0.replace("Approved", "Awaiting approval").replace("# Plan v1 —", "# Plan v1 Rev 2 —").replace("LINE-B.", "LINE-B, now green.")
open(pf, "w", encoding="utf-8").write(sent)
o = pre("ExitPlanMode", {"plan": sent, "planFilePath": pf})
res(3, "a short plan without the old shape is not sent back for its shape", "Quick read" not in o and "Stages to finish" not in o, o[:250])
res(3, "the colour marks are still added, and the marked text is shown", any(s in open(pf, encoding="utf-8").read() for s in SQ)
    and "Read that file and show the plan again" in o, o[:250])
_fc = sent.replace("LINE-A", '<font color="red">LINE-A</font>')
open(pf, "w", encoding="utf-8").write(_fc)
o = pre("ExitPlanMode", {"plan": _fc, "planFilePath": pf})
res(3, "colour code in a plan is still caught", "colour code" in o, o[:200])

o = pre("Bash", {"command": "sleep 45 && gh run watch 123"})
res(4, "a sleep and a GitHub wait are not refused", '"deny"' not in o, o[:200])
json.dump({"slowest_full_minutes": 8.3, "latest_full_minutes": 8.3}, open(os.path.join(P, ".claude", "state", "test-speed.json"), "w"))
open(os.path.join(P, "package.json"), "w").write('{"scripts":{"test":"node t.js"}}')
o = pre("Bash", {"command": "npm test"})
res(4, "a full suite measured slow is still handled", '"deny"' in o or "updatedInput" in o, o[:200])

BAD = "Done the copy.\n\nResult: copied."
T5 = tx(os.path.join(V, "t5.jsonl"), [user("copy the log"), asst(tool("Bash", {"command": "ls"}, "b1")), asst(text(BAD))])
o = hook("dispatch.py", P, {"hook_event_name": "Stop", "session_id": "v1", "transcript_path": T5})
res(5, "a turn without real work is not checked for the closing block", '"block"' not in o and "closing" not in o.lower(), o[:200])
T6 = tx(os.path.join(V, "t6.jsonl"), [user("build"), asst(tool("Edit", {"file_path": "a.js", "old_string": "a", "new_string": "b"}, "e1")), asst(text(BAD))])
o = hook("validation-line.py", P, {"hook_event_name": "Stop", "session_id": "v2", "transcript_path": T6})
res(5, "a turn with real work is still checked", o.strip() != "", o[:200])

o = hook("plan-gate.py", P, {"session_id": "g", "prompt": "Please do:\n- a\n- b\n- c\n- d"})
res(6, "no plan tier, planner or reviewer demand", not re.search(r"plan-gate\]|\[planner\]|\[reviewer\]", o), o[:200])
o = hook("plan-gate.py", P, {"session_id": "g2", "prompt": "good night"})
res(6, "the night words still work", "[night]" in o, o[:200])

RU = open(os.path.join(C, "rules", "CLAUDE-rules.md"), encoding="utf-8").read()
for ph in ("## 1. Default first", "## 2. Small job (one pull request)", "## 3. Bigger job (a new app, many sessions)",
           "**One review pass before my merge:**", "**My design file first.**", "**Rule 0.**",
           "An artefact (record file, report, picture, test tool) is made only when a later reader exists"):
    res(7, f"rules: {ph[:55]}", ph in RU)
res(7, "the lead-and-workers rules are gone", "The main session is the lead" not in RU and "Exact hand-overs" not in RU)
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
