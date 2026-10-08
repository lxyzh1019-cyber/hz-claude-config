#!/usr/bin/env python3
"""v3.2.0: does this version solve the problems of earlier real sessions?
Use: python tools/replay_sessions.py <session.jsonl> [<session.jsonl> ...]
Each session file needs its folder of the same name next to it (subagents/ with the helper files).
For each session it replays the real data through the current checks and prints, per known problem, what the
current version would have done: plan send-backs and coloured marks, edits to approved plans, worker time/test/memory
limits, single-read steps, screenshot reads, hand-backs with runs still going, main-session memory notices, waiting
commands, scratch-folder writes, and the session summary with away time and usage-limit stops.
It never changes the session files. Worker limits are worked out from the same settings the worker check uses."""
import glob, json, os, re, subprocess, sys, tempfile, shutil
from datetime import datetime

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "central", "hooks")
sys.path.insert(0, HOOKS)
from _common import load_config, is_test_run  # noqa: E402

cfg = load_config()


def load(f):
    out = []
    for l in open(f, encoding="utf-8", errors="replace"):
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def ts(r):
    try:
        return datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def tok(u):
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                             "cache_read_input_tokens"))


def run_hook(script, payload, env_extra=None, cwd_proj=None):
    env = dict(os.environ, **(env_extra or {}))
    if cwd_proj:
        env["CLAUDE_PROJECT_DIR"] = cwd_proj
    o = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=json.dumps(payload), capture_output=True,
                       text=True, env=env, cwd=HOOKS)
    return o.stdout.strip()


def plans(main, proj, planner_rule=True):
    """Replay every real plan showing through the plan check. Without planner_rule, the planner rule is left out
    (older sessions ran before it existed), to show the marks on the real rounds."""
    os.makedirs(os.path.join(proj, "plans"), exist_ok=True)
    pf, tp = os.path.join(proj, "plans", "plan.md"), os.path.join(proj, "t.jsonl")
    real_back = new_back = marked = shown = 0
    results = {}
    for i, r in enumerate(main):
        c = (r.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in results:
                if "hook error" in json.dumps(b.get("content"))[:200]:
                    real_back += 1
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "ExitPlanMode":
                shown += 1
                plan = (b.get("input") or {}).get("plan") or ""
                open(pf, "w", encoding="utf-8").write(plan)
                with open(tp, "w", encoding="utf-8") as f:
                    for x in main[:i + 1]:
                        f.write(json.dumps(x) + "\n")
                pay = {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "session_id": "replay",
                       "transcript_path": tp, "tool_input": {"plan": plan, "planFilePath": pf}}
                # old plans were written before the proof/size tags, so that rule is reported apart (see notags)
                envx = {"HZ_PLAN_ROUNDS_OFF": "", "HZ_STAGE_TAGS_OFF": "1"} if planner_rule else \
                    {"HZ_PLAN_ROUNDS_OFF": "", "HZ_PLANNER_CHECK_OFF": "1", "HZ_STAGE_TAGS_OFF": "1"}
                out = run_hook("plan-guard.py", pay, envx, proj)
                if "added the coloured change marks" in out:
                    marked += 1
                    pay["tool_input"]["plan"] = open(pf, encoding="utf-8").read()
                    out = run_hook("plan-guard.py", pay, envx, proj)
                if '"deny"' in out:
                    new_back += 1
                results[b["id"]] = out
    reasons = {}
    try:
        for l in open(os.path.join(proj, ".claude", "state", "plan-guard.jsonl"), encoding="utf-8"):
            for x in (json.loads(l).get("reasons") or []):
                reasons[x] = reasons.get(x, 0) + 1
    except (OSError, ValueError):
        pass
    for f in ("plan-guard.jsonl", "plan-store.json"):
        try:
            os.remove(os.path.join(proj, ".claude", "state", f))
        except OSError:
            pass
    return shown, real_back, new_back, marked, reasons


def notags(main):
    """Plans whose Build stages lack the proof and size tags (rule new in v3.2.0)."""
    n = tot = 0
    for r in main:
        c = (r.get("message") or {}).get("content")
        for b in c if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "ExitPlanMode":
                plan = ((b.get("input") or {}).get("plan") or "").lower()
                st = plan.split("stages to finish", 1)[1] if "stages to finish" in plan else ""
                build = [l for l in st.splitlines() if "claude" in l and "build" in l]
                tot += 1
                if build and any(not re.search(r"\bproof:", l) or not re.search(r"\bsize:\s*[sml]\b", l) for l in build):
                    n += 1
    return n, tot


def approved_edits(main):
    """Edits of a plan file after its version was approved, which the plan-edit check now refuses."""
    approved_ver, pending, n = None, {}, 0
    for r in main:
        c = (r.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") == "ExitPlanMode":
                m = re.search(r"Plan v(\d+)", (b.get("input") or {}).get("plan") or "")
                pending[b["id"]] = int(m.group(1)) if m else None
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                if "has approved your plan" in json.dumps(b.get("content")):
                    approved_ver = pending[b["tool_use_id"]]
            elif b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write", "MultiEdit") and approved_ver:
                inp = b.get("input") or {}
                if "/plans/" not in str(inp.get("file_path") or "").replace("\\", "/"):
                    continue
                new = str(inp.get("new_string") or inp.get("content") or "")
                old = str(inp.get("old_string") or "")
                bump = re.search(r"Plan v(\d+)", new)
                if bump and int(bump.group(1)) > approved_ver:
                    continue
                if re.sub(r"(?i)awaiting approval|approved|\s", "", old) == re.sub(r"(?i)awaiting approval|approved|\s", "", new):
                    continue
                n += 1
    return n


def workers(folder):
    """The worker limits, worked out step by step on each real worker record."""
    res = []
    for f in sorted(glob.glob(os.path.join(folder, "subagents", "*.jsonl"))):
        try:
            kind = json.load(open(f[:-6] + ".meta.json", encoding="utf-8")).get("agentType") or ""
        except (OSError, ValueError):
            kind = ""
        if kind not in ("opus-worker", "sonnet-worker"):
            continue
        recs = load(f)
        lim = (cfg.get("worker_minutes") or {}).get(kind) or ([45, 60] if "sonnet" in kind else [90, 120])
        first, tests, shape, pngs, total, seen = None, 0, [], 0, 0, set()
        started, ended = set(), set()
        ev = {"time warn": None, "time stop": None, "tests warn": None, "tests stop": None, "memory": None,
              "batch reads": 0, "screenshot": 0, "open runs at hand-back": 0}
        after_stop = 0
        stopped = False
        for r in recs:
            t = ts(r)
            if first is None and t:
                first = t
            line = json.dumps(r)
            started.update(re.findall(r"running in background with ID: ([A-Za-z0-9_-]+)", line))
            ended.update(re.findall(r"<task-id>([A-Za-z0-9_-]+)</task-id>", line))
            if r.get("type") != "assistant":
                continue
            m = r.get("message") or {}
            u = m.get("usage")
            if u and m.get("id") not in seen:
                seen.add(m.get("id"))
                total += tok(u)
                if stopped:
                    after_stop += tok(u)
                ctx = tok(u) - int(u.get("output_tokens") or 0)
                if ctx >= int(cfg.get("worker_memory_max", 250000)) and ev["memory"] is None:
                    ev["memory"] = len(seen)
            tu = [b for b in (m.get("content") or []) if isinstance(b, dict) and b.get("type") == "tool_use"] \
                if isinstance(m.get("content"), list) else []
            if not tu:
                continue
            mins = (t - first) / 60 if t and first else 0
            for k, cond in (("time warn", mins >= lim[0]), ("time stop", mins >= lim[1])):
                if cond and ev[k] is None:
                    ev[k] = round(mins)
            tests += sum(1 for b in tu if b.get("name") == "Bash" and is_test_run((b.get("input") or {}).get("command")))
            for k, n in (("tests warn", int(cfg.get("worker_tests_warn", 10))), ("tests stop", int(cfg.get("worker_tests_stop", 20)))):
                if tests >= n and ev[k] is None:
                    ev[k] = len(seen)
            single = len(tu) == 1 and tu[0].get("name") in ("Read", "Grep", "Glob")
            shape.append(single)
            trailing = next((i for i, s in enumerate(reversed(shape)) if not s), len(shape))
            if single and trailing >= 5 and trailing % 5 == 0:
                ev["batch reads"] += 1
            if any(b.get("name") == "Read" and re.search(r"\.(png|jpe?g|webp)$", str((b.get("input") or {}).get("file_path") or ""), re.I) for b in tu):
                pngs += 1
            if any(b.get("name") == "SubagentHandback" for b in tu) and (started - ended):
                ev["open runs at hand-back"] += 1
            if not stopped and (ev["time stop"] is not None or ev["tests stop"] is not None):
                stopped = True
        ev["screenshot"] = pngs
        res.append({"file": os.path.basename(f)[:20], "kind": kind, "steps": len(seen), "tokens": total,
                    "minutes": round(((ts(recs[-1]) or first or 0) - (first or 0)) / 60), "tests": tests, "ev": ev,
                    "after_stop": after_stop})
    return res


def main_checks(main, proj):
    """Main-session memory notices, waiting commands, and scratch-folder writes."""
    notices, last_lvl, waits, scratch = 0, None, 0, 0
    seen = set()
    for r in main:
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        m = r.get("message") or {}
        u = m.get("usage")
        if u and m.get("id") not in seen:
            seen.add(m.get("id"))
            ctx = tok(u) - int(u.get("output_tokens") or 0)
            b = int(cfg.get("main_memory_max", 200000))
            if ctx >= b:
                lvl = (ctx - b) // 100000
                if lvl != last_lvl:
                    notices += 1
                    last_lvl = lvl
        for x in (m.get("content") or []) if isinstance(m.get("content"), list) else []:
            if not isinstance(x, dict) or x.get("type") != "tool_use":
                continue
            inp = x.get("input") or {}
            if x.get("name") == "Bash" and re.search(r"\bsleep\s+([6-9]|\d\d+)|tail\s+-f|until\b|while\b.*sleep|gh\s+run\s+watch|while\b[\s\S]*gh\s+run", str(inp.get("command") or "")):
                out = run_hook("wait-guard.py", {"tool_name": "Bash", "tool_input": inp, "session_id": "replay"}, cwd_proj=proj)
                waits += 1 if '"deny"' in out else 0
            if x.get("name") in ("Write", "Edit") and re.search(r"[\\/]temp[\\/]claude[\\/]", str(inp.get("file_path") or "").lower()):
                out = run_hook("routing-guard.py", {"tool_name": x["name"], "tool_input": inp, "session_id": "replay"}, cwd_proj=proj)
                scratch += 0 if '"deny"' in out else 1
    return notices, waits, scratch


def summary(sess_file, proj):
    tmp = os.path.join(proj, os.path.basename(sess_file))
    shutil.copy(sess_file, tmp)
    folder = sess_file[:-len(".jsonl")]
    if os.path.isdir(folder):
        shutil.copytree(folder, tmp[:-len(".jsonl")], dirs_exist_ok=True)
    with open(tmp, "a", encoding="utf-8") as f:
        last = max((r.get("timestamp") or "" for r in load(sess_file)), default="")
        f.write(json.dumps({"type": "assistant", "timestamp": last, "message": {"id": "replay-end", "role": "assistant",
                "content": [{"type": "text", "text": "x\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** x\n> 👉 **I need from you:** nothing\n> ➡️ **Next:** x"}]}}) + "\n")
    out = run_hook("stats.py", {"transcript_path": tmp, "session_id": "replay"}, cwd_proj=proj)
    try:
        return json.loads(out).get("systemMessage", "")
    except ValueError:
        return ""


for sess in sys.argv[1:]:
    name = os.path.basename(sess)[:8]
    proj = tempfile.mkdtemp()
    open(os.path.join(proj, "WORKING_RECORD.md"), "w").write("# WORKING RECORD\n")
    main = load(sess)
    shown, real_back, new_back, marked, why = plans(main, proj)
    _s2, _r2, new_back2, marked2, why2 = plans(main, proj, planner_rule=False)
    edits = approved_edits(main)
    ws = workers(sess[:-len(".jsonl")])
    notices, waits, scratch = main_checks(main, proj)
    summ = summary(sess, proj)
    print(f"\n=== Session {name}")
    _nt, _tt = notags(main)
    print(f"Plans written before the proof and size tags: {_nt} of {_tt} would get one send-back for them (new rule)")
    print(f"Plans: {shown} showings · send-backs then {real_back}, now {new_back} ({', '.join(f'{k} {v}' for k, v in why.items()) or 'none'})"
          f" · without the planner rule: {new_back2} ({', '.join(f'{k} {v}' for k, v in why2.items()) or 'none'}), marked by code {marked2}")
    print(f"Edits of an approved plan file, now refused: {edits}")
    tot_w = sum(w["tokens"] for w in ws)
    hit = lambda k: sum(1 for w in ws if w["ev"][k] is not None)
    print(f"Workers: {len(ws)} runs, {round(tot_w / 1e6, 1)} M tokens · time warning {hit('time warn')}, time stop {hit('time stop')}"
          f" · test-run warning {hit('tests warn')}, stop {hit('tests stop')} · memory budget {hit('memory')}"
          f" · read-in-one-step notes {sum(w['ev']['batch reads'] for w in ws)} · screenshot reads {sum(w['ev']['screenshot'] for w in ws)}"
          f" (warned once per worker: {sum(1 for w in ws if w['ev']['screenshot'])}) · hand-backs with runs still going {sum(w['ev']['open runs at hand-back'] for w in ws)}")
    saved = sum(w["after_stop"] for w in ws)
    print(f"Worker tokens after a time or test-run stop (the most a stop could save): {round(saved / 1e6, 1)} M"
          f" ({round(100 * saved / max(tot_w, 1))}% of worker tokens)")
    for w in sorted(ws, key=lambda x: -x["tokens"])[:5]:
        print(f"  {w['kind']} {w['file']}: {w['steps']} steps, {w['minutes']} min, {w['tests']} test runs, "
              f"{round(w['tokens'] / 1e6, 1)} M · {', '.join(f'{k} at {v}' for k, v in w['ev'].items() if v not in (None, 0))}")
    print(f"Main session: memory notices {notices} · waiting commands refused {waits} · scratch-folder writes now allowed {scratch}")
    print("Summary now:\n" + "\n".join("  " + l for l in summ.splitlines()[1:]))
    shutil.rmtree(proj, ignore_errors=True)
