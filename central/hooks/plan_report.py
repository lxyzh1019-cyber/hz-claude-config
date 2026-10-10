#!/usr/bin/env python3
"""v3.2.9: the measured part of the end-of-plan report.

Usage (by the session, at the end of a plan):  python3 <rules folder>/hooks/plan_report.py "<plan name>"
It reads every session file of this project that names the plan (main session and helpers), measures where the time
and the tokens went, lists the slowest steps, and compares the numbers with the last report in docs/reports/.
The session writes the Quick read and the suggestions above this output; this part is measured, not written.
Never blocks anything; prints plain Markdown and one metrics line for the next report."""
import glob, json, os, re, statistics, sys
from datetime import datetime

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
STATE_DIR = os.path.join(PROJECT_DIR, ".claude", "state")
TEST_RE = re.compile(r"npm (run )?(test|check|smoke)|node tests/|playwright|SMOKE_|run-tests|pytest")
METRICS_RE = re.compile(r"<!-- metrics: (\{.*?\}) -->")


def _t(r):
    try:
        return datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _load(p):
    out = []
    try:
        for l in open(p, encoding="utf-8", errors="replace"):
            l = l.strip()
            if l:
                try:
                    out.append(json.loads(l))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def sessions_for(plan, folder):
    """Main session files in the folder that name the plan."""
    found = []
    for p in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        try:
            if plan in open(p, encoding="utf-8", errors="replace").read():
                found.append(p)
        except OSError:
            pass
    return found


def measure(paths):
    m = {"sessions": len(paths), "wall_min": 0.0, "tokens_m": 0.0, "tool_calls": 0, "helpers": 0,
         "test_min": 0.0, "refusals": 0, "floor_s": None}
    floor, slow, by_helper, spans = [], [], {}, []
    # v3.2.9: time first, tokens second (owner). Minutes by kind, owner-blind: app, config, plan or waiting.
    tm = {"test runs": 0.0, "waiting for GitHub": 0.0, "other commands": 0.0, "model thinking": 0.0, "waiting for you": 0.0}
    one_test, gh_wait = [], 0.0
    for p in paths:
        R = _load(p)
        ts = [x for x in (_t(r) for r in R) if x]
        if len(ts) > 1:
            m["wall_min"] += (ts[-1] - ts[0]) / 60
        # v3.2.10: dynamic workflow helpers keep their records one folder deeper (subagents/workflows/wf_<run>/)
        files = [("main", p)] + [(os.path.basename(f)[6:12], f) for f in
                                  sorted(glob.glob(os.path.join(p[:-6], "subagents", "agent-*.jsonl"))
                                         + glob.glob(os.path.join(p[:-6], "subagents", "workflows", "*", "agent-*.jsonl")))]
        for name, f in files:
            kind = "main"
            if name != "main":
                m["helpers"] += 1
                try:
                    kind = json.load(open(f[:-6] + ".meta.json", encoding="utf-8")).get("agentType") or "helper"
                except (OSError, ValueError):
                    kind = "helper"
            recs = R if name == "main" else _load(f)
            seen, pend, tok = set(), {}, 0
            bg = {}       # v3.2.10: background GitHub waits end at their task notice (9 Oct: 101 min were not counted)
            edited, stage, t_first, t_last = set(), None, None, None
            for r in recs:
                if name == "main" and r.get("isSidechain"):
                    continue
                msg = r.get("message") or {}
                if r.get("type") == "assistant" and msg.get("id") and msg["id"] not in seen:
                    seen.add(msg["id"])
                    u = msg.get("usage") or {}
                    tok += sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                             "cache_creation_input_tokens", "cache_read_input_tokens"))
                c = msg.get("content")
                _tt = _t(r)
                if _tt:
                    t_first = t_first or _tt
                    t_last = _tt
                if stage is None and r.get("type") == "user" and name != "main":
                    _sm = re.search(r"Stage\s+(\d+[a-z]?)\s+of\s+\d+", json.dumps(msg.get("content"), ensure_ascii=False))
                    stage = _sm.group(1) if _sm else ""
                _raw = json.dumps(c, ensure_ascii=False) if name == "main" and r.get("type") == "user" else ""
                if "<task-notification>" in _raw:
                    for _id in re.findall(r"<tool-use-id>(\w+)</tool-use-id>", _raw):
                        if _id in bg and _tt:
                            tm["waiting for GitHub"] += (_tt - bg.pop(_id)) / 60
                for b in c if isinstance(c, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        pend[b.get("id")] = (_t(r), b.get("name"), (b.get("input") or {}))
                        _in = b.get("input") or {}
                        if b.get("name") in ("Edit", "Write", "MultiEdit") and _in.get("file_path"):
                            edited.add(os.path.basename(str(_in["file_path"]).replace("\\", "/")))
                        if (b.get("name") == "Bash" and _in.get("run_in_background") and _t(r)
                                and re.search(r"\bgh\s+(run\s+(watch|view)|pr\s+checks)\b", str(_in.get("command") or ""))):
                            bg[b.get("id")] = _t(r)
                    elif b.get("type") == "tool_result" and b.get("tool_use_id") in pend:
                        t0, nm, inp = pend.pop(b["tool_use_id"])
                        t1 = _t(r)
                        txt = json.dumps(b.get("content"), ensure_ascii=False)
                        if "hook error" in txt:
                            m["refusals"] += 1
                        if not (t0 and t1):
                            continue
                        d = t1 - t0
                        m["tool_calls"] += 1
                        if nm in ("Read", "Grep", "Glob"):
                            floor.append(d)
                        cmd = str(inp.get("command") or "") if nm == "Bash" else ""
                        if cmd and TEST_RE.search(cmd):
                            m["test_min"] += d / 60
                            tm["test runs"] += d / 60
                            if re.search(r"SMOKE_ONLY=|--grep\b|\.test\.[jt]s\b|-k\s", cmd):
                                one_test.append(d)
                        elif cmd and re.search(r"\bgh\s+(run\s+(watch|view)|pr\s+checks)\b", cmd):
                            tm["waiting for GitHub"] += d / 60
                        elif nm == "Bash":
                            tm["other commands"] += d / 60
                        if d >= 60:
                            slow.append((d, kind, nm, re.sub(r"\s+", " ", cmd or json.dumps(inp))[:90]))
            m["tokens_m"] += tok / 1e6
            # model time: the gap before each answer (capped); waiting for you: the gap before each real prompt
            prev = None
            for r in recs:
                tt = _t(r)
                if tt and prev and r.get("type") == "assistant":
                    tm["model thinking"] += min(tt - prev, 600) / 60
                if tt and prev and name == "main" and r.get("type") == "user" and not r.get("isSidechain"):
                    c0 = (r.get("message") or {}).get("content")
                    txt0 = c0 if isinstance(c0, str) else ""
                    if txt0 and not txt0.lstrip().startswith(("<task-notification>", "Another Claude session")):
                        gap = tt - prev
                        if gap <= 3600:
                            tm["waiting for you"] += gap / 60
                if tt:
                    prev = tt
            if name == "main":   # v3.2.9: the main session's context (owner: the /context view belongs in the report)
                ctx = [sum(int((r.get("message") or {}).get("usage", {}).get(k) or 0) for k in
                           ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                       for r in recs if r.get("type") == "assistant" and not r.get("isSidechain")
                       and (r.get("message") or {}).get("usage")]
                ctx = [x for x in ctx if x]
                if ctx:
                    m["ctx_start_k"] = max(m.get("ctx_start_k", 0), round(ctx[0] / 1000))
                    m["ctx_peak_k"] = max(m.get("ctx_peak_k", 0), round(max(ctx) / 1000))
                    m["steps_over_200k"] = m.get("steps_over_200k", 0) + sum(1 for x in ctx if x > 200000)
                    m["over_200k_tokens_m"] = round(m.get("over_200k_tokens_m", 0) + sum(max(0, x - 200000) for x in ctx) / 1e6, 1)
                    m["main_steps"] = m.get("main_steps", 0) + len(ctx)
                m["compacts"] = m.get("compacts", 0) + sum(1 for r in recs if r.get("subtype") == "compact_boundary"
                                                          or r.get("isCompactSummary"))
            if name != "main" and t_first and t_last:
                spans.append({"stage": stage or "", "kind": kind, "start": t_first, "end": t_last, "files": edited})
            h = by_helper.setdefault(kind, [0, 0.0])
            h[0] += 1
            h[1] += tok / 1e6
    if floor:
        m["floor_s"] = round(statistics.median(floor), 2)
        tm["hook time on every call"] = m["tool_calls"] * statistics.median(floor) / 60
    m["time_kinds"] = {k: round(v, 1) for k, v in tm.items()}
    m["one_test_runs"] = len(one_test)
    m["one_test_median_s"] = round(statistics.median(one_test)) if one_test else None
    m["tokens_by_helper"] = {k: round(v[1], 1) for k, v in by_helper.items()}
    for k in ("wall_min", "tokens_m", "test_min"):
        m[k] = round(m[k], 1)
    slow.sort(reverse=True)
    m["parallel"] = parallel_candidates(spans)
    return m, slow[:6], by_helper


def parallel_candidates(spans):
    """v3.2.10: helpers of different stages that ran one after another, edited no file in common, and so could have
    run at the same time. Minutes lost = the shorter of the two runs. Read-only helpers (no edits) are left out."""
    work = sorted([s for s in spans if s["files"] and s["stage"]], key=lambda s: s["start"])
    out = []
    for a, b in zip(work, work[1:]):
        if a["stage"] != b["stage"] and b["start"] >= a["end"] and not (a["files"] & b["files"]):
            out.append({"stages": f"{a['stage']} and {b['stage']}",
                        "minutes": round(min(a["end"] - a["start"], b["end"] - b["start"]) / 60)})
    out.sort(key=lambda x: -x["minutes"])
    return {"pairs": out[:3], "minutes": sum(x["minutes"] for x in out)}


def last_report(plan):
    best = None
    for p in glob.glob(os.path.join(PROJECT_DIR, "docs", "reports", "*.md")):
        try:
            t = open(p, encoding="utf-8").read()
        except OSError:
            continue
        mm = METRICS_RE.search(t)
        if mm and plan not in os.path.basename(p):
            if best is None or os.path.getmtime(p) > best[0]:
                best = (os.path.getmtime(p), os.path.basename(p), json.loads(mm.group(1)))
    return best


def main():
    args, folder = sys.argv[1:], ""
    if "--dir" in args:
        i = args.index("--dir")
        folder = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    plan = " ".join(args).strip()
    if not folder:
        try:
            folder = open(os.path.join(STATE_DIR, "transcripts-dir.txt"), encoding="utf-8").read().strip()
        except OSError:
            folder = ""
    paths = sessions_for(plan, folder) if plan and folder else []
    if not paths:
        print(f"## Measured part\n\nNo session file names the plan \"{plan}\" (folder: {folder or 'unknown'}).")
        return
    m, slow, by_helper = measure(paths)
    out = ["## Measured part (by code, from the session files)", "",
           "| Measure | Value |", "|---|---|",
           f"| Sessions | {m['sessions']} |",
           f"| Session time (sum) | {m['wall_min'] / 60:.1f} h |",
           f"| Tokens | {m['tokens_m']:.1f} M |",
           f"| Tool calls | {m['tool_calls']} |",
           f"| Hook time per call (median Read/Grep/Glob) | {m['floor_s']} s |",
           f"| Test runs (time in test commands) | {m['test_min']:.0f} min |",
           f"| Helpers started | {m['helpers']} |",
           f"| Refused steps (checks) | {m['refusals']} |",
           f"| Main session context: at start / peak | {m.get('ctx_start_k', '?')} k / {m.get('ctx_peak_k', '?')} k |",
           f"| Main steps over 200 k context | {m.get('steps_over_200k', 0)} of {m.get('main_steps', 0)} |",
           f"| Compactions (/compact) | {m.get('compacts', 0)} |", "",
           "**Tokens by helper:** " + " · ".join(f"{k} {v[0]}× {v[1]:.1f} M" for k, v in
                                                sorted(by_helper.items(), key=lambda kv: -kv[1][1])), ""]
    if slow:
        out += ["**Slowest steps (60 s or more):**"] + [f"- {d / 60:.1f} min · {k} · {nm} · `{c}`" for d, k, nm, c in slow] + [""]
    prev = last_report(plan)
    if prev:
        _, name, pm = prev
        out += [f"**Since the last report** ({name}):", "", "| Measure | Last | Now |", "|---|---|---|"]
        for key, label in (("floor_s", "Hook time per call (s)"), ("test_min", "Test runs (min)"),
                           ("tokens_m", "Tokens (M)"), ("wall_min", "Session time (min)"), ("refusals", "Refused steps"),
                           ("ctx_peak_k", "Main context peak (k)"), ("steps_over_200k", "Main steps over 200 k")):
            out.append(f"| {label} | {pm.get(key)} | {m.get(key)} |")
        out.append("")
    # v3.2.9: the top 3 time sinks, then the top 3 token sinks, each with the usual fix (owner-blind)
    FIX = {"test runs": "make a one-test run start in under 1 minute; run long tests in the background",
           "waiting for GitHub": "start the next stage while GitHub tests run; keep each GitHub job under 5 minutes",
           "waiting for you": "fewer stops: join your checks, fewer pull requests, decide questions before approval",
           "model thinking": "fewer steps: read several files in one step, smaller hand-overs",
           "other commands": "look at the slowest steps below",
           "hook time on every call": "hz-claude-config: hooks in one process (from v3.2.7)"}
    tops = sorted(m["time_kinds"].items(), key=lambda kv: -kv[1])[:3]
    total = sum(m["time_kinds"].values()) or 1
    out_top = ["## Top 3 time sinks (time first)", ""] + [
        f"{i}. **{k}**: {v:.0f} min ({v * 100 / total:.0f}%). Fix: {FIX.get(k, '')}." for i, (k, v) in enumerate(tops, 1)]
    tk = dict(m["tokens_by_helper"])
    over = m.get("over_200k_tokens_m")
    if over:
        tk["main context above 200 k"] = over
    tfix = {"main": "type /compact at a stop when the context is above 50%; keep big files out of the main session",
            "main context above 200 k": "type /compact at a stop when the context is above 50%",
            "opus-worker": "give Routine work to sonnet-worker; bigger hand-overs, fewer restarts",
            "sonnet-worker": "fewer test loops; one change, one run",
            "reviewer": "light reviewer for small jobs", "Explore": "one map per stage"}
    ttop = sorted(tk.items(), key=lambda kv: -kv[1])[:3]
    out_top += ["", "## Top 3 token sinks (tokens second)", ""] + [
        f"{i}. **{k}**: {v:.1f} M ({v * 100 / (m['tokens_m'] or 1):.0f}%). Fix: {tfix.get(k, 'look at its steps')}." for i, (k, v) in enumerate(ttop, 1)]
    if m.get("one_test_median_s") and m["one_test_median_s"] > 120:   # the slow one-test finding, in every app
        out_top += ["", f"**Slow one-test runs:** {m['one_test_runs']} runs, median {m['one_test_median_s'] / 60:.1f} min. "
                        "Make a one-test run start in under 1 minute in this app. The next plan offers it as decision A, "
                        f"with the saving (about {m['one_test_runs'] * max(0, m['one_test_median_s'] - 60) / 60:.0f} min on a plan like this)."]
    pc = m.get("parallel") or {}
    if pc.get("pairs"):
        out_top += ["", f"**Parallel candidates:** {pc['minutes']} min could have run side by side (stages that shared no "
                        "file but ran one after another). " + "; ".join(f"Stages {x['stages']}: {x['minutes']} min"
                                                                        for x in pc["pairs"]) + "."]
    else:
        out_top += ["", "**Parallel candidates:** none. Each stage waited for the one before it."]
    out = out[:1] + [""] + out_top + [""] + out[1:]
    out.append("<!-- metrics: " + json.dumps(m) + " -->")
    print("\n".join(out))


if __name__ == "__main__":
    main()
