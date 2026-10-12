#!/usr/bin/env python3
"""v3.2.17 item test. Usage: python3 tools/test_v3217_items.py <repo dir>
Items (owner, 12 Oct: 1A, 2B with fallback A after 1 trial, 3A, then A A):
 1 G1 the plan name is read with "Rev" in the title          2 G2 base = the newest saved plan (store or plans/)
 3 D1 a change after approval is the next Rev                 4 G3 old "[in vN]" points are a note, not a send-back
 5 G4 marks go into the plan file, never "allow"; fallback A after a failed trial
 6 G5 a waiting answer needs a notice that names what waits; "Notice sent." passes
 7 G6 tappable questions: notice first, recommended first, every option says what follows
 8 G7 the merge check counts checks read by a worker         9 G8 no switch back to draft
10 G9 the scorecard counts opened pull requests and adds the colour and notice lines
11 hook list and rules: AskUserQuestion in the app hook list (setup 3.2.17), rules lines
12 P03 end-of-answer checks read the final answer from the Stop input when the session file lags"""
import json, os, subprocess, sys, tempfile, shutil, time
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
results = []
SQ = "🟦🟩🟧🟪"


def res(item, name, ok, detail=""):
    ok = bool(ok); results.append((item, ok))
    print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))


def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""


def proj(name):
    P = os.path.join(V, name); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
    os.makedirs(os.path.join(P, ".claude", "agents"))
    open(os.path.join(P, ".claude", "agents", "planner.md"), "w").write("x")
    subprocess.run("git init -q", shell=True, cwd=P)
    return P


def env(P, **kw):
    e = dict(os.environ, CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1")
    for k in list(e):
        if k.startswith("HZ_") and k not in ("HZ_RULES_FIRST_OFF",):
            e.pop(k)
    e.update(kw); return e


def hook(script, P, inp, **kw):
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True,
                          env=env(P, **kw), cwd=P).stdout


def tx(path, recs):
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def user(t, ts="2026-10-12T10:00:00Z"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": t}}


def asst(*blocks, ts="2026-10-12T10:00:05Z"):
    return {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": list(blocks)}}


def tool(name, inp, i="t1"):
    return {"type": "tool_use", "id": i, "name": name, "input": inp}


def text(t):
    return {"type": "text", "text": t}


def plan(title, extra=""):
    return (f"# {title} — Pass — Awaiting approval\n\n**Quick read** · 40 words · about 1 min\n\n**Summary**\n- Goal: kit.\n"
            "- Done: 2 of 6.\n- I need from you: approve.\n\n**What changed since Rev 3**\n- Fewer stops.\n" + extra +
            "\n**Decisions:** None open.\n\n**Next steps**\n- Stage 3: maps.\n\nStages to finish\n2 stages: 1 build and 1 check by you.\n"
            "3. Kit 1.1 · Claude · Build · proof: tests green · size: S\n4. Merge Kit 1.1 · You · Check · stop: merge\n\n"
            "Technical details\n- none\n")


# ---- 1 G1
sys.path.insert(0, H)
try:
    import importlib, _common as _c
    importlib.reload(_c)
    n = _c.plan_name_of("# Plan v11 Rev 4 — Weekly-Planner consistency pass — Approved")
except Exception as ex:
    n = repr(ex)
res(1, "the plan name is read from '# Plan v11 Rev 4 — <name> — <status>'", n == "weekly-planner consistency pass", n)

# ---- 2-5: the 11 Oct case. Saved copy: Rev 1 (13:24); committed: Rev 3 (approved); shown: Rev 4 with "Rev" in the title
P = proj("plan")
open(os.path.join(P, "plans", "pass-v11-rev3.md"), "w", encoding="utf-8").write(plan("Plan v11 Rev 3"))
json.dump({"last": "pass", "plans": {"pass": {"version": 11, "rev": 1, "text": plan("Plan v11"), "approved": True,
                                              "history": [], "cur": {"rev": 1, "n": 0}}}},
          open(os.path.join(P, ".claude", "state", "plan-store.json"), "w", encoding="utf-8"))
open(os.path.join(P, "WORKING_RECORD.md"), "w", encoding="utf-8").write(
    "## Design decisions\n- [agreed] [in v7] Night check: plan in the morning — search: Plan v7 in the morning\n"
    "- [agreed] Fewer stops for the owner — search: Fewer stops\n\n## Next\n")
pf = os.path.join(P, "plans", "cur.md")
open(pf, "w", encoding="utf-8").write(plan("Plan v11 Rev 4", "- One pull request per round.\n"))
T = tx(os.path.join(V, "t_plan.jsonl"), [user("show the Rev")])
o = hook("plan-guard.py", P, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T,
                               "tool_input": {"plan": "x", "planFilePath": pf}})
body = read(pf)
res(2, "shown at once (no planner rewrite, no send-back)", '"deny"' not in o, o[:300])
res(2, "  ...compared with the committed Rev 3, not the old saved Rev 1", "Rev 4** — One pull request per round" in body
    and "Rev 4** — Fewer stops" not in body, body[:400])
res(3, "a change to the approved plan is its next Rev (no 'next version' send-back)", "next version" not in o and
    "**Rev 4**" in body, o[:200])
res(4, "an old '[in v7]' point is a note, not a send-back", "[earlier points]" in o and "Plan v7 in the morning" in o
    and '"deny"' not in o, o[:300])
res(5, "the marks are written into the plan file", any(s in body for s in SQ), body[:200])
res(5, "  ...and the check never answers 'allow' (the real program then approves without the owner)",
    '"allow"' not in o and "permissionDecision\": \"allow" not in read(H, "plan-guard.py").replace("'", '"'), o[:200])
# the trial: the plan Claude Code kept at the approval has no squares -> fallback A (one more showing)
st = json.load(open(os.path.join(P, ".claude", "state", "plan-store.json"), encoding="utf-8"))
T2 = tx(os.path.join(V, "t_plan2.jsonl"), [user("show the Rev"), asst(tool("ExitPlanMode", {}, "e1")),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "e1",
         "content": "User has approved your plan."}]}, "toolUseResult": {"plan": plan("Plan v11 Rev 4"), "filePath": pf}},
        user("change one more thing")])
open(pf, "w", encoding="utf-8").write(plan("Plan v11 Rev 5", "- One pull request per round.\n- A new line.\n"))
o2 = hook("plan-guard.py", P, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T2,
                                "tool_input": {"plan": "x", "planFilePath": pf}})
st2 = json.load(open(os.path.join(P, ".claude", "state", "plan-store.json"), encoding="utf-8"))
res(5, "a failed trial (approved plan without squares) switches to fallback A", st2.get("marks_mode") == "round"
    and "Show the plan again now. Change nothing." in o2, (st2.get("marks_mode"), o2[:200]))
# a passed trial keeps the file way
P5 = proj("plan5"); shutil.copy(os.path.join(P, "plans", "pass-v11-rev3.md"), os.path.join(P5, "plans"))
pf5 = os.path.join(P5, "plans", "cur.md"); open(pf5, "w", encoding="utf-8").write(plan("Plan v11 Rev 4", "- X.\n"))
hook("plan-guard.py", P5, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T,
                            "tool_input": {"plan": "x", "planFilePath": pf5}})
T5 = tx(os.path.join(V, "t_plan5.jsonl"), [user("x"), asst(tool("ExitPlanMode", {}, "e1")),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "e1",
         "content": "User has approved your plan."}]}, "toolUseResult": {"plan": read(pf5), "filePath": pf5}}, user("y")])
open(pf5, "w", encoding="utf-8").write(plan("Plan v11 Rev 5", "- X.\n- Y.\n"))
o5 = hook("plan-guard.py", P5, {"tool_name": "ExitPlanMode", "session_id": "s", "transcript_path": T5,
                                 "tool_input": {"plan": "x", "planFilePath": pf5}})
try:
    st5 = json.load(open(os.path.join(P5, ".claude", "state", "plan-store.json"), encoding="utf-8"))
except OSError:
    st5 = {}
res(5, "a passed trial keeps the marks in the file, with no extra showing", st5.get("marks_mode") == "file"
    and '"deny"' not in o5, (st5.get("marks_mode"), o5[:200]))

# ---- 6 G5 notice-guard and the switchboard
P6 = proj("notice")
WAIT = ("Round 1 is ready.\n\n**❓ Decisions**\n1. R1 keep? Recommend: keep. Ends here.\n2. R2 keep? Recommend: keep. Ends here.\n\n"
        "---\n> 📌 **Result:** Ready to merge.\n> 👉 **I need from you:** Answer R1–R2, then merge.\n> ➡️ **Next:** Round 2.")
def stop(script, recs, name, **kw):
    T6 = tx(os.path.join(V, name + ".jsonl"), recs)
    return hook(script, P6, {"hook_event_name": "Stop", "session_id": name, "transcript_path": T6}, **kw)
o = stop("notice-guard.py", [user("go"), asst(text(WAIT))], "n1")
res(6, "a waiting answer without a notice is sent back once", '"block"' in o and "Notice sent." in o, o[:200])
o = stop("notice-guard.py", [user("go"), asst(tool("PushNotification", {"message": "WP: pull request #149 is ready to merge"})),
                             asst(text(WAIT))], "n2")
res(6, "a notice that names only the merge, while questions wait, is sent back", '"block"' in o and "did not name" in o, o[:200])
o = stop("notice-guard.py", [user("go"), asst(tool("PushNotification", {"message": "WP: 2 questions + merge #149 waiting"})),
                             asst(text(WAIT))], "n3")
res(6, "a notice that names the questions passes", o.strip() == "", o[:200])
o = stop("dispatch.py", [user("go"), asst(text(WAIT)), user("Stop hook feedback: send the notice"),
                         asst(tool("PushNotification", {"message": "WP: 2 questions + merge waiting"})), asst(text("Notice sent."))], "n4")
res(6, "after the send-back, the line 'Notice sent.' passes every Stop check (no second answer)", '"block"' not in o, o[:200])
open(os.path.join(P6, "WORKING_RECORD.md"), "w").write("x")
o = stop("dispatch.py", [user("go"), asst(text(WAIT.replace("> 📌 ", "")))], "n5")
res(6, "when the notice is the only work problem, other problems are saved, not sent back with it",
    '"block"' in o and "Notice sent." in o and "Fix all of these" not in o, o[:300])
res(6, "the pull request notice asks to name everything that waits", "names everything in your 'I need" in read(H, "notice-reminder.py"))

# ---- 7 G6 ask-guard
P7 = proj("ask")
GOOD = {"questions": [{"question": "R1?", "header": "R1", "options": [
    {"label": "Keep (Recommended)", "description": "Nothing changes. Ends here."},
    {"label": "Change", "description": "A new picture. Brings back: one picture check."}]}]}
BAD = {"questions": [{"question": "R1?", "header": "R1", "options": [
    {"label": "Change", "description": "A new picture."}, {"label": "Keep (Recommended)", "description": "Nothing."}]}]}
def ask(recs, inp, name):
    T7 = tx(os.path.join(V, name + ".jsonl"), recs)
    return hook("ask-guard.py", P7, {"tool_name": "AskUserQuestion", "session_id": name, "transcript_path": T7,
                                      "tool_input": inp})
o = ask([user("go")], GOOD, "a1")
res(7, "questions without a notice first are refused", '"deny"' in o and "PushNotification" in o, o[:200])
o = ask([user("go"), asst(tool("PushNotification", {"message": "WP: 1 question waiting"}))], BAD, "a2")
res(7, "options without what follows, and the recommendation not first, are refused in one message",
    '"deny"' in o and "Ends here." in o and "(Recommended)" in o, o[:300])
o = ask([user("go"), asst(tool("PushNotification", {"message": "WP: 1 question waiting"}))], GOOD, "a3")
res(7, "a notice first and good options pass", o.strip() == "", o[:200])
res(7, "the question check is registered for AskUserQuestion", '"ask-guard.py"' in read(H, "config.json")
    and "AskUserQuestion" in read(H, "config.json"))

# ---- 8 G7 merge-guard with a worker's check reading
P8 = proj("merge"); subprocess.run("git config user.email t@t; git config user.name t; git add -A; git commit -qm code; mkdir -p docs; "
                                   "echo a > docs/r.md; git add docs; git commit -qm 'notes [skip ci]'", shell=True, cwd=P8)
sid = "m1"; tdir = os.path.join(V, "mt"); os.makedirs(os.path.join(tdir, sid, "subagents"))
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
MERGE = "Ready.\n\n---\n> 📌 **Result:** Ready to merge.\n> 👉 **I need from you:** Merge #149.\n> ➡️ **Next:** Round 2."
mt = tx(os.path.join(tdir, sid + ".jsonl"), [user("go", now), asst(tool("Bash", {"command": "git push origin claude/r1"}, "p1"), ts=now),
                                              asst(text(MERGE), ts=now)])
def mg():
    return hook("merge-guard.py", P8, {"hook_event_name": "Stop", "session_id": sid, "transcript_path": mt})
o = mg()
res(8, "without any check reading, the merge request is still sent back", '"block"' in o, o[:200])
tx(os.path.join(tdir, sid, "subagents", "agent-w.jsonl"), [asst(tool("Bash", {"command": "gh run watch 3828"}, "w1"), ts=now)])
o = mg()
res(8, "a worker read the checks and the main session pushed notes only: no send-back", o.strip() == "", o[:200])

# ---- 9 G8
P9 = proj("draft")
T9 = tx(os.path.join(V, "t9.jsonl"), [user("go")])
o = hook("git-guard.py", P9, {"tool_name": "Bash", "session_id": "d", "transcript_path": T9,
                               "tool_input": {"command": "git pull -q && gh pr ready 149 --undo"}})
res(9, "gh pr ready --undo is refused", '"deny"' in o and "stays ready" in o, o[:200])
o = hook("git-guard.py", P9, {"tool_name": "mcp__github__update_pull_request", "session_id": "d", "transcript_path": T9,
                               "tool_input": {"pullNumber": 149, "draft": True}})
res(9, "the GitHub tool's switch to draft is refused", '"deny"' in o, o[:200])
RULES = read(C, "rules", "CLAUDE-rules.md")
res(9, "the rule that told sessions to go back to draft is gone", "first switch it back to draft" not in RULES)

# ---- 10 G9 scorecard
S = os.path.join(V, "sc"); os.makedirs(S)
tx(os.path.join(S, "s.jsonl"), [user("go"),
    asst(tool("Bash", {"command": "gh pr create --fill"}, "c1")),
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1",
     "content": "PreToolUse:Bash hook error: git-guard: open the pull request when it is ready"}]}},
    asst(tool("Bash", {"command": "gh pr create --fill"}, "c2")),
    {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c2",
     "content": "https://github.com/o/r/pull/149"}]}},
    asst(text(MERGE)), asst(text(MERGE))])
sc = subprocess.run(["python3", os.path.join(H, "plan_report.py"), "--scorecard", S], capture_output=True, text=True).stdout
res(10, "a refused try is not counted as an opened pull request; a repeated answer is one stop",
    "1 pull requests opened, 1 merge stops" in sc, [l for l in sc.splitlines() if "Pull requests" in l])
res(10, "the scorecard shows colour on approved plans and notices for waiting answers",
    "Approved plans with colour marks" in sc and "Waiting answers with a notice" in sc, sc[-300:])

# ---- 11 hook list and rules
stub = read(C, "stub-files", "settings.json")
res(11, "the app hook list sends tappable questions to the checks", "ExitPlanMode|AskUserQuestion" in stub
    and "ExitPlanMode|AskUserQuestion" in read(R, "stub", "settings.json"))
res(11, "the setup check expects the 3.2.17 hook list", '"version": "3.2.17"' in read(H, "_common.py")
    and '"AskUserQuestion", "question check' in read(H, "_common.py"))
res(11, "rules: notice that names what waits; questions as taps with what follows; Rev after approval",
    "**Phone notice when you need me (Hook).**" in RULES and "**Questions as taps, with what follows (Hook).**" in RULES
    and "is its next Rev" in RULES)
# ---- 12 P03: the session file lags; the final answer is only in the Stop input
P12 = proj("lag"); subprocess.run("git config user.email t@t; git config user.name t; git add -A; git commit -qm code", shell=True, cwd=P12)
T12 = tx(os.path.join(V, "t12.jsonl"), [user("push it"), asst(tool("Bash", {"command": "git push origin claude/x"}, "p1")),
         {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "p1", "content": "ok"}]}}])
o = hook("dispatch.py", P12, {"hook_event_name": "Stop", "session_id": "lag", "transcript_path": T12,
                              "last_assistant_message": MERGE}, HZ_NOTICE_CHECK_OFF="1")
res(12, "a merge request that is only in the Stop input (file behind) is still checked and sent back",
    '"block"' in o and "read the checks" in o, o[:200])
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
