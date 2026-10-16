#!/usr/bin/env python3
"""v3.3.6 item test (owner, 16 Oct: "build 3.3.6", 10 items). Usage: python3 tools/test_v336_items.py <repo dir> [<session>]
 1 V1  the status line ends with ' · Rules v<version>': session start says so, the format accepts it, a missing one is
       a saved fix (never a send-back)
 2 G1  safe git steps on the work branch are approved (no permission question); main, force and other commands are not
 3 G2/G3/G4/G6 one gate: a merge request needs the checks read and the code-made summary pasted; one send-back; other
       sessions untouched
 7 G5  .claude/state/ is in the local ignore list and the checks folder exists; the rule names it
 8 G8  the summary counts reading, browser checks, other commands and review fixes apart, with steps and context
 9 B1  a locked setup worktree whose folder is gone is cleared at the session start; the setup code unlocks and prunes
10 O5  kept, and measured on reading steps (rule)"""
import json, os, re, shutil, subprocess, sys, tempfile
R = os.path.abspath(sys.argv[1]); C = os.path.join(R, "central"); H = os.path.join(C, "hooks"); V = tempfile.mkdtemp()
SESSION = sys.argv[2] if len(sys.argv) > 2 else None
results = []


def res(i, n, ok, d=""):
    results.append((i, bool(ok))); print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {n}" + ("" if ok else f"  -> {str(d)[:220]!r}"))


def env(P, **kw):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); e.update(kw); return e


def hook(s, P, inp, **kw):
    return subprocess.run(["python3", os.path.join(H, s)], input=json.dumps(inp), capture_output=True, text=True,
                          env=env(P, **kw), cwd=P).stdout


def proj(name, branch="work-1"):
    P = os.path.join(V, name); os.makedirs(os.path.join(P, ".claude", "state"))
    subprocess.run(f"git init -q -b main && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c && git switch -qc {branch}",
                   shell=True, cwd=P)
    return P


VER = open(os.path.join(C, "MANIFEST.txt"), encoding="utf-8").readline().split(":", 1)[1].strip()
# 1 V1
P = proj("v1")
o = hook("session-start.py", P, {"session_id": "s1", "hook_event_name": "SessionStart", "source": "startup"})
ctx = json.loads(o)["hookSpecificOutput"]["additionalContext"] if o.strip() else ""
res(1, "the session start says to end the status line with the version", f"' · Rules v{VER}'" in ctx, ctx[:200])
sys.path.insert(0, H)
import importlib
F = importlib.import_module("formats")
res(1, "the status line format accepts the version", re.search(F.VALIDATION_PATTERN, f"Confidence: High · Status: Checked · Rules v{VER}"))
res(1, "  ...also after a short note", re.search(F.VALIDATION_PATTERN, f"Confidence: High · Status: Validated — tests 9/9 · Rules v{VER}"))
T = os.path.join(V, "t1.jsonl")
reply = "Done.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Ready.\n> 👉 **I need from you:** nothing\n> ➡️ **Next:** x"
with open(T, "w") as h:
    h.write(json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}) + "\n")
    h.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": reply}]}}) + "\n")
o = hook("validation-line.py", P, {"session_id": "s1", "transcript_path": T, "hook_event_name": "Stop"})
fx = open(os.path.join(P, ".claude", "state", "pending-fixes.json"), encoding="utf-8").read() if os.path.exists(os.path.join(P, ".claude", "state", "pending-fixes.json")) else ""
res(1, "a status line without the version is a saved fix, not a send-back", "Rules v" in fx and '"block"' not in o, (o[:150], fx[:150]))
RU = open(os.path.join(C, "rules", "CLAUDE-rules.md"), encoding="utf-8").read()
res(1, "the rules say where the version is", "The status line of every reply ends with ` · Rules v<version>`" in RU)

# 2 G1
P = proj("g1", "Test-336")
def gg(cmd):
    o = hook("git-guard.py", P, {"session_id": "g", "tool_name": "Bash", "cwd": P, "tool_input": {"command": cmd}})
    return json.loads(o)["hookSpecificOutput"]["permissionDecision"] if o.strip() else "ask"
for cmd in ('git add index.html README.md && git commit -q -m "Build 1a: ice\n\n- items" && git push -u origin Test-336',
            "git add -u && git commit -q -m \"$(cat <<'EOF'\nReview fixes\nEOF\n)\" && git push -u origin Test-336"):
    res(2, f"approved without a question: {cmd[:50]}", gg(cmd) == "allow")
for cmd, want in (("git push --force origin Test-336", "ask"), ("git push origin main", "deny"), ("git push origin Test-336:main", "deny"),
                  ("git add -A && rm -rf x", "ask"), ("git commit --amend -m x", "ask")):
    res(2, f"not approved: {cmd}", gg(cmd) == want, gg(cmd))
P2 = proj("g1main", "main2"); subprocess.run("git switch -q main", shell=True, cwd=P2)
o = hook("git-guard.py", P2, {"session_id": "g", "tool_name": "Bash", "cwd": P2, "tool_input": {"command": "git add a && git commit -m x"}})
res(2, "on main nothing is approved", '"allow"' not in o, o[:150])

# 3 gate
P = proj("gate"); SD = os.path.join(P, ".claude", "state")
TG = os.path.join(V, "tg.jsonl")
def merge_reply(extra):
    return (extra + "\n\nConfidence: High · Status: Checked · Rules v" + VER + "\n\n---\n> 📌 **Result:** Ready to merge.\n"
            "> 👉 **I need from you:** Merge #15.\n> ➡️ **Next:** x")
def stop(text, sid="sg"):
    with open(TG, "w") as h:
        h.write(json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}) + "\n")
        h.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}) + "\n")
    for f in ("merge-summary-rounds.json",):
        try:
            os.remove(os.path.join(SD, f))
        except OSError:
            pass
    return hook("merge-guard.py", P, {"session_id": sid, "transcript_path": TG, "hook_event_name": "Stop"})
summ = "**Completion:** Build 1 of 1 done (100%) · Check 0 of 1 — x · **GitHub checks:** passed"
open(os.path.join(SD, "pr-summary.md"), "w").write(summ + "\n")
json.dump({"url": "https://github.com/o/r/pull/15", "checks": "", "session": "sg"}, open(os.path.join(SD, "pr-summary.json"), "w"))
o = stop(merge_reply("Built."))
res(3, "merge request before the checks are read: sent back to read them, then paste the file", "read the pull request's checks once" in o, o[:200])
json.dump({"url": "https://github.com/o/r/pull/15", "checks": "passed", "session": "sg"}, open(os.path.join(SD, "pr-summary.json"), "w"))
o = stop(merge_reply("Built. All good."))
res(3, "checks read, own summary: sent back to paste the file", "Paste the summary file" in o, o[:200])
o = stop(merge_reply(summ))
res(3, "checks read and the file pasted: passes", '"block"' not in o, o[:200])
o = stop(merge_reply("Built."), sid="other")
res(3, "another session's pull request: untouched", "Paste the summary file" not in o and "read the pull request's checks once" not in o, o[:200])

# 7 G5 and 9 B1
P = proj("g5")
tmp = tempfile.mkdtemp(prefix="hz-setup-"); wt = os.path.join(tmp, "wt")
subprocess.run(["git", "worktree", "add", "-q", "-b", "hz-setup-update-x", wt], cwd=P)
subprocess.run(["git", "worktree", "lock", wt], cwd=P); shutil.rmtree(tmp)
before = subprocess.run(["git", "worktree", "list"], cwd=P, capture_output=True, text=True).stdout
hook("session-start.py", P, {"session_id": "s5", "hook_event_name": "SessionStart", "source": "startup"})
after = subprocess.run(["git", "worktree", "list"], cwd=P, capture_output=True, text=True).stdout
res(9, "a locked setup worktree with no folder is cleared at the session start", "hz-setup-" in before and "hz-setup-" not in after, after)
ex = open(os.path.join(P, ".git", "info", "exclude"), encoding="utf-8").read()
res(7, ".claude/state/ is in the local ignore list", ".claude/state/" in ex, ex[-120:])
res(7, "the checks folder exists", os.path.isdir(os.path.join(P, ".claude", "state", "checks")))
os.makedirs(os.path.join(P, ".claude", "state", "checks"), exist_ok=True); open(os.path.join(P, ".claude", "state", "checks", "pic.png"), "w").write("x")
st = subprocess.run(["git", "status", "--short"], cwd=P, capture_output=True, text=True).stdout
res(7, "a picture in the checks folder is not an uncommitted change", ".claude" not in st, st)
res(7, "the rule names the checks folder", "`.claude/state/checks/`, never in the repository folder" in RU)
SU = open(os.path.join(H, "stubupdate.py"), encoding="utf-8").read()
res(9, "the setup update unlocks, removes and prunes its worktree", '"worktree", "unlock", wt' in SU and '"--force", "--force", wt' in SU and '"worktree", "prune"' in SU)

# 8 G8 and 10 O5
try:
    import pr_report
    importlib.reload(pr_report)
except ImportError:
    pr_report = None
if pr_report and SESSION:
    s = pr_report.summary_block(SESSION, "https://github.com/o/r/pull/13", 2, "x", "passed") or ""
    bt = re.search(r"- \*\*By type:\*\* (.*)", s).group(1) if "- **By type:**" in s else ""
    res(8, "reading, other commands and review fixes are apart", all(k in bt for k in ("reading ", "other commands ", "review fixes ")), bt)
    res(8, "each type shows steps and their context", re.search(r"reading \d+% \([\d.]+ M, \d+ steps × \d+ k\)", bt), bt)
    res(8, "review fixes have time too", re.search(r"review fixes \d+% \([^)]*\) (?!0\.0 min)[\d.]+ min", bt), bt)
else:
    print("    (item 8 needs the real session file)")
res(10, "O5 stays and is measured on reading steps", "Read a file over 1,000 lines by parts" in RU and "counts reading steps apart" in RU)
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
