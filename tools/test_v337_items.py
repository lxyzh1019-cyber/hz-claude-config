#!/usr/bin/env python3
"""v3.3.7 item test (owner, 5 Nov: "Build hz-claude-config 3.3.7 in this session, from this block"). Every expected result
of the paste block, as expected vs got, on 3.3.6 and on 3.3.7. Proof rule: each test starts from real files — the
HZ_Trout_Map .claude/settings.json at d70bc8a, the owner's session files — and must fail on 3.3.6 and pass on 3.3.7.
Usage: python3 tools/test_v337_items.py <3.3.7 repo> <3.3.6 repo> [--trout <HZ_Trout_Map>] [--sessions <folder>]
       [--real-program]    (also runs tools/real-harness/scenario_v337_git.py: the real Claude Code program)
Session files by id under ~/.claude/projects: f178f73a (Build 1b), 65f9be9a (Build 2), 092967ad (Build 3), b131a236 (Build 4).
A missing one is named, and the rest still run."""
import glob, json, os, re, shutil, subprocess, sys, tempfile

NEW, OLD = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
A = sys.argv[3:]
opt = lambda n, d=None: A[A.index(n) + 1] if n in A else d
TROUT = opt("--trout", os.path.join(os.path.dirname(NEW), "HZ_Trout_Map"))
SESS_DIR = opt("--sessions", os.path.join(os.path.expanduser("~"), ".claude", "projects"))
PY = sys.executable
HR = os.path.join(NEW, "tools", "real-harness")
IDS = {"Build 1b": "f178f73a-fa48-41cb-b2d4-28265db490b1", "Build 2": "65f9be9a-5277-464a-b61a-f356580b5c94",
       "Build 3": "092967ad-7398-4c41-af72-d585458affd8", "Build 4": "b131a236-c7c1-45e1-a75f-165476208e12"}
SESS = {}
for k, i in IDS.items():
    hit = glob.glob(os.path.join(SESS_DIR, "*", i + ".jsonl"))
    if hit:
        SESS[k] = hit[0]
    else:
        print(f"MISSING session file {k} ({i}); its tests are skipped")
results = []


def res(item, name, expected, got, ok):
    results.append((item, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  [{item}] {name}\n        expected: {expected}\n        got:      {got}")


def env(P, **kw):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1", PYTHONUTF8="1",
             PYTHONIOENCODING="utf-8")
    e.update(kw)
    return e


def hook(repo, script, inp, P, **kw):
    r = subprocess.run([PY, os.path.join(repo, "central", "hooks", script)], input=json.dumps(inp), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env(P, **kw), cwd=P)
    return r.stdout.strip()


def proj(branch="work-1", remote=None):
    P = tempfile.mkdtemp(prefix="hz337t-")
    os.makedirs(os.path.join(P, ".claude", "state"))
    subprocess.run("git init -q -b main && git config user.email t@t && git config user.name t && git commit -q "
                   f"--allow-empty -m c && git switch -qc {branch}", shell=True, cwd=P)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=P)
    return P


def tool(name, *args):
    r = subprocess.run([PY, os.path.join(HR, name), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env(os.getcwd()))
    m = re.search(r"^RESULT (.*)$", r.stdout, re.M)
    return json.loads(m.group(1)) if m else r.stdout + r.stderr


def load_mod(repo, name):
    import importlib.util
    sys.path.insert(0, os.path.join(repo, "central", "hooks"))
    spec = importlib.util.spec_from_file_location(name + str(abs(hash(repo))), os.path.join(repo, "central", "hooks", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    sys.path.pop(0)
    return m


def gitguard_fn(repo, fn="_safe_git_only"):
    src = open(os.path.join(repo, "central", "hooks", "git-guard.py"), encoding="utf-8").read()
    if fn == "_safe_git_only":
        a = src.index("_GIT_ENV = re.compile") if "_GIT_ENV = re.compile" in src else src.index("def _safe_git_only")
        b = src.index("\ndef _safe_gh_rest") if "\ndef _safe_gh_rest" in src else src.index("\nif tool == \"Bash\" and not _stack_warn")
    else:
        a = src.index("def _safe_gh_rest")
        b = src.index("\nif tool == \"Bash\" and not os.environ.get(\"HZ_FULL_RULES\") and _safe_gh_rest")
    ns = {"re": re, "os": os, "__file__": os.path.join(repo, "central", "hooks", "git-guard.py")}
    sys.path.insert(0, os.path.join(repo, "central", "hooks"))
    exec(src[a:b], ns)
    sys.path.pop(0)
    return ns[fn]


# ---------------------------------------------------------------------------------------------------------------- 1
real_settings = json.loads(subprocess.run(["git", "-C", TROUT, "show", "d70bc8a:.claude/settings.json"], capture_output=True,
                                          text=True, encoding="utf-8").stdout or "{}")
def merged(repo):
    W = tempfile.mkdtemp(); t = os.path.join(W, "s.json")
    json.dump(real_settings, open(t, "w", encoding="utf-8"))
    st = os.path.join(repo, "central", "stub-files")
    subprocess.run([PY, os.path.join(st, "merge_settings.py"), os.path.join(st, "settings.json"), t, "hz-loader.py"])
    return json.load(open(t, encoding="utf-8"))
m6, m7 = merged(OLD), merged(NEW)
res(1, "merge on the real Trout settings (d70bc8a): ask keeps only the deploy rules",
    "3.3.6 keeps the git asks · 3.3.7 ['Bash(firebase deploy:*)', 'Bash(npm run deploy:*)']",
    f"3.3.6 {len(m6['permissions'].get('ask', []))} asks · 3.3.7 {m7['permissions'].get('ask')}",
    "Bash(git commit:*)" in m6["permissions"].get("ask", []) and
    m7["permissions"].get("ask") == ["Bash(firebase deploy:*)", "Bash(npm run deploy:*)"])
res(1, "  ...deny still has gh pr merge", "True", "Bash(gh pr merge:*)" in m7["permissions"]["deny"],
    "Bash(gh pr merge:*)" in m7["permissions"]["deny"])
res(1, "  ...the stub settings carry showClearContextOnPlanAccept (D5)", "3.3.6 None · 3.3.7 True",
    f"3.3.6 {m6.get('showClearContextOnPlanAccept')} · 3.3.7 {m7.get('showClearContextOnPlanAccept')}",
    m7.get("showClearContextOnPlanAccept") is True and m6.get("showClearContextOnPlanAccept") is None)
# a session on old rules: the app still has the old asks -> the setup check names it, the setup update removes them
P = proj()
os.makedirs(os.path.join(P, ".claude"), exist_ok=True)
json.dump(real_settings, open(os.path.join(P, ".claude", "settings.json"), "w", encoding="utf-8"))
def stub_missing(repo):
    sys.path.insert(0, os.path.join(repo, "central", "hooks"))
    try:
        sc = load_mod(repo, "stubcheck"); cm = load_mod(repo, "_common")
        return sc._missing(cm.load_config(), P, sc._reader_disk(P))
    finally:
        sys.path.pop(0)
o6, o7 = stub_missing(OLD), stub_missing(NEW)
res(1, "a session on old rules (old ask rules in the app): the setup check names them",
    "3.3.6 silent · 3.3.7 'old ask rules removed'", f"3.3.6 {any('ask rules' in x for x in o6)} · 3.3.7 {any('ask rules' in x for x in o7)}",
    not any("ask rules" in x for x in o6) and any("ask rules" in x for x in o7))
SHAPES = [
    ("Build 1b", 'git add a.txt && GIT_AUTHOR_EMAIL="t@t" GIT_COMMITTER_EMAIL="t@t" git commit -q -m "Q15" && git push -q 2>&1 | tail -1; git log --oneline -1 build-4'),
    ("Build 2", "git commit -q -F - <<'XEOF'\nBuild 2: estimates\n\n- heights <380>\nXEOF"),
    ("Build 3", 'git -c user.email=t@t commit -q -m "fixes" && git push -q && git log --oneline -1 build-4'),
    ("Build 4", "git push -u origin build-4 2>&1 | tail -3")]
g6, g7 = gitguard_fn(OLD), gitguard_fn(NEW)
got = [(n, g6(c, "build-4"), g7(c, "build-4")) for n, c in SHAPES]
res(1, "git-guard approves the 4 real git step shapes on the work branch", "3.3.6 0 of 4 · 3.3.7 4 of 4",
    f"3.3.6 {sum(1 for _, a, _ in got if a)} of 4 · 3.3.7 {sum(1 for _, _, b in got if b)} of 4",
    not any(a for _, a, _ in got) and all(b for _, _, b in got))
unsafe = ["git push --force origin build-4", "git push origin main", "python -I x.py && git add -A", "git push | sh",
          "git commit --amend --no-edit", "git push > out.txt", "git status || rm -rf x"]
res(1, "  ...and none of the unsafe ones; nothing on main", "0 of 7 · main False",
    f"{sum(1 for c in unsafe if g7(c, 'build-4'))} of 7 · main {g7('git push -u origin main 2>&1 | tail -3', 'main')}",
    not any(g7(c, "build-4") for c in unsafe) and not g7("git push -u origin main 2>&1 | tail -3", "main"))
# the review's injection cases (3.3.7 review items 1-4): none may be approved
inj = ['git commit -m "$(rm -rf ~)"', "git commit -m 'x\"' ; rm -rf / ; git commit -m '\"y'", "git status & rm -rf ~",
       'git push --receive-pack="sh -c x" . HEAD', "git fetch --upload-pack=x origin", "git diff --output=/tmp/x",
       "git commit -F - <<'EOF' && git push -f origin HEAD; curl x|sh\nbody\nEOF", "git commit -F - <<EOF\n$(rm -rf ~)\nEOF",
       "git commit -m `id`", "git branch -f main HEAD"]
res(1, "  ...and none of the 10 injection cases from the review", "0 of 10", f"{sum(1 for c in inj if g7(c, 'build-4'))} of 10",
    not any(g7(c, "build-4") for c in inj))
if "--real-program" in A:
    r = subprocess.run([PY, os.path.join(HR, "scenario_v337_git.py"), OLD, NEW, TROUT], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    last = (r.stdout.strip().splitlines() or ["?"])[-1]
    res(1, "real Claude Code program on the real Trout settings (scenario_v337_git.py)", "7 of 7 passed", last,
        last.startswith("7 of 7"))

# ---------------------------------------------------------------------------------------------------------------- 2
if "Build 3" in SESS:
    b6, b7 = tool("replay_plan_showings.py", OLD, SESS["Build 3"]), tool("replay_plan_showings.py", NEW, SESS["Build 3"])
    pick = lambda rows, t: next((d for d in rows if isinstance(rows, list) and d.get("when", "").endswith(t)), {})
    for t in ("9:02 PM", "9:08 PM"):
        a, b = pick(b6, t), pick(b7, t)
        res(2, f"Build 3 re-showing at {t}: marks", "3.3.6 0 · 3.3.7 about 21 / 36, 'since' one below the newest mark",
            f"3.3.6 {a.get('marks')} · 3.3.7 {b.get('marks')} (Rev {b.get('rev')}, since Rev {b.get('since')}, newest Rev {b.get('newest')})",
            a.get("marks") == 0 and (b.get("marks") or 0) >= 15 and b.get("since") == (b.get("newest") or 0) - 1)
if "Build 4" in SESS:
    c6, c7 = tool("replay_plan_showings.py", OLD, SESS["Build 4"]), tool("replay_plan_showings.py", NEW, SESS["Build 4"])
    mk = lambda rows: [d["marks"] for d in rows if d["marks"]] if isinstance(rows, list) else rows
    res(2, "Build 4: the two re-showings are marked on both versions", "about 10 and 21 on both", f"3.3.6 {mk(c6)} · 3.3.7 {mk(c7)}",
        mk(c6) == mk(c7) and len(mk(c7)) == 2)
s6, s7 = tool("replay_plan_showings.py", OLD, "--synthetic"), tool("replay_plan_showings.py", NEW, "--synthetic")
shape = lambda rows: [(d["rev"], d["marks"]) for d in rows] if isinstance(rows, list) else rows
res(2, "synthetic, one plan file, 4 showings, then a higher Plan vN",
    "3.3.7 [(1, 0), (1, 0), (2, 1), (3, 1), (1, 0)], title never marked · 3.3.6 0 marks on all",
    f"3.3.7 {shape(s7)} title marked {any(d['title_marked'] for d in s7) if isinstance(s7, list) else '?'} · 3.3.6 {shape(s6)}",
    isinstance(s7, list) and shape(s7) == [(1, 0), (1, 0), (2, 1), (3, 1), (1, 0)] and not any(d["title_marked"] for d in s7)
    and isinstance(s6, list) and all(d["marks"] == 0 for d in s6))
# D3: a plan that names an earlier Rev the check has never seen gets one reason line; path forms of the plan file
for label, form in (("/d/…", lambda p: "/" + p[0].lower() + p[2:].replace("\\", "/")), ("D:/…", lambda p: p.replace("\\", "/")),
                    ("D:\\…", lambda p: p.replace("/", "\\"))):
    P = proj()
    pf = os.path.join(P, "plans", "x.md"); os.makedirs(os.path.dirname(pf))
    txt = "# Plan v1 — Thing — Awaiting approval\n\n**Summary**\n- Goal: a.\n\n**What changed since Rev 3**\n- b\n\n**Stops**\n- Merge.\n"
    open(pf, "w", encoding="utf-8").write(txt)
    T = os.path.join(P, "t.jsonl"); open(T, "w").close()
    shown = form(pf) if os.name == "nt" else pf
    o = hook(NEW, "plan-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "session_id": "d3",
                                    "transcript_path": T, "tool_input": {"plan": txt, "planFilePath": shown}}, P)
    after = open(pf, encoding="utf-8").read()
    res(2, f"D3: 'What changed since Rev 3' with no earlier showing gets one reason line (plan path {label})",
        "the reason line, no refusal", f"line {'No earlier showing' in after} · refused {'deny' in o}",
        "No earlier showing of this plan was found" in after and '"deny"' not in o)

# ---------------------------------------------------------------------------------------------------------------- 3
def b4_start(repo, cloud):
    W = tempfile.mkdtemp(prefix="hz-b4-")
    sh = lambda c: subprocess.run(c, shell=True, cwd=W, capture_output=True, text=True)
    sh(f'git clone -q --bare "{TROUT}" origin.git && git -C origin.git update-ref refs/heads/main d3e3c0d')
    sh("git clone -q origin.git app && git -C app switch -q build-2 && git -C app reset -q --hard 8909ad3")
    P = os.path.join(W, "app"); home = os.path.join(W, "home"); os.makedirs(home)
    kw = dict(HOME=home, USERPROFILE=home, HZ_SETUP_PUBLISH_OFF="1")
    if cloud:
        store = os.path.join(W, "gh.json")
        kw.update(CLAUDE_CODE_REMOTE="true", STAND_IN_GH_STORE=store, HZ_GH_CMD=json.dumps([PY, os.path.join(HR, "stand_in_gh.py")]))
    out = hook(repo, "session-start.py", {"hook_event_name": "SessionStart", "session_id": "b4", "source": "startup"}, P, **kw)
    try:
        out = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        pass
    m = re.search(r"\[completion\][^\n]*", out)
    calls = json.load(open(store)).get("calls", []) if cloud and os.path.exists(store) else []
    return (m.group(0) if m else "(none)"), out, calls
if os.path.isdir(TROUT):
    for cloud in (False, True):
        a, _, _ = b4_start(OLD, cloud); b, out7, calls = b4_start(NEW, cloud)
        res(3, "Build 4 session start (main d3e3c0d, branch build-2): the completion line" + (" — simulated cloud" if cloud else ""),
            "3.3.6 '0 of 2 done' · 3.3.7 '2 of 2 merged'", f"3.3.6 {a[:60]} · 3.3.7 {b[:90]}",
            "0 of 2 done" in a and "2 of 2 merged" in b)
        if cloud:
            res(3, "  ...and the cloud session start runs and names no gh pr / gh issue",
                "no gh pr call, no 'gh pr' text", f"calls {[c[:2] for c in calls]} · text {bool(re.search(r'gh (pr|issue)', out7))}",
                not any(c and c[0] in ("pr", "issue") for c in calls) and not re.search(r"\bgh (pr|issue)\b", out7))
def summary(repo, tp):
    sys.path.insert(0, os.path.join(repo, "central", "hooks"))
    os.environ["CLAUDE_PROJECT_DIR"] = os.path.dirname(tp)
    pr = load_mod(repo, "pr_report")
    s, m = pr.summary_block(tp) or "", pr.measured_part(tp) or ""
    sys.path.pop(0)
    return s, m
if "Build 3" in SESS:
    s6, m6_ = summary(OLD, SESS["Build 3"]); s7, m7_ = summary(NEW, SESS["Build 3"])
    sl = lambda m: m[m.find("**Slowest steps"):]
    res(3, "Build 3 'Slowest steps' no longer lists the 17.6 and 12.4 min git prompts", "3.3.6 lists them · 3.3.7 does not",
        f"3.3.6 {'17.6 min' in sl(m6_) and '12.4 min' in sl(m6_)} · 3.3.7 {'17.6 min' in sl(m7_) or '12.4 min' in sl(m7_)}",
        "17.6 min" in sl(m6_) and "12.4 min" in sl(m6_) and "17.6 min" not in sl(m7_) and "12.4 min" not in sl(m7_))
    sb = re.search(r"\*\*Send-backs:\*\* (\d+)", s7)
    res(3, "Build 3 send-backs counted from the session file", "at least 3 (git-guard cd, a refused question, a notice Stop block)",
        sb.group(0) if sb else "(none)", sb and int(sb.group(1)) >= 3)
if "Build 4" in SESS:
    s6, _ = summary(OLD, SESS["Build 4"]); s7, m7_ = summary(NEW, SESS["Build 4"])
    ex = lambda s: (re.search(r"Explore \(1×\)[^·\n]*", s) or re.search(r"$^", "")).group(0)
    res(3, "Build 4 Explore helper time from its own file", "3.3.6 no time · 3.3.7 1.8 min",
        f"3.3.6 '{ex(s6)}' · 3.3.7 '{ex(s7)}' · measured part '{(re.search(r'helper: Explore \| [^|]*', m7_) or re.search(r'$^', '')).group(0)}'",
        "1.8 min" in ex(s7) and "1.8 min" not in ex(s6) and "helper: Explore | 1.8 min" in m7_)

# ---------------------------------------------------------------------------------------------------------------- 4, 5
stops = {"Build 2": [1383, 1733], "Build 3": [2307], "Build 4": [2188, 2243]}
sb6 = sb7 = 0; when7 = []
for k, idx in stops.items():
    if k not in SESS:
        continue
    r6 = tool("replay_stops.py", OLD, SESS[k], *map(str, idx)); r7 = tool("replay_stops.py", NEW, SESS[k], *map(str, idx))
    for a, b in zip(r6, r7):
        n6 = any("notice" in x for x in a["reasons"]); n7 = any("notice" in x for x in b["reasons"])
        sb6 += n6; sb7 += n7
        if n7:
            when7.append(b["when"])
    if k == "Build 4":
        res(4, "Build 4 Stops at 1:25 and 1:39 PM: no send-back", "3.3.6 2 sent back · 3.3.7 0",
            f"3.3.6 {sum(1 for a in r6 if a['sent_back'])} · 3.3.7 {sum(1 for b in r7 if b['sent_back'])}",
            sum(1 for a in r6 if a["sent_back"]) == 2 and not any(b["sent_back"] for b in r7))
if len(SESS) >= 3:
    res(5, "notice-guard on the 4 real Stops (Build 2 8:29 and 8:41 PM, Build 3 11:38 AM, Build 4 1:25 PM)",
        "3.3.6 sends back 4 · 3.3.7 sends back 2 (8:29 and 8:41 PM)", f"3.3.6 {sb6} · 3.3.7 {sb7} {when7}",
        sb6 == 4 and sb7 == 2 and all(w.endswith(("8:29 PM", "8:41 PM")) for w in when7))
# rules-read-guard: Build 2's 4:19 PM command
if "Build 2" in SESS:
    cmd419 = None
    for l in open(SESS["Build 2"], encoding="utf-8"):
        if '"tool_use"' in l and "features-ledger.txt" in l and "coverage_gate" in l:
            for c in (json.loads(l).get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    cmd419 = (c.get("input") or {}).get("command")
            break
    P = proj()
    rr = lambda repo, c: hook(repo, "rules-read-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": c}}, P)
    a, b = rr(OLD, cmd419 or ""), rr(NEW, cmd419 or "")
    res(5, "rules-read-guard: Build 2's 4:19 PM command (ledger edit + coverage_gate.py, piped to tail) passes",
        "3.3.6 refused · 3.3.7 passes", f"3.3.6 {'deny' in a} · 3.3.7 {'deny' in b}", cmd419 and "deny" in a and "deny" not in b)
    ok_reads = [rr(NEW, "cat ~/.cache/hz-rules/3.3.7/rules/CLAUDE-rules.md"), rr(NEW, "sed -n 1,40p ~/.cache/hz-rules/3.3.7/rules/CLAUDE-rules.md")]
    bad = rr(NEW, "cat ~/.cache/hz-rules/3.3.7/rules/CLAUDE-rules.md > /tmp/r.md")
    res(5, "  ...cat and sed reads of the rules are still allowed; a rules read that writes elsewhere is still refused",
        "allow, allow, deny", f"{['allow' in x for x in ok_reads]} · write {'deny' in bad}",
        all('"allow"' in x for x in ok_reads) and '"deny"' in bad)
# per-script test speed: the real refused commands (Weekly-Planner 85c1952c, 17 Oct, after a slow 'npm test' run of 8.3 min)
WP = glob.glob(os.path.join(SESS_DIR, "*", "85c1952c-bf6f-44e5-9c64-522bc787386d.jsonl"))
real_cmds = []
if WP:
    _u = {}
    for _l in open(WP[0], encoding="utf-8"):
        _r = json.loads(_l) if _l.strip() else {}
        for _b in ((_r.get("message") or {}).get("content") or []) if isinstance((_r.get("message") or {}).get("content"), list) else []:
            if isinstance(_b, dict) and _b.get("type") == "tool_use":
                _u[_b["id"]] = (_b.get("input") or {}).get("command")
            if isinstance(_b, dict) and _b.get("type") == "tool_result" and "too slow" in str(_b.get("content"))[:200]:
                real_cmds.append(_u.get(_b["tool_use_id"]) or "")
else:
    print("MISSING Weekly-Planner session 85c1952c: the per-script speed test uses its commands written here")
    real_cmds = ['npm run check 2>&1 | tail -15; npm run test:fast 2>&1 | tail -25', "npm run test:fast 2>&1 | tail -30"]
P = proj()
json.dump({"latest_full_minutes": 8.3, "slowest_full_minutes": 8.3, "command": "npm test", "told": True,
           "by_script": {"npm test": {"latest": 8.3, "stopped": False}}},
          open(os.path.join(P, ".claude", "state", "test-speed.json"), "w"))
wg = lambda repo, c: "too slow" in hook(repo, "wait-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "w", "tool_input": {"command": c}}, P)
r6, r7 = [wg(OLD, c) for c in real_cmds], [wg(NEW, c) for c in real_cmds]
res(5, f"wait-guard: the {len(real_cmds)} real refused commands (npm run test:fast, a python edit of tests/smoke.js) after a slow 'npm test'",
    "3.3.6 refuses all · 3.3.7 refuses none; 'npm test' itself still refused",
    f"3.3.6 {sum(r6)} of {len(r6)} · 3.3.7 {sum(r7)} of {len(r7)} · npm test {wg(NEW, 'npm test')}",
    real_cmds and all(r6) and not any(r7) and wg(NEW, "npm test"))
# notes-only commit from git's staged list
P = proj()
os.makedirs(os.path.join(P, "js")); open(os.path.join(P, "js", "app.js"), "w").write("x")
subprocess.run("git add js/app.js", shell=True, cwd=P)
gg = lambda repo, c: hook(repo, "git-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "g", "tool_input": {"command": c}}, P)
open(os.path.join(P, "WORKING_RECORD.md"), "w").write("r")
o6, o7 = gg(OLD, 'git add WORKING_RECORD.md && git commit -m "notes"'), gg(NEW, 'git add WORKING_RECORD.md && git commit -m "notes"')
res(5, "git-guard notes-only commit reads git's staged list (code already staged)", "3.3.6 adds [skip ci] · 3.3.7 does not",
    f"3.3.6 {'skip ci' in o6} · 3.3.7 {'skip ci' in o7}", "skip ci" in o6 and "skip ci" not in o7)
# ask-guard and validation-line: no send-back
P = proj(); T = os.path.join(P, "t.jsonl"); open(T, "w").close()
q = {"hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "session_id": "a", "transcript_path": T,
     "tool_input": {"questions": [{"question": "Which?", "header": "x", "options": [{"label": "A", "description": "a"}, {"label": "B", "description": "b"}]}]}}
res(5, "ask-guard: a question with shape problems reaches me (saved fix, no refusal)", "3.3.6 refused · 3.3.7 passes",
    f"3.3.6 {'deny' in hook(OLD, 'ask-guard.py', q, P)} · 3.3.7 {'deny' in hook(NEW, 'ask-guard.py', q, P)}",
    "deny" in hook(OLD, "ask-guard.py", q, P) and "deny" not in hook(NEW, "ask-guard.py", q, P))
F7 = load_mod(NEW, "formats")
res(5, "no ' · Rules v<version>' in the validation line shape", "absent", F7.VALIDATION_SHAPE, "Rules v" not in F7.VALIDATION_SHAPE)
# owner, 6 Nov: a local session keeps gh pr create / edit / checks (Claude Code shows the pull request card); only a
# cloud session (CLAUDE_CODE_REMOTE=true, gh pr answers 403) gets the GitHub tool or gh api REST
P = proj()
SU7 = load_mod(NEW, "stubupdate")
_old_remote, _old_common = os.environ.get("CLAUDE_CODE_REMOTE"), sys.modules.pop("_common", None)
sys.path.insert(0, os.path.join(NEW, "central", "hooks"))   # the 3.3.7 _common, not one loaded earlier from 3.3.6
os.environ["CLAUDE_CODE_REMOTE"] = ""; loc = SU7._setup_pr_step(P, "hz-setup-update-x", "3.3.7")
os.environ["CLAUDE_CODE_REMOTE"] = "true"; cld = SU7._setup_pr_step(P, "hz-setup-update-x", "3.3.7")
sys.path.pop(0); sys.modules.pop("_common", None)
if _old_common is not None:
    sys.modules["_common"] = _old_common
os.environ.pop("CLAUDE_CODE_REMOTE") if _old_remote is None else os.environ.__setitem__("CLAUDE_CODE_REMOTE", _old_remote)
res(5, "the setup pull request: gh pr create locally, the GitHub tool in a cloud session", "local gh pr create · cloud no gh pr",
    f"local {'gh pr create --base main --head hz-setup-update-x' in loc} · cloud {'GitHub tool' in cld and 'gh pr' not in cld}",
    "gh pr create --base main --head hz-setup-update-x" in loc and "GitHub tool" in cld and "gh pr" not in cld)
_gd = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "g",
       "tool_input": {"command": "gh pr create --draft --base main --head work-1 --title x --body y"}}
dl, dc = hook(NEW, "git-guard.py", _gd, P, CLAUDE_CODE_REMOTE=""), hook(NEW, "git-guard.py", _gd, P, CLAUDE_CODE_REMOTE="true")
res(5, "  ...a draft refusal names gh pr ready locally, the GitHub tool in a cloud session", "local gh pr ready · cloud no gh pr",
    f"local {'gh pr ready' in dl} · cloud {'update_pull_request' in dc and 'gh pr ready' not in dc}",
    "gh pr ready" in dl and "update_pull_request" in dc and "gh pr ready" not in dc)
_gs = dict(_gd, tool_input={"command": "gh pr create --base work-0 --head work-1 --title x --body y"})
sl, sc = hook(NEW, "git-guard.py", _gs, P, CLAUDE_CODE_REMOTE=""), hook(NEW, "git-guard.py", _gs, P, CLAUDE_CODE_REMOTE="true")
res(5, "  ...the move-to-main warning names gh pr edit locally, the GitHub tool in a cloud session", "local gh pr edit · cloud no gh pr",
    f"local {'gh pr edit <number> --base main' in sl} · cloud {'GitHub tool' in sc and 'gh pr edit' not in sc}",
    "gh pr edit <number> --base main" in sl and "GitHub tool" in sc and "gh pr edit" not in sc)
# git-guard approves the setup's own REST steps (the real hook, in a project whose origin is on GitHub)
P = proj(remote="https://github.com/owner/app.git")
ga = lambda c: "the setup's own GitHub REST step" in hook(NEW, "git-guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "g", "tool_input": {"command": c}}, P)
okc = [ga("gh api -X PATCH repos/owner/app/pulls/3 -F body=@body.json"), ga("gh api -X POST repos/owner/app/pulls -f head=b -f base=main -f title=x"),
       ga("gh api repos/owner/app/commits/abcdef1/check-runs"), ga(f'python3 "{os.path.join(NEW, "central", "hooks").replace(os.sep, "/")}/pr_checks.py" 3')]
badc = [ga("gh api -X DELETE repos/owner/app/pulls/3"), ga("gh api -X POST repos/owner/app/issues -f title=x"),
        ga("gh api -X PATCH repos/other/app/pulls/3 -f body=x"), ga("gh api -X POST repos/owner/app/pulls -f draft=true"),
        ga("gh api -X PATCH repos/owner/app/pulls/3 -f body=x; rm -rf ~")]
res(5, "git-guard approves only this repository's pull-request REST steps and the check wait", "4 approved · 0 of 5 unsafe",
    f"{sum(okc)} · {sum(badc)}", all(okc) and not any(badc))

# ---------------------------------------------------------------------------------------------------------------- cloud
if "Build 4" in SESS:
    W = tempfile.mkdtemp(prefix="hz-cloud-"); P = os.path.join(W, "app"); os.makedirs(os.path.join(P, ".claude", "state"))
    home = os.path.join(W, "home"); os.makedirs(home)
    subprocess.run("git init -q -b main && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m c "
                   "&& git remote add origin https://github.com/owner/app.git && git switch -qc build-9", shell=True, cwd=P)
    store = os.path.join(W, "gh.json")
    json.dump({"head_sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=P, capture_output=True, text=True).stdout.strip()}, open(store, "w"))
    tp = os.path.join(W, "s.jsonl"); shutil.copyfile(SESS["Build 4"], tp)
    if os.path.isdir(os.path.splitext(SESS["Build 4"])[0]):
        shutil.copytree(os.path.splitext(SESS["Build 4"])[0], os.path.splitext(tp)[0])
    kw = dict(HOME=home, USERPROFILE=home, CLAUDE_CODE_REMOTE="true", STAND_IN_GH_STORE=store,
              HZ_GH_CMD=json.dumps([PY, os.path.join(HR, "stand_in_gh.py")]))
    resp = json.loads(subprocess.run(json.loads(kw["HZ_GH_CMD"]) + ["api", "-X", "POST", "repos/owner/app/pulls", "-f", "head=build-9",
                      "-f", "base=main", "-f", "title=Build 9", "-f", "body=## Quick read\nmine"], capture_output=True, text=True,
                      env=env(P, **kw), cwd=P).stdout)
    hook(NEW, "notice-reminder.py", {"hook_event_name": "PostToolUse", "session_id": "c1", "transcript_path": tp,
                                     "tool_name": "mcp__github__create_pull_request", "tool_input": {"head": "build-9", "draft": False},
                                     "tool_response": resp}, P, **kw)
    chk = subprocess.run([PY, os.path.join(NEW, "central", "hooks", "pr_checks.py"), str(resp["number"])], capture_output=True,
                         text=True, encoding="utf-8", env=env(P, **kw), cwd=P).stdout
    o2 = hook(NEW, "notice-reminder.py", {"hook_event_name": "PostToolUse", "session_id": "c1", "transcript_path": tp, "tool_name": "Bash",
                                          "tool_input": {"command": "python3 pr_checks.py 1"}, "tool_response": {"stdout": chk}}, P, **kw)
    st = json.load(open(store)); body = st["pulls"][str(resp["number"])]["body"]
    calls = [c for c in st["calls"] if c and c[0] in ("pr", "issue")]
    res("cloud", "simulated cloud session: the report and the scorecard reach the pull request text; no gh pr / gh issue call",
        "the session's part kept, hz-report and hz-scorecard parts, 0 gh pr calls, the summary as its own notice",
        f"kept {'mine' in body} · report {'<!-- hz-report -->' in body} · scorecard {'<!-- hz-scorecard -->' in body} · gh pr calls {len(calls)} · notice {'GitHub checks:** passed' in o2}",
        "mine" in body and "<!-- hz-report -->" in body and "<!-- hz-scorecard -->" in body and not calls and "GitHub checks:** passed" in o2)
    print("\n----- the pull request text the cloud session would get (scorecard part) -----")
    i = body.find("<!-- hz-scorecard -->"); print(body[i:])
    # the merge stop in the cloud: checks read with REST, the scorecard written again, no send-back
    T2 = os.path.join(W, "t2.jsonl")
    json.dump({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "p1", "name": "Bash", "input": {"command": "git push -q"}}]}}, open(T2, "w"))
    with open(T2, "a") as f:
        f.write("\n" + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done.\n\n---\n> 👉 **I need from you:** merge #1"}]}}) + "\n")
    o3 = hook(NEW, "merge-guard.py", {"hook_event_name": "Stop", "session_id": "c1", "transcript_path": T2, "stop_hook_active": False}, P, **kw)
    res("cloud", "the merge stop in the cloud: checks read with GitHub REST; passed -> no send-back", "no block", o3 or "(nothing)", '"block"' not in o3)

# ---------------------------------------------------------------------------------------------------------------- 8, 9
if os.path.isdir(TROUT):
    W = tempfile.mkdtemp(prefix="hz-fc-"); subprocess.run(["git", "clone", "-q", TROUT, W]); subprocess.run(["git", "-C", W, "checkout", "-q", "d3e3c0d"])
    open(os.path.join(W, "FEATURES.md"), "w", encoding="utf-8").write("# FEATURES\n\n- Lake panel — files: js/lake-sheet.js — test: none\n")
    r = subprocess.run([PY, os.path.join(NEW, "central", "checks", "feature_check.py"), "--repo", W, "--base", "d3e3c0d^1", "--head", "d3e3c0d"],
                       capture_output=True, text=True, encoding="utf-8")
    res(8, "feature check on HZ_Trout_Map merge d3e3c0d (Build 3) with the sample map", "red ✗ naming the lake panel",
        (r.stdout.strip().splitlines() or ["?"])[0] + f" (exit {r.returncode})", r.returncode == 1 and "✗ Lake panel" in r.stdout)
    open(os.path.join(W, "FEATURES.md"), "w", encoding="utf-8").write("# FEATURES\nno map\n")
    r = subprocess.run([PY, os.path.join(NEW, "central", "checks", "feature_check.py"), "--repo", W, "--base", "d3e3c0d^1", "--head", "d3e3c0d"],
                       capture_output=True, text=True, encoding="utf-8")
    res(8, "  ...no map yet: a notice and a pass", "notice, exit 0", r.stdout.strip()[:70] + f" (exit {r.returncode})", r.returncode == 0 and "notice" in r.stdout)
EXP = {"Build 2": {1: ("FAIL", 3), 2: None, 3: "PASS", 4: None}, "Build 3": {1: ("FAIL", 5), 2: "FAIL", 3: "FAIL", 4: "FAIL"},
       "Build 4": {1: ("FAIL", 2), 2: "PASS", 3: "FAIL", 4: None}}
for k, exp in EXP.items():
    if k not in SESS:
        continue
    out = subprocess.run([PY, os.path.join(NEW, "tools", "scorecard.py"), SESS[k]], capture_output=True, text=True, encoding="utf-8").stdout
    L = {int(l[0]): l for l in out.splitlines() if l[:1].isdigit()}
    for n, e in exp.items():
        if e is None:
            continue
        want, num = (e if isinstance(e, tuple) else (e, None))
        got = L.get(n, "?")
        ok = f"· {want} ·" in got and (num is None or got.split("· ")[-1].startswith(f"{num} git"))
        res(9, f"scorecard {k} check {n}", want + (f" ({num})" if num else ""), got[:120], ok)
    print("        " + (L.get(5) or "")[:150])

# ---------------------------------------------------------------------------------------------------------------- other cases
# two sessions in one folder: each gets its own one reminder; another session's pull request is not touched
P = proj(); T = os.path.join(P, "t.jsonl")
json.dump({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Work.\n\n❓ Decisions\n1. A or B? Recommend A\n\n---\n> 👉 **I need from you:** answer 1"}]}}, open(T, "w"))
open(T, "a").write("\n")
ng = lambda sid, act=False: hook(NEW, "notice-guard.py", {"hook_event_name": "Stop", "session_id": sid, "transcript_path": T, "stop_hook_active": act}, P)
for sid in ("s1", "s2"):
    open(os.path.join(P, ".claude", "state", "prompt-number.json"), "w").write(json.dumps({"session": sid, "n": 1}))
a, b = ng("s1"), ng("s1", True)
res("other", "a refusal ends after one reminder (notice, same Stop sent again)", "first: block · second: nothing",
    f"first {'block' in a} · second {'block' in b}", "block" in a and "block" not in b)
c = ng("s2")
res("other", "two sessions in one folder: the second session gets its own one reminder", "block", "block" if "block" in c else c[:80], "block" in c)
# a folder behind GitHub main: the session start fetches and reads merges from origin/main
W = tempfile.mkdtemp(prefix="hz-behind-")
_g = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd or os.path.join(W, "a"), capture_output=True, text=True)
_g("init", "-q", "--bare", "o.git", cwd=W); _g("clone", "-q", "o.git", "a", cwd=W)
for _c in (["config", "user.email", "t@t"], ["config", "user.name", "t"], ["commit", "-q", "--allow-empty", "-m", "c"],
           ["push", "-q", "origin", "HEAD:main"], ["switch", "-qc", "build-2"], ["commit", "-q", "--allow-empty", "-m", "b"],
           ["push", "-q", "origin", "build-2"], ["switch", "-q", "main"],
           ["merge", "-q", "--no-ff", "build-2", "-m", "Merge pull request #7 from o/build-2"], ["push", "-q", "origin", "main"],
           ["reset", "-q", "--hard", "HEAD~1"], ["update-ref", "refs/remotes/origin/main", "HEAD"]):
    _g(*_c)
cwd0 = os.getcwd(); os.chdir(os.path.join(W, "a"))
try:
    os.environ["CLAUDE_PROJECT_DIR"] = os.path.join(W, "a"); os.environ.pop("HZ_PR_LIVE_OFF", None)
    cm = load_mod(NEW, "_common")
    cm._FETCHED.clear(); got = cm.merged_on_main("build-2")
finally:
    os.chdir(cwd0)
res("other", "a folder behind GitHub main: the merge is found after git fetch origin", "True", got, got is True)
# a step refused by the safety check: no send-back after it
P = proj(); T = os.path.join(P, "t.jsonl")
with open(T, "w") as f:
    f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "x1", "name": "Bash", "input": {"command": "git push -q"}}]}}) + "\n")
    f.write(json.dumps({"type": "user", "toolDenialKind": "automode-classifier", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x1", "is_error": True, "content": "denied by the auto mode classifier"}]}}) + "\n")
    f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Stopped.\n\n---\n> 👉 **I need from you:** merge #1"}]}}) + "\n")
o = hook(NEW, "dispatch.py", {"hook_event_name": "Stop", "session_id": "r", "transcript_path": T, "stop_hook_active": False}, P)
res("other", "a step refused by the safety check: the Stop sends nothing back", "no block", o[:100] or "(nothing)", '"block"' not in o)

n_ok = sum(1 for _, ok in results if ok)
print(f"\nchecks passed {n_ok} of {len(results)}" + ("" if n_ok == len(results) else
      " · failing: " + ", ".join(str(i) for i, ok in results if not ok)))
sys.exit(0 if n_ok == len(results) else 1)
