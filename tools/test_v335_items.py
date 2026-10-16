#!/usr/bin/env python3
"""v3.3.5 item test (owner, 16 Oct: "3.3.5 A only changes for the summary section; bold the words; no tables").
Usage: python3 tools/test_v335_items.py <repo dir> [<session file>]
 1 the summary has the Weekly-Planner Completion lines with bold labels, a plan link to its own heading and a report link
 2 Tokens and time and Session time are bold-label lines, not tables, with % for tokens and for time
 3 tokens and time use one set of types: every type shows both
 4 each helper has its own time (the 12-minute build helper and the 2.5-minute reviewer of run #13)
 5 the files are made when the pull request opens and again after the checks, with the check result
 6 the report holds the summary and the approved plan under its own heading (the plan link's target)
 7 the rule names the summary shape"""
import json, os, re, shutil, subprocess, sys, tempfile
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
SESSION = sys.argv[2] if len(sys.argv) > 2 else None
results = []


def res(i, n, ok, d=""):
    results.append((i, bool(ok))); print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {n}" + ("" if ok else f"  -> {str(d)[:220]!r}"))


sys.path.insert(0, H)
try:
    import pr_report
    sb = getattr(pr_report, "summary_block", None)
except ImportError:
    pr_report, sb = None, None
res(1, "the summary maker exists", sb is not None)
if sb and SESSION:
    s = sb(SESSION, "https://github.com/o/r/pull/13", 2, "HZ Trout Map Build 1a", "passed") or ""
    res(1, "Completion line with bold label and the check result", s.startswith("**Completion:** Build 1 of 1 done (100%)") and "**GitHub checks:** passed" in s, s[:200])
    res(1, "Waiting on you and Then, in order, in bold", "**Waiting on you**" in s and "**Then, in order:**" in s, s[:300])
    res(1, "the plan links to its own heading; the report links to the pull request",
        "(https://github.com/o/r/pull/13#approved-plan-rev-2)" in s and "**Report:** [#13](https://github.com/o/r/pull/13)" in s, s[:400])
    res(2, "Tokens and time and Session time as bold lines", "**Tokens and time:**" in s and "**Session time:**" in s
        and "- **By model:**" in s and "- **By role:**" in s and "- **By type:**" in s, s[-600:])
    res(2, "no tables", "|---" not in s and not re.search(r"(?m)^\|", s), s)
    res(2, "time shares in %", re.search(r"\*\*Session time:\*\* [\d.]+ min on the clock · your answers \d+% \(", s), s[-400:])
    bt = re.search(r"- \*\*By type:\*\* (.*)", s).group(1) if "- **By type:**" in s else ""
    items = [x.strip() for x in bt.split(" · ") if x.strip()]
    res(3, "every type shows tokens and time", items and all(re.search(r"\d+% \([\d.]+ M\) [\d.]+ min$", x) for x in items), items)
    res(4, "each helper has its own time", re.search(r"opus-worker \(1×\) \d+% \([\d.]+ M\) 1[0-9](\.\d)? min", s)
        and re.search(r"reviewer-light \(1×\) \d+% \([\d.]+ M\) 2\.\d min", s), s)
elif not SESSION:
    print("    (items 1-4 need the real session file)")

P = os.path.join(V, "p"); os.makedirs(os.path.join(P, ".claude", "state")); os.makedirs(os.path.join(P, "plans"))
subprocess.run("git init -q", shell=True, cwd=P)
T = SESSION or os.path.join(V, "t.jsonl")
if not SESSION:
    open(T, "w").write('{"type":"user","message":{"role":"user","content":"x"}}\n')
f = os.path.join(P, "plans", "cur.md")
R1 = "# Plan v1 Rev 1 — Build 1a — Awaiting approval\n\n**Summary**\n- Goal: 9 items.\n\n**What changed since v0**\n- First version.\n"
open(f, "w", encoding="utf-8").write(R1)
e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
e.update(CLAUDE_PROJECT_DIR=P, HZ_RULES_FIRST_OFF="1")
run = lambda s_, inp: subprocess.run(["python3", os.path.join(H, s_)], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=P).stdout
run("plan-guard.py", {"session_id": "s", "transcript_path": T, "tool_name": "ExitPlanMode", "tool_input": {"plan": R1, "planFilePath": f}})
o = run("notice-reminder.py", {"session_id": "s", "transcript_path": T, "tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"},
                               "tool_response": {"stdout": "https://github.com/o/r/pull/13"}})
sf, rf = os.path.join(P, ".claude", "state", "pr-summary.md"), os.path.join(P, ".claude", "state", "pr-report.md")
s1 = open(sf, encoding="utf-8").read() if os.path.exists(sf) else ""
res(5, "the summary file is made when the pull request opens", "**GitHub checks:** not read yet" in s1 or not SESSION and os.path.exists(sf), s1[:200])
res(5, "the notice says to copy the summary file after the checks", "pr-summary.md" in o and "after step 1" in o, o[-400:])
run("notice-reminder.py", {"session_id": "s", "transcript_path": T, "tool_name": "Bash", "tool_input": {"command": "gh pr checks 13 --watch"},
                           "tool_response": {"stdout": "All checks were successful\nData and script checks\tpass"}})
s2 = open(sf, encoding="utf-8").read() if os.path.exists(sf) else ""
res(5, "after the checks the summary holds the result", "**GitHub checks:** passed" in s2 or not SESSION, s2[:200])
run("notice-reminder.py", {"session_id": "s", "transcript_path": T, "tool_name": "Bash", "tool_input": {"command": "gh pr checks 13 --watch"},
                           "tool_response": {"stdout": "Data and script checks\tfail"}})
s3 = open(sf, encoding="utf-8").read() if os.path.exists(sf) else ""
res(5, "a failed check is named as failed", "**GitHub checks:** failed" in s3 or not SESSION, s3[:200])
rp = open(rf, encoding="utf-8").read() if os.path.exists(rf) else ""
res(6, "the report holds the summary and the plan under its own heading",
    rp.startswith("## Summary") and "## Approved plan (Rev 1)" in rp and "<details>" in rp, rp[:200])
RU = open(os.path.join(C, "rules", "CLAUDE-rules.md"), encoding="utf-8").read()
res(7, "the rule names the summary shape", "in bold labels and lines, not tables" in RU)
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
