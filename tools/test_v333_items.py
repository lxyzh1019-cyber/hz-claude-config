#!/usr/bin/env python3
"""v3.3.3 item test (owner, 15 Oct). Usage: python3 tools/test_v333_items.py <repo dir> [<session file>]
 1 at Rev 2 the change list is written in words, with green and red lines per section and the colour line
 2 the no-objection line is added; the marked plan shown again passes; a first showing gets no block
 3 the second failing test run gets one "find all" note
 4 a ready pull request brings the report instruction, the measured table and the 3-line summary
 5 the time-and-token table by task and by model (real session file when given)
 6 rules and plan shape: decisions marked as made, no objection = recommended option, choices built not asked,
   report in the pull request, short summary with a link
 7 (16 Oct, fix 6) before the rules are read, steps that only read pass and steps that change something wait
 8 (16 Oct, "C") marks before showing: the marks go into the plan text when it is written, so the sent text holds
   them and no extra showing is needed; first showings, two writes, approvals and colour code are handled"""
import json, os, re, shutil, subprocess, sys, tempfile
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
SESSION = sys.argv[2] if len(sys.argv) > 2 else None
results = []


def res(i, n, ok, d=""):
    results.append((i, bool(ok))); print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {n}" + ("" if ok else f"  -> {str(d)[:200]!r}"))


def env(P, **kw):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(kw); return e


def hook(s, P, inp, **kw):
    return subprocess.run(["python3", os.path.join(H, s)], input=json.dumps(inp), capture_output=True, text=True, env=env(P, **kw), cwd=P).stdout


P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
subprocess.run("git init -q && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c", shell=True, cwd=P)
T = os.path.join(V, "t.jsonl"); open(T, "w").write('{"type":"user","message":{"role":"user","content":"x"}}\n')
pf = os.path.join(P, "plans", "cur.md")
R1 = ("# Plan v1 Rev 1 — Build 1a rest — Awaiting approval\n\n**Summary**\n- Goal: 9 items.\n- I need from you: answer 3 "
      "questions.\n\n**What changed since v0**\n- First version.\n\n**Decisions:**\n1. Three lakes open Apr 1–Nov 30: A both "
      "(ends here) · B early. Recommend A.\n\n**Stops**\n- Merge and phone check.\n")


def show(txt):
    open(pf, "w", encoding="utf-8").write(txt)
    return hook("plan-guard.py", P, {"session_id": "s", "transcript_path": T, "tool_name": "ExitPlanMode",
                                     "tool_input": {"plan": txt, "planFilePath": pf}})
o1 = show(R1)
f1 = open(pf, encoding="utf-8").read()
res(2, "a first showing gets no marks and no extra block", '"deny"' not in o1 and "🎨" not in f1, (o1[:150], f1[:150]))
R2 = R1.replace("answer 3 questions", "approve").replace(
    "1. Three lakes open Apr 1–Nov 30: A both (ends here) · B early. Recommend A.",
    "1. ✅ Decided: A — your answer at Rev 1.").replace("Rev 1 —", "Rev 2 —")
o2 = show(R2)
f2 = open(pf, encoding="utf-8").read()
res(1, "the change list is written in words under 'since Rev 1'", "**What changed since Rev 1**" in f2
    and "- 🎨 Summary: 1 new line, 1 removed" in f2 and "First version" not in f2, f2[:500])
res(1, "green and red lines per section", "```diff" in f2 and "@@ Decisions @@" in f2 and "+ 1. ✅ Decided: A" in f2
    and "- I need from you: answer 3 questions." in f2, f2[:600])
res(1, "the colour line names the Rev", re.search(r"🎨 🟩 \*\*Rev 2\*\* marks \d+ changed line", f2), f2[:400])
res(2, "the no-objection line is in the Decisions section",
    "If I receive no objection, I use the recommended option for each open decision." in f2)
o3 = show(f2)
res(2, "the marked plan shown again passes", '"deny"' not in o3, o3[:200])

# 3 find all
json.dump({}, open(os.path.join(P, ".claude", "state", "test-failures.json"), "w"))
def run_test(n):
    return hook("test-speed.py", P, {"session_id": "f", "tool_name": "Bash", "tool_input": {"command": "python3 -m unittest discover"},
                                     "tool_response": {"stdout": f"FAILED (failures={n})", "stderr": ""}})
a, b, c = run_test(1), run_test(2), run_test(1)
res(3, "the second failing test run gets the find-all note, once", "[find all]" not in a and "[find all]" in b
    and "[find all]" not in c, (a[:80], b[:80], c[:80]))

# 4 ready pull request
TT = SESSION or T
o = hook("notice-reminder.py", P, {"session_id": "r", "transcript_path": TT, "tool_name": "Bash",
                                    "tool_input": {"command": "gh pr create --fill"},
                                    "tool_response": {"stdout": "https://github.com/o/r/pull/12", "stderr": ""}})
res(4, "a ready pull request brings the report and the short summary", ("[report]" in o and "Report: <the pull request link>" in o)
    or not SESSION, o[:300])
res(4, "  ...with the measured table", ("| Task | Time | Tokens |" in o and "| Model | Tokens |" in o) or not SESSION, o[-300:])

# 5 the table
sys.path.insert(0, H)
try:
    from _common import session_table
except ImportError:
    session_table = None
res(5, "the time-and-token table exists", session_table is not None)
if SESSION and session_table:
    tab = session_table(SESSION) or ""
    res(5, "the table counts each message once and splits by model", re.search(r"tokens \d+(\.\d)? M", tab)
        and "| Model | Tokens |" in tab, tab[:300])
    print("     " + tab.split("\n")[0])

# 6 rules and plan shape
RU = open(os.path.join(C, "rules", "CLAUDE-rules.md"), encoding="utf-8").read()
FM = open(os.path.join(H, "formats.py"), encoding="utf-8").read()
SS = open(os.path.join(H, "session-start.py"), encoding="utf-8").read()
for ph, txt, where in (("✅ Decided: A — your answer at Rev n", RU, "rules"),
                       ("If I receive no objection, I use the recommended option for each open decision.", RU + FM, "rules and plan shape"),
                       ("A choice that has a recommendation and can be undone is built with it and listed, not asked.", RU, "rules"),
                       ("**The report is the pull request text**", RU, "rules"),
                       ("**The chat summary is short:**", RU, "rules"),
                       ("Pick a check's inputs (lakes, dates, users) from the data in one step", RU, "rules"),
                       ("keeps its plan in the pull request text", SS, "session start")):
    res(6, f"{where}: {ph[:60]}", ph in txt)
# 7 fix 6: read-only steps never wait for the rules; changes still do (real program: tools/real-harness/scenario_v333_rules_first.sh)
def rf(tool, inp, sid="rf7"):
    return hook("rules-first-guard.py", P, {"session_id": sid, "tool_name": tool, "tool_input": inp}, HZ_RULES_FIRST_OFF="")
for cmd in ("git status && git log --oneline -3", "git -C ../x diff HEAD~1", "ls -la | head", "gh pr view 12", "git branch -a"):
    o = rf("Bash", {"command": cmd}); res(7, f"read-only step passes: {cmd}", '"deny"' not in o, o[:160])
o = rf("mcp__github__get_file_contents", {}); res(7, "a read-only MCP call passes", '"deny"' not in o, o[:160])
for cmd in ("git checkout test-333", "git status && git commit -m x", "cat a > b", "ls $(rm -rf x)", "find . -delete",
            "PAGER=sh git log", "git fetch origin", "npm test"):
    o = rf("Bash", {"command": cmd}); res(7, f"a change still waits for the rules: {cmd}", "Read the working rules first" in o, o[:160])
o = rf("Edit", {"file_path": "a.js"}); res(7, "an edit still waits for the rules", "Read the working rules first" in o, o[:160])

# 8 "C": marks before showing (real program: tools/real-harness/scenario_v333_mark_plan.py)
def p8(name):
    Q = os.path.join(V, name); os.makedirs(os.path.join(Q, ".claude", "state")); os.makedirs(os.path.join(Q, "plans"))
    subprocess.run("git init -q && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c", shell=True, cwd=Q)
    return Q, os.path.join(Q, "plans", "cur.md")
def exit_plan(Q, f, tr=T):
    sent = open(f, encoding="utf-8").read()       # the desktop app sends the text it has; it is the file's text
    return hook("plan-guard.py", Q, {"session_id": "s8", "transcript_path": tr, "tool_name": "ExitPlanMode",
                                     "tool_input": {"plan": sent, "planFilePath": f}})
def write(Q, f, content, tr=T):
    """The Write step through the switchboard; returns the text that lands in the file and the raw answer."""
    o = hook("dispatch.py", Q, {"hook_event_name": "PreToolUse", "session_id": "s8", "transcript_path": tr,
                                "tool_name": "Write", "tool_input": {"file_path": f, "content": content}})
    try:
        hs = json.loads(o).get("hookSpecificOutput") or {}
    except ValueError:
        hs = {}
    if hs.get("permissionDecision") == "deny":
        return None, o
    final = (hs.get("updatedInput") or {}).get("content", content)
    open(f, "w", encoding="utf-8").write(final)
    return final, o
# before C: the plan written as is costs one extra showing at the showing
Qa, fa = p8("c-before")
open(fa, "w", encoding="utf-8").write(R1); exit_plan(Qa, fa)
open(fa, "w", encoding="utf-8").write(R2); o = exit_plan(Qa, fa)
res(8, "before C: a changed plan written without marks costs one extra showing", "show the plan again" in o, o[:160])
o = exit_plan(Qa, fa)
res(8, "  ...and the marked plan shown again then passes (the uploaded 3.3.3 refused it again in the real program)",
    '"deny"' not in o, o[:160])
# the real-program case: Rev 2 of an approved, committed Plan v1 with a Quick read line (16 Oct: refused twice)
_hs = open(os.path.join(R, "tools", "real-harness", "scenario_v3217.py"), encoding="utf-8").read()
_g = {}; exec(_hs[_hs.index("SQ = "):_hs.index('if "window" in WANT:')], _g)
Qe, fe = p8("c-real"); open(os.path.join(Qe, "plans", "test-v1.md"), "w", encoding="utf-8").write(_g["PLAN1"])
open(fe, "w", encoding="utf-8").write(_g["PLAN2"]); o1 = exit_plan(Qe, fe); o2 = exit_plan(Qe, fe)
res(8, "  ...also for an approved plan with a Quick read line: one extra showing, then it passes",
    "show the plan again" in o1 and '"deny"' not in o2, (o1[:120], o2[:160]))
Qf, ff = p8("c-real-write"); open(os.path.join(Qf, "plans", "test-v1.md"), "w", encoding="utf-8").write(_g["PLAN1"])
w6, o = write(Qf, ff, _g["PLAN2"])
res(8, "  ...and with C its first showing passes", w6 and "🟩" in w6 and '"deny"' not in exit_plan(Qf, ff), o[:160])
# with C
Qb, fb = p8("c-after")
w1, o = write(Qb, fb, R1)
res(8, "a first plan: the write is not changed", w1 == R1 and "updatedInput" not in o, o[:160])
res(8, "  ...and the first showing passes as before", '"deny"' not in exit_plan(Qb, fb))
w2, o = write(Qb, fb, R2)
res(8, "a changed plan: the marks go into the text when it is written", w2 and "🟩" in w2 and "**What changed since Rev 1**" in w2
    and "```diff" in w2 and '"allow"' in o, (o[:200], (w2 or "")[:300]))
R2b = R2.replace("- Merge and phone check.", "- Merge and one phone check.")
w2b, o = write(Qb, fb, R2b)
res(8, "a second write before the showing stays Rev 2 (not Rev 3)", w2b and "🟩" in w2b and "🟧" not in w2b
    and "Rev 3" not in w2b and "phone check" in w2b, (w2b or "")[:400])
o = exit_plan(Qb, fb)
res(8, "the showing sends the marked text and passes: no extra showing", '"deny"' not in o, o[:200])
res(8, "  ...and the file still holds the marks", "🟩" in open(fb, encoding="utf-8").read())
w2c, o = write(Qb, fb, open(fb, encoding="utf-8").read())
res(8, "writing the shown plan again changes nothing", w2c == open(fb, encoding="utf-8").read() and "updatedInput" not in o, o[:160])
# after your Approve: a change is the next Rev
TA = os.path.join(V, "approved.jsonl")
with open(TA, "w", encoding="utf-8") as h:
    h.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "e1", "name": "ExitPlanMode", "input": {}}]}}) + "\n")
    h.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "e1", "content": "User has approved your plan. You can now start."}]}}) + "\n")
sys.path.insert(0, H)
import planmarks as _PM8
R3 = _PM8.strip_marks(open(fb, encoding="utf-8").read()).replace("- Merge and one phone check.", "- Merge only.").replace("Rev 2 —", "Rev 3 —")
w3, o = write(Qb, fb, R3, tr=TA)
res(8, "a change after your Approve is marked as the next Rev", w3 and "🟧" in w3 and "Rev 3" in w3, (o[:200], (w3 or "")[:400]))
res(8, "  ...and its showing passes with no extra showing", '"deny"' not in exit_plan(Qb, fb, tr=TA))
# colour code: the write goes ahead unmarked, and the showing sends it back as before
Qd, fd = p8("c-html"); write(Qd, fd, R1); exit_plan(Qd, fd)
bad = R2.replace("- Merge and phone check.", '- <span style="color:red">Merge</span> and phone check.')
w4, o = write(Qd, fd, bad)
res(8, "a plan with colour code is written as it is", w4 == bad, o[:160])
res(8, "  ...and its showing is sent back as before", "colour code" in exit_plan(Qd, fd))
# not a plan file: never touched
Qc, _ = p8("c-other"); fo = os.path.join(Qc, "notes.md")
w5, o = write(Qc, fo, R2)
res(8, "a Write outside plans/ is never changed", w5 == R2 and "updatedInput" not in o, o[:160])
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
