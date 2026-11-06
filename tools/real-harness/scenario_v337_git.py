#!/usr/bin/env python3
"""v3.3.7 (X48 G1 reopened): the real Claude Code program, a scripted stand-in model, the real checks as hooks, and a
copy of the REAL HZ_Trout_Map .claude/settings.json (commit d70bc8a), merged with each version's stub settings by that
version's merge_settings.py. On a work branch the session runs the four git step shapes that asked me in Builds 1b-4
(env-prefixed commit, here-document commit, "git -c user.email" commit, "git push … 2>&1 | tail -3") against a local
bare origin, in default permission mode. Print mode (-p) cannot show a question: a question shows as a step whose result
says the permission was not granted, and the commit or push does not happen.
The 3.3.6 proof wrote a settings.json with no ask rules and a plain command, a setup no app has; this one starts from
the real file and the real commands.
Usage: python3 scenario_v337_git.py <3.3.6 repo folder> <3.3.7 repo folder> [<HZ_Trout_Map folder>]
Needs: CLAUDE_BIN (default: claude on PATH), git, Python 3. Prints expected vs got per line."""
import json, os, random, shutil, subprocess, sys, tempfile, time

OLD, NEW = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
TROUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(NEW), "HZ_Trout_Map")
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ok_all = []
BR = "Test-337"
STEPS = [  # the shapes of the real asked steps (Build 1b 15:50, Build 2 23:20, Build 3 18:34, Build 4 20:18)
    ("Build 1b: env-prefixed commit + push | tail",
     f'git add a.txt && GIT_AUTHOR_EMAIL="t@t" GIT_COMMITTER_EMAIL="t@t" git commit -q -m "Shorter hint (Q15)" && git push -q -u origin {BR} 2>&1 | tail -1; git log --oneline -1 {BR}'),
    ("Build 2: commit message from a here-document",
     "git commit -q --allow-empty -F - <<'XEOF'\nBuild 2: estimates\n\n- Lake heights <380 lakes>\nXEOF"),
    ("Build 3: git -c user.email commit + push",
     f'git -c user.email=t@t commit -q --allow-empty -m "Build 3 review fixes" && git push -q && git log --oneline -1 {BR}'),
    ("Build 4: git push -u … 2>&1 | tail -3", f"git push -u origin {BR} 2>&1 | tail -3"),
]


def say(name, expected, got, ok):
    ok_all.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      expected: {expected}\n      got:      {got}")


def sh(cmd, cwd):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)


real = subprocess.run(["git", "-C", TROUT, "show", "d70bc8a:.claude/settings.json"], capture_output=True, text=True,
                      encoding="utf-8")
if real.returncode != 0:
    sys.exit("cannot read HZ_Trout_Map d70bc8a:.claude/settings.json: " + real.stderr)
TROUT_SETTINGS = json.loads(real.stdout)


def merged_settings(repo, work):
    t = os.path.join(work, "target.json")
    json.dump(TROUT_SETTINGS, open(t, "w", encoding="utf-8"), indent=2)
    stub = os.path.join(repo, "central", "stub-files")
    r = subprocess.run([PY, os.path.join(stub, "merge_settings.py"), os.path.join(stub, "settings.json"), t,
                        "hz-loader.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.load(open(t, encoding="utf-8"))


def run(label, repo):
    B = tempfile.mkdtemp(prefix=f"hz337-{label}-")
    P = os.path.join(B, "proj"); os.makedirs(os.path.join(P, ".claude"))
    s = merged_settings(repo, B)
    perm = s.get("permissions", {})
    # the merged file's hooks call the loader (it fetches from GitHub); run this version's checks directly instead
    disp = os.path.join(repo, "central", "hooks", "dispatch.py").replace("\\", "/")
    s["hooks"] = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": f'"{PY}" -B "{disp}"'.replace("\\", "/")}]}]}
    json.dump(s, open(os.path.join(P, ".claude", "settings.json"), "w", encoding="utf-8"), indent=2)
    open(os.path.join(P, "a.txt"), "w").write("x\n")
    sh("git init -q -b main && git config user.email t@t && git config user.name t && git add -A && git commit -qm c "
       f"&& git init -q --bare ../origin.git && git remote add origin ../origin.git && git push -q origin main "
       f"&& git switch -qc {BR} && echo y >> a.txt", P)
    port = 9000 + random.randint(0, 800)
    script = os.path.join(B, "script.json")
    json.dump([{"text": n, "tools": [{"id": f"g{i}", "name": "Bash", "input": {"command": c, "description": n}}]}
               for i, (n, c) in enumerate(STEPS)] + [{"text": "END"}], open(script, "w"))
    env = dict(os.environ, HARNESS_LOG=os.path.join(B, "requests.log"))
    srv = subprocess.Popen([PY, os.path.join(HERE, "stand_in_model.py"), str(port), script], env=env)
    time.sleep(1.0)
    cfgdir = os.path.join(B, "config"); os.makedirs(cfgdir)
    e = {k: v for k, v in os.environ.items() if not k.startswith(("HZ_", "ANTHROPIC_", "CLAUDE_CODE_"))}
    e.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{port}", ANTHROPIC_API_KEY="sk-test", CLAUDE_CONFIG_DIR=cfgdir,
             CLAUDE_PROJECT_DIR=P, HZ_RULES_FIRST_OFF="1", DISABLE_AUTOUPDATER="1",
             CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    try:
        r = subprocess.run([CLAUDE, "-p", "Commit and push.", "--permission-mode", "default", "--output-format",
                            "stream-json", "--verbose"], cwd=P, env=e, capture_output=True, text=True, timeout=240,
                           encoding="utf-8", errors="replace")
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired as x:
        out = str(x.stdout or "") + " TIMEOUT"
    finally:
        srv.kill()
    results = {}
    for line in out.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for c in ((rec.get("message") or {}).get("content") or []) if isinstance((rec.get("message") or {}).get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                results[c.get("tool_use_id")] = (str(c.get("content")), bool(c.get("is_error")))
    denials = []
    for line in out.splitlines():
        if '"permission_denials"' in line:
            try:
                denials = json.loads(line).get("permission_denials") or []
            except ValueError:
                pass
    asked = []
    for i, (n, _) in enumerate(STEPS):
        txt, err = results.get(f"g{i}", ("(no result)", True))
        a = any(d.get("tool_use_id") == f"g{i}" for d in denials) or "permission" in txt.lower() and err
        asked.append(a)
    commits = sh(f"git rev-list --count {BR}", os.path.join(B, "origin.git")).stdout.strip() or "0"
    return dict(ask=perm.get("ask", []), deny=perm.get("deny", []), asked=asked, commits=commits,
                tail=out[-500:].replace("\n", " "))


a = run("336", OLD)
b = run("337", NEW)
print(f"      3.3.6 merged ask: {a['ask']}\n      3.3.7 merged ask: {b['ask']}")
for i, (n, _) in enumerate(STEPS):
    say(f"{n}: 3.3.6 asks me, 3.3.7 does not", "3.3.6 asked = True · 3.3.7 asked = False",
        f"3.3.6 asked = {a['asked'][i]} · 3.3.7 asked = {b['asked'][i]}", a["asked"][i] and not b["asked"][i])
say("3.3.7: all three commits are on the origin work branch (main commit + 3)", "4 commits on Test-337",
    f"3.3.6: {a['commits']} · 3.3.7: {b['commits']}", b["commits"] == "4")
say("3.3.7 merge result on the Trout copy: ask keeps only the deploy rules",
    "['Bash(firebase deploy:*)', 'Bash(npm run deploy:*)']", b["ask"],
    b["ask"] == ["Bash(firebase deploy:*)", "Bash(npm run deploy:*)"])
say("3.3.7 merge result: deny still has gh pr merge", "True", "Bash(gh pr merge:*)" in b["deny"],
    "Bash(gh pr merge:*)" in b["deny"])
if not all(ok_all):
    print("      3.3.6 tail: " + a["tail"]); print("      3.3.7 tail: " + b["tail"])
print(f"\n{sum(ok_all)} of {len(ok_all)} passed")
