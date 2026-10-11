#!/usr/bin/env python3
"""v3.2.13 item test, the same checks on any rules version. Usage: python3 tools/test_v3213_items.py <repo dir>
A fake 'gh' answers like GitHub: branch claude/merged-5 has a merged pull request; claude/open-6 has an open draft.
Items: 1 restart line checks GitHub (a merged branch is never named; after a merge it names main) · 2 never ask the
owner to open a new session · 3 the ready check asks GitHub · 4 worktrees only for lanes, lane names, clean-up."""
import json, os, subprocess, sys, tempfile, shutil, stat
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp(); results = []
def res(item, name, ok, detail=""):
    results.append((item, ok)); print(f"{item:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:170]!r}"))
def read(*p):
    try:
        return open(os.path.join(*p), encoding="utf-8").read()
    except OSError:
        return ""
BIN = os.path.join(V, "bin"); os.makedirs(BIN)
open(os.path.join(BIN, "gh"), "w").write('''#!/bin/sh
case "$*" in
  *"list --head claude/merged-5 --state merged"*) echo '[{"number":141}]';;
  *"list --head"*"--state merged"*) echo '[]';;
  *"view claude/merged-5"*) echo '{"state":"MERGED","isDraft":true}';;
  *"view claude/open-6"*) echo '{"state":"OPEN","isDraft":true}';;
  *) echo '[]';;
esac
''')
os.chmod(os.path.join(BIN, "gh"), 0o755)
ENV = dict(os.environ, PATH=BIN + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1",
           HZ_COMPLEX_REASON_OFF="1")   # v3.2.14: these hand-overs predate the reason line
def run(script, inp, proj, **env):
    e = dict(ENV, CLAUDE_PROJECT_DIR=proj); e.update(env)
    for k in [k for k, v in e.items() if v is None]:
        e.pop(k)
    return subprocess.run(["python3", os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True, env=e, cwd=proj).stdout
def jl(path, rows): open(path, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
def sh(c, cwd): subprocess.run(c, shell=True, cwd=cwd, capture_output=True, env=ENV)
A = os.path.join(V, "app"); os.makedirs(os.path.join(A, ".claude", "state"))
sh("git init -q --bare ../o.git && git init -q && git config user.email t@t && git config user.name t && git remote add origin ../o.git", A)
open(os.path.join(A, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n"
    "| Pass · Stage 1 of 3 — Part 5 headers | COMPLETE | ok |\n| Pass · Stage 2 of 3 — merge Part 5 (Check) | COMPLETE | merged |\n| Pass · Stage 3 of 3 — Part 6 words | QUEUED | |\n")
sh("git add -A && git commit -qm a && git push -q origin HEAD:main && git checkout -qb claude/merged-5 && git push -q -u origin claude/merged-5", A)
TR = os.path.join(V, "t.jsonl")
def reply(text):
    jl(TR, [{"type": "user", "message": {"role": "user", "content": "restart line please"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}])
CLOSE = "\nCompletion: Build 1 of 2 done (50%) · Check 1 of 1 — Pass\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Ready.\n> 👉 **I need from you:** {need}\n> ➡️ **Next:** Stage 3."
# 1 restart line
reply("```\nContinue Pass on branch claude/merged-5; next: Stage 3 of 3 — Part 6 words.\n```" + CLOSE.format(need="Nothing."))
o = run("handoff-guard.py", {"transcript_path": TR, "session_id": "h1"}, A)
res(1, "a restart line naming a branch merged on GitHub is sent back, asking for main", "is merged on GitHub" in o and "names main" in o, o[:200])
reply("```\nContinue Pass on branch main; next: Stage 3 of 3 — Part 6 words.\n```" + CLOSE.format(need="Nothing."))
o = run("handoff-guard.py", {"transcript_path": TR, "session_id": "h2"}, A)
res(1, "  ...the line naming main passes, though the session still sits on the merged branch", "merged" not in o and "but this session is on" not in o, o[:200])
res(1, "the hand-off text says: check GitHub first", "First check GitHub" in read(H, "_common.py"), "")
# 2 new session
reply("Done." + CLOSE.format(need="Paste the restart line into the new session."))
run("validation-line.py", {"transcript_path": TR, "session_id": "v1"}, A)
pf = read(A, ".claude", "state", "pending-fixes.json")
res(2, "asking me to open a new session gets a saved fix for the next step", "new session" in pf, pf[:200])
# 3 ready check
def stub_draft(branch):
    p = os.path.join(A, ".claude", "state", "pr-branches.json"); open(p, "w").write(json.dumps({"s3": {branch: "draft"}}))
reply("Ready." + CLOSE.format(need="Merge #141."))
for b, want, name in (("claude/merged-5", False, "a merged pull request: no 'mark ready' request"),
                      ("claude/open-6", True, "an open draft on GitHub: the request stays")):
    stub_draft(b)
    o = run("pr-ready-guard.py", {"transcript_path": TR, "session_id": "s3"}, A)
    res(3, name, ("still a draft" in o) == want, o[:200])
# 4 worktrees
T0 = os.path.join(V, "e.jsonl"); jl(T0, [{"type": "user", "message": {"role": "user", "content": "go"}}])
open(os.path.join(A, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": "wt", "n": 2}))
hv = lambda: run("worker-guard.py", {"tool_name": "Agent", "session_id": "wt", "transcript_path": T0, "tool_use_id": "x",
                 "tool_input": {"subagent_type": "opus-worker", "prompt": "Task: Stage 3 — Part 6\nLevel: Complex\nMap: not needed - t\nSize: M\nWorktree: ../app-6"}}, A,
                 HZ_STAGE_TAGS_OFF="1", HZ_PLANNER_CHECK_OFF="1")
o1 = hv(); o2 = hv()
res(4, "a single worker with a worktree is refused once, with the fix", '"deny"' in o1 and "main folder" in o1, o1[:200])
res(4, "  ...the second try passes (never loops)", '"deny"' not in o2, o2[:200])
res(4, "parallel lanes are told the lane names", "-lane-<a|b|c>" in read(H, "worker-guard.py"), "")
L = os.path.join(V, "app-lane-a"); M2 = os.path.join(V, "app-lane-b")
sh(f"git checkout -q main && git worktree add -q {L} claude/merged-5 && git worktree add -q {M2} -b claude/open-6", A)
lc = lambda: subprocess.run(["python3", "-c", "import sys;sys.path.insert(0,'.');from _common import *;print(lane_cleanup())"],
                            capture_output=True, text=True, cwd=H, env=dict(ENV, CLAUDE_PROJECT_DIR=A)).stdout
out = lc(); go, stay = (out.split("], [") + [""])[:2]
res(4, "clean-up offers a lane that is merged on GitHub and clean", "app-lane-a" in go, out[:300])
res(4, "  ...and keeps a lane whose pull request is not merged", "app-lane-b" in stay and "not merged" in stay, out[:300])
open(os.path.join(L, "dirty.txt"), "w").write("x")
out = lc()
res(4, "  ...and keeps a merged lane with uncommitted changes", "app-lane-a" in out and "uncommitted changes" in out, out[:300])
res(4, "rules: a single worker never works in a worktree; clean-up after merge", "never in a worktree (Hook)" in read(C, "rules", "CLAUDE-rules.md"), "")
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
