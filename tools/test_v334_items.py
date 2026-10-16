#!/usr/bin/env python3
"""v3.3.4 item test (owner, 16 Oct: "build 3.3.4 A"). Usage: python3 tools/test_v334_items.py <repo dir> [<session file>]
From the 3.3.3 runs #13 (local) and #14 (cloud):
 1 P1  a plan changed with Edit or MultiEdit gets its marks when written; its showing passes
 2 P2  default first names only the reviewer role file; the main session builds
 3 P3  the pull request opens without a GitHub wait; merge-guard wants one check read (gh or the GitHub tool)
 4 P4  the measured time counts helper time and shows my time apart (real session file when given)
 5 P5  the approved plan for the report: titled Approved, marks removed; the report file is written
 6 P6  the skill router is silent on a build request and speaks when a skill is named
 7 P7  a cd to the current folder before git is dropped; another cd before git is refused; risky never auto-allowed
 8 P8  default first asks nothing about the feature list, test map, references or working record
 9 P9, O1, O3, O5  rules: browser pictures in the chat, workflow on pull requests, changed tests locally, read by parts
10 P10 plans/ is in the local git ignore list after the session start
11 P11 hook texts name the GitHub tool for cloud sessions
12 P12 the measured part has the checkpoint parts: time sinks, token sinks, scorecard, totals, slowest steps
13 O2  the change box has at most 8 lines and shows a decided question once"""
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
    return subprocess.run(["python3", os.path.join(H, s)], input=json.dumps(inp), capture_output=True, text=True,
                          env=env(P, **kw), cwd=P).stdout


def proj(name):
    P = os.path.join(V, name); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
    subprocess.run("git init -q -b main && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c",
                   shell=True, cwd=P)
    return P


T = os.path.join(V, "t.jsonl"); open(T, "w").write('{"type":"user","message":{"role":"user","content":"x"}}\n')
R1 = ("# Plan v1 Rev 1 — Build — Awaiting approval\n\n**Summary**\n- Goal: 9 items.\n\n**What changed since v0**\n"
      "- First version.\n\n**Decisions:**\n1. Lakes open Apr 1–Nov 30: A both (ends here) · B early. Recommend A.\n"
      "2. Count: A data (ends here) · B as asked. Recommend A.\n\n**Stops**\n- Merge and phone check.\n")
R2 = R1.replace("Rev 1 —", "Rev 2 —").replace("1. Lakes open Apr 1–Nov 30: A both (ends here) · B early. Recommend A.",
                                               "1. ✅ Decided: A — your answer at Rev 1").replace(
    "2. Count: A data (ends here) · B as asked. Recommend A.", "2. ✅ Decided: A — your answer at Rev 1")


def exit_plan(P, f):
    return hook("plan-guard.py", P, {"session_id": "s", "transcript_path": T, "tool_name": "ExitPlanMode",
                                     "tool_input": {"plan": open(f, encoding="utf-8").read(), "planFilePath": f}})


def dispatch(P, tool, inp, **kw):
    return hook("dispatch.py", P, dict({"hook_event_name": "PreToolUse", "session_id": "s", "transcript_path": T,
                                        "tool_name": tool, "tool_input": inp}, **kw))


# 1 P1
for tool in ("Edit", "MultiEdit"):
    P = proj("p1" + tool); f = os.path.join(P, "plans", "cur.md"); open(f, "w", encoding="utf-8").write(R1); exit_plan(P, f)
    old, new = "1. Lakes open Apr 1–Nov 30: A both (ends here) · B early. Recommend A.", "1. ✅ Decided: A — your answer at Rev 1"
    inp = {"file_path": f, "old_string": old, "new_string": new} if tool == "Edit" else \
        {"file_path": f, "edits": [{"old_string": old, "new_string": new}, {"old_string": "Rev 1 —", "new_string": "Rev 2 —"}]}
    if tool == "Edit":
        open(f, "w", encoding="utf-8").write(R1.replace("Rev 1 —", "Rev 2 —"))
    o = dispatch(P, tool, inp)
    try:
        u = json.loads(o)["hookSpecificOutput"]["updatedInput"]
        after = u["new_string"] if tool == "Edit" else u["edits"][0]["new_string"]
        whole = (u["old_string"] if tool == "Edit" else u["edits"][0]["old_string"]) == open(f, encoding="utf-8").read()
    except (ValueError, KeyError, TypeError):
        after, whole = "", False
    res(1, f"{tool} of a changed plan: one edit writes the whole marked text", "🟩" in after and whole, o[:200])
    if after:
        open(f, "w", encoding="utf-8").write(after)
    o = exit_plan(P, f)
    res(1, f"  ...and the {tool} showing passes with no extra showing", '"deny"' not in o and after, o[:160])
res(1, "the plan check's show-again text says not to write the plan in the chat",
    "Do not write the plan in the chat" in open(os.path.join(H, "plan-guard.py"), encoding="utf-8").read())

# 2 P2 and 8 P8 (session start, default first)
P = proj("p2"); open(os.path.join(P, "FEATURES.md"), "w").write("# <app or plan name>\n"); open(os.path.join(P, "index.html"), "w").write("<p>")
o = hook("session-start.py", P, {"session_id": "s2", "hook_event_name": "SessionStart", "source": "startup"})
ctx = json.loads(o)["hookSpecificOutput"]["additionalContext"] if o.strip() else ""
res(2, "default first names only the reviewer role file", "reviewer-instructions.md" in ctx and "opus-worker-instructions" not in ctx, ctx[:300])
res(2, "  ...and says the main session builds", "You build in this session" in ctx, ctx[:300])
res(8, "no feature-list, test-map, references or record notes", not re.search(r"test map|picture references|still the template|Missing files", ctx), ctx[:400])
o = hook("session-start.py", P, {"session_id": "s2b", "hook_event_name": "SessionStart", "source": "startup"}, HZ_FULL_RULES="1")
ctx2 = json.loads(o)["hookSpecificOutput"]["additionalContext"] if o.strip() else ""
res(8, "  ...the full method still has them (HZ_FULL_RULES=1)", "opus-worker-instructions" in ctx2 and "still the template" in ctx2, ctx2[:200])
res(10, "plans/ is in the local git ignore list", "plans/" in open(os.path.join(P, ".git", "info", "exclude")).read())
open(os.path.join(P, "plans", "x.md"), "w").write("# Plan v1\n")
st = subprocess.run(["git", "status", "--short"], cwd=P, capture_output=True, text=True).stdout
res(10, "  ...so an untracked plan file is not shown as a change", "plans" not in st, st)
hook("session-start.py", P, {"session_id": "s2c", "hook_event_name": "SessionStart", "source": "startup"})
res(10, "  ...added once, not again at the next start", open(os.path.join(P, ".git", "info", "exclude")).read().count("plans/") == 1)

# 3 P3 and 11 P11
P = proj("p3"); os.makedirs(os.path.join(P, ".github", "workflows")); open(os.path.join(P, ".github", "workflows", "t.yml"), "w").write("on:\n  push:\n  pull_request:\n")
subprocess.run("git switch -qc feat && git commit -q --allow-empty -m w", shell=True, cwd=P)
T3 = os.path.join(V, "t3.jsonl")
with open(T3, "w") as h:
    h.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "p", "name": "Bash", "input": {"command": "git push -u origin feat"}}]}}) + "\n")
    h.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "p", "content": "ok"}]}}) + "\n")
o = hook("git-guard.py", P, {"session_id": "s3", "transcript_path": T3, "tool_name": "Bash", "cwd": P,
                             "tool_input": {"command": "gh pr create --base main --head feat --fill"}})
res(3, "the pull request opens without a GitHub wait first", "wait for GitHub's tests" not in o, o[:200])
MG = open(os.path.join(H, "merge-guard.py"), encoding="utf-8").read()
res(3, "merge-guard reads the GitHub tool's check status (cloud)", "create_pull_request|push_files" in MG and "workflow_run" in MG)
res(11, "merge-guard and the report notice name the GitHub tool for the cloud",
    "the GitHub tool" in MG and "the GitHub tool" in open(os.path.join(H, "notice-reminder.py"), encoding="utf-8").read())

# 4 P4 and 12 P12
sys.path.insert(0, H)
try:
    import pr_report
except ImportError:
    pr_report = None
res(12, "the report module exists", pr_report is not None)
if pr_report and SESSION:
    mp = pr_report.measured_part(SESSION, V) or ""
    res(4, "helper time is counted (the 12-minute build helper)", re.search(r"helper: opus-worker \| 1[0-9]\.\d min", mp), mp[:600])
    res(4, "my time is shown apart from time worked", "| Your time (answers, approvals) | 5" in mp, mp[-900:])
    res(4, "time worked is within 2 minutes of the clock minus my time (34.2 - 5.9)",
        (lambda w: w and abs(float(w.group(1)) - 28.3) <= 2)(re.search(r"Worked \(your time and pauses left out\) \| ([\d.]+)", mp)), mp[-900:])
    for part in ("### Top 3 time sinks", "### Top 3 token sinks", "### Scorecard (default first)", "### Totals",
                 "**Slowest steps", "| Build helpers (0 unless parallel parts) | 1 |", "| Pull request refused (0) | 2 |",
                 "| test runs |"):
        res(12, f"the measured part has '{part}'", part in mp, mp[:300])
elif not SESSION:
    print("    (items 4 and 12 need the real session file for the measured checks)")

# 5 P5
P = proj("p5"); f = os.path.join(P, "plans", "cur.md"); open(f, "w", encoding="utf-8").write(R1); exit_plan(P, f)
open(f, "w", encoding="utf-8").write(R2); exit_plan(P, f); exit_plan(P, f)
code = ("import sys,os,json;sys.path.insert(0,sys.argv[1]);os.chdir(sys.argv[2]);import pr_report as p;"
        "print(json.dumps(p.approved_plan()))")
o = subprocess.run(["python3", "-c", code, H, P], capture_output=True, text=True, env=env(P)).stdout if pr_report else ""
try:
    plan, rev = json.loads(o)
except ValueError:
    plan, rev = "", None
res(5, "the approved plan is titled Approved, with no marks", plan and "Approved" in plan.split("\n")[0]
    and not re.search("[🟦🟩🟧🟪]|```diff", plan), o[:200])
T5 = os.path.join(V, "t5.jsonl"); shutil.copy(SESSION, T5) if SESSION else open(T5, "w").write(open(T).read())
o = hook("notice-reminder.py", P, {"session_id": "s5", "transcript_path": T5, "tool_name": "Bash",
                                   "tool_input": {"command": "gh pr create --fill"}, "tool_response": {"stdout": "https://github.com/o/r/pull/9"}})
rf = os.path.join(P, ".claude", "state", "pr-report.md")
res(5, "the report file holds the approved plan in a fold-out", os.path.exists(rf) and "Approved plan (Rev" in open(rf, encoding="utf-8").read()
    or not SESSION, o[:200])
res(12, "the notice asks for the checkpoint shape and the file as it is", ("## Quick read" in o and "pr-report.md" in o) or not SESSION, o[:300])

# 6 P6
o = hook("skill-router.py", V, {"session_id": "s6", "prompt": "Build the rest of Build 1a. Keep the tests passing and review it."})
res(6, "the router is silent on a build request", not o.strip(), o[:200])
o = hook("skill-router.py", V, {"session_id": "s6", "prompt": "use hz-reviewer: review the index.html"})
res(6, "  ...and speaks when I name a skill", "hz-reviewer" in o, o[:200])

# 7 P7
def gg(cmd, cwd):
    return hook("git-guard.py", V, {"session_id": "s7", "tool_name": "Bash", "cwd": cwd, "tool_input": {"command": cmd}})
o = gg('cd "D:/User/Heng Z/Documents/GitHub/HZ_Trout_Map" && git push -u origin test-333-local', "D:\\User\\Heng Z\\Documents\\GitHub\\HZ_Trout_Map")
res(7, "the real local command: the cd to the current folder is dropped", '"git push -u origin test-333-local"' in o and '"allow"' in o, o[:200])
o = gg("cd .. && git add index.html", "/repo/scripts")
res(7, "the real cloud command: another cd before git is refused with the two steps", "own step" in o and '"deny"' in o, o[:200])
o = gg("cd /repo && git push --force origin feat", "/repo")
res(7, "a risky command is never allowed without the prompt", '"allow"' not in o, o[:200])
o = gg("git status", "/repo")
res(7, "git alone is untouched", not o.strip(), o[:200])

# 9 rules
RU = open(os.path.join(C, "rules", "CLAUDE-rules.md"), encoding="utf-8").read()
for ph in ("Those pictures stay visible in the chat.", "pull requests and pushes to main only",
           "Locally, run only the tests of the changed parts.", "Read a file over 1,000 lines by parts",
           "Never put `cd` and `git` in one Bash step", "the browser pictures first",
           "a helper builds only parts that run side by side on separate files"):
    res(9, f"rules: {ph[:60]}", ph in RU)

# 13 O2
P = proj("o2"); f = os.path.join(P, "plans", "cur.md")
big = R1 + "".join(f"\n**Part {k}**\n- line {k} old\n" for k in range(10))
open(f, "w", encoding="utf-8").write(big); exit_plan(P, f)
open(f, "w", encoding="utf-8").write(R2 + "".join(f"\n**Part {k}**\n- line {k} new\n" for k in range(10))); exit_plan(P, f)
txt = open(f, encoding="utf-8").read()
box = re.search(r"```diff\n(.*?)```", txt, re.S)
lines = [l for l in (box.group(1).split("\n") if box else []) if l.strip() and not l.startswith("@@")]
res(13, "the change box has at most 9 lines (8 and one '… more')", box and len(lines) <= 9, lines)
res(13, "a decided question is shown once (no red copy of it)", box and not re.search(r"(?m)^- 1\. Lakes open", box.group(1)), box.group(1)[:300] if box else txt[:300])

shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
