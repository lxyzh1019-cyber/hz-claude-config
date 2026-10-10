#!/usr/bin/env python3
"""PreToolUse (all checked tools). A worker's memory grows with every step, and every step re-reads it.
v3.1.28: the step count comes from the worker's own record file (<session folder>/subagents/agent-<id>.jsonl),
so it is right however few of the worker's tool calls reach this check — in the Weekly-Planner Sunday v15 session
only file writes reached it (21 counted for a worker of 320 steps). Without that file the hook-call count is used.
At worker_step_warn steps the worker is told once to finish its current fix and report; past worker_step_stop it
must report what is done and what is left, so the main session sends a fresh worker (empty memory) for the rest.
v3.2.0, from the Weekly-Planner consistency pass (a worker ran 11 hours; workers ran 103 test runs one after another;
a worker handed back while 2 of its full test runs still ran, and ending it killed them):
- time limit per worker: Routine (sonnet-worker) warning at 45 min, stop at 60; Complex (opus-worker) warning at 90 min,
  stop at 120. At the stop only the report (and stopping its own runs) is allowed;
- test runs per worker: a warning at 10 ("list all problems, fix them together, run once"), a stop at 20;
- the hand-back is refused once while the worker's own background runs are still going: wait for them, or stop them
  and say so in the report.
The main session is never limited here.
Each call also records which tool reached the check, so the logs show which tools Claude Code sends."""
import json, os
from _common import read_hook_input, deny_tool, load_config, STATE_DIR, log

data = read_hook_input()
cfg = load_config()
aid = next((str(data.get(k)) for k in (cfg.get("subagent_marker_fields") or ["agent_id"]) if data.get(k)), "")
if not aid or aid == str(data.get("session_id")):
    raise SystemExit(0)
tool = str(data.get("tool_name") or "")
warn, stop = int(cfg.get("worker_step_warn", 80)), int(cfg.get("worker_step_stop", 100))
NEVER_REFUSE = set(cfg.get("worker_never_refuse") or ["SubagentHandback", "TaskStop", "KillShell", "TodoWrite"])
HANDBACK = {"SubagentHandback"}
import re as _re
from datetime import datetime as _dt
from _common import is_test_run as _is_test


def record_file():
    """The worker's own transcript, next to the session transcript Claude Code names in the hook input."""
    tp = str(data.get("transcript_path") or "")
    sid = str(data.get("session_id") or "")
    if not tp:
        return None
    base = os.path.dirname(tp)
    name = f"agent-{aid}.jsonl"
    for cand in (tp if os.path.basename(tp) == name else None,
                 os.path.join(base, sid, "subagents", name),
                 os.path.join(base, os.path.splitext(os.path.basename(tp))[0], "subagents", name),
                 os.path.join(base, "subagents", name)):
        if cand and os.path.isfile(cand):
            return cand
    # v3.2.10: a dynamic workflow's helpers keep their records one folder deeper (subagents/workflows/wf_<run>/);
    # real Claude Code 2.1.296: without this, a workflow helper ran 22 test runs with no warning and no stop
    import glob
    for d in (os.path.join(base, sid, "subagents", "workflows"),
              os.path.join(base, os.path.splitext(os.path.basename(tp))[0], "subagents", "workflows")):
        hits = glob.glob(os.path.join(d, "*", name))
        if hits:
            return hits[0]
    return None


def _tests_factor():
    """v3.2.10: 2 for a test-speed helper ('Task kind: test speed' in its first message), else 1."""
    try:
        with open(rf, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"type":"user"' in line.replace(" ", ""):
                    return 2 if _re.search(r"Task kind:\W*test[- ]speed", line, _re.I) else 1
    except (OSError, NameError, TypeError):
        pass
    return 1


def read_record(path):
    """Steps (distinct assistant message ids), first time, test runs, and background runs still going."""
    ids, first, tests, started, ended = set(), None, 0, set(), set()
    ctx, shape, pngs, seen_u = 0, [], 0, set()   # v3.2.0: memory per step, single-read steps, screenshot reads
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if first is None and r.get("timestamp"):
                    first = r["timestamp"]
                if r.get("type") == "assistant":
                    m = r.get("message") or {}
                    ids.add(m.get("id") or r.get("uuid"))
                    _u = m.get("usage") or {}
                    if _u and m.get("id") not in seen_u:
                        seen_u.add(m.get("id"))
                        ctx = sum(int(_u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                                 "cache_creation_input_tokens"))
                    _tu = [b for b in (m.get("content") or []) if isinstance(b, dict) and b.get("type") == "tool_use"] \
                        if isinstance(m.get("content"), list) else []
                    if _tu:
                        shape.append(len(_tu) == 1 and _tu[0].get("name") in ("Read", "Grep", "Glob"))
                        pngs += sum(1 for b in _tu if b.get("name") == "Read" and _re.search(
                            r"\.(png|jpe?g|webp)$", str((b.get("input") or {}).get("file_path") or ""), _re.I))
                    for b in (m.get("content") or []) if isinstance(m.get("content"), list) else []:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash" and \
                                _is_test((b.get("input") or {}).get("command")):
                            tests += 1
                if "running in background with ID:" in line or "moved to the background (ID:" in line:
                    from _common import BG_START_RE   # v3.2.5: both ways a command ends up in the background
                    started.update(BG_START_RE.findall(line))
                if "<task-id>" in line:
                    ended.update(_re.findall(r"<task-id>([A-Za-z0-9_-]+)</task-id>", line))
    except OSError:
        return None
    return {"steps": len(ids), "first": first, "tests": tests, "open": sorted(started - ended), "ctx": ctx,
            "single_reads": next((i for i, s in enumerate(reversed(shape)) if not s), len(shape)),
            "pngs": pngs}


def agent_type(path):
    try:
        return str(json.load(open(path[:-len(".jsonl")] + ".meta.json", encoding="utf-8")).get("agentType") or "")
    except (OSError, ValueError, TypeError):
        return ""


path = os.path.join(STATE_DIR, "worker-steps.json")
try:
    state = json.load(open(path, encoding="utf-8"))
except (OSError, ValueError):
    state = {}
if not isinstance(state.get("agents"), dict):     # v3.1.28 layout; the old {id: count} file is dropped
    state = {"agents": {}}
if len(state["agents"]) > 200:
    state = {"agents": {}}
a = state["agents"].setdefault(aid, {"calls": 0, "tools": {}, "warned": False})
a["calls"] = int(a.get("calls", 0)) + 1
a["tools"][tool] = int(a["tools"].get(tool, 0)) + 1
rf = record_file()
rec = read_record(rf) if rf else None
counted = rec["steps"] if rec else None
n = counted if counted is not None else a["calls"]
a["steps"], a["source"] = n, ("record" if counted is not None else "calls")
a.setdefault("first", (rec or {}).get("first") or _dt.utcnow().isoformat() + "Z")
if rec and rec.get("first"):
    a["first"] = rec["first"]
try:
    minutes = (_dt.utcnow() - _dt.fromisoformat(a["first"].replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 60
except (ValueError, TypeError):
    minutes = 0
kind = (agent_type(rf) if rf else "") or str(data.get("agent_type") or "")
lim = (cfg.get("worker_minutes") or {}).get(kind) or ([45, 60] if "sonnet" in kind else [90, 120])
tests = (rec or {}).get("tests", 0)
ctx = (rec or {}).get("ctx", 0)
single_reads = (rec or {}).get("single_reads", 0)
pngs = (rec or {}).get("pngs", 0)
open_runs = (rec or {}).get("open", [])
say = None
# v3.2.11: a worker runs its tests in the foreground (up to 10 minutes). Weekly-Planner 10 Oct: workers put 7 test runs in
# the background, tried to wait with sleep loops (refused 13 times), then stopped with the run still going; each finished
# run woke the main session again (5 identical ⏳ lines). Refused once per worker, with the fix.
_ti = data.get("tool_input") or {}
if (tool == "Bash" and _ti.get("run_in_background") and _is_test(_ti.get("command"))
        and not a.get("bg_test_refused")):
    a["bg_test_refused"] = True
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(state, open(path, "w", encoding="utf-8"))
    except OSError:
        pass
    log("worker-budget", {"agent": aid, "said": "test in the foreground"})
    deny_tool("Run this test in the foreground and let it finish: no run_in_background, and set the Bash timeout to "
              "600000 (10 minutes). Use the background only for a run you expect to take more than 10 minutes; then "
              "read code meanwhile, with no sleep loop. Run it again now.")
if tool in HANDBACK and open_runs and not a.get("handback_warned"):
    a["handback_warned"] = True
    say = "runs open"
elif tool not in NEVER_REFUSE:
    if n > stop:
        say = "stop"
    elif minutes >= lim[1]:
        say = "time stop"
    elif tests >= int(cfg.get("worker_tests_stop", 20)) * _tests_factor():
        say = "tests stop"
    elif n >= warn and not a.get("warned"):
        say = "wrap up"
        a["warned"] = True
    elif minutes >= lim[0] and not a.get("time_warned"):
        say = "time warn"
        a["time_warned"] = True
    elif tests >= int(cfg.get("worker_tests_warn", 10)) * _tests_factor() and not a.get("tests_warned"):
        say = "tests warn"
        a["tests_warned"] = True
    # v3.2.9: off by default (worker_memory_max 0). Weekly-Planner Stage 9: one stage needed 3 Opus workers because of
    # this limit, each re-reading the same files; model time per step stayed at 2.5 s from 50 k to 200 k context.
    elif int(cfg.get("worker_memory_max", 0)) > 0 and ctx >= int(cfg.get("worker_memory_max", 0)) and not a.get("memory_warned"):
        say = "memory"
        a["memory_warned"] = True
    elif single_reads >= 5 and tool in ("Read", "Grep", "Glob") and not a.get("reads_warned"):
        say = "batch reads"
        a["reads_warned"] = True
    elif pngs >= 1 and tool == "Read" and _re.search(r"\.(png|jpe?g|webp)$", str((data.get("tool_input") or {})
                                                                                 .get("file_path") or ""), _re.I) \
            and not a.get("png_warned"):
        say = "screenshot"
        a["png_warned"] = True
try:
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(state, open(path, "w", encoding="utf-8"))
except OSError:
    pass
# v3.2.0: measured stop signals for the main session — a worker stopped by a limit, or a stage over twice its size
def _signal(reason):
    sp = os.path.join(STATE_DIR, "stop-signals.json")
    try:
        sig = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        sig = []
    sig.append({"agent": aid, "reason": reason, "told": False})
    json.dump(sig[-20:], open(sp, "w", encoding="utf-8"))


_size = None
try:
    _first_user = next((json.loads(l) for l in open(rf, encoding="utf-8", errors="replace")
                        if '"type":"user"' in l.replace(" ", "")), None) if rf else None
    _m = _re.search(r"(?mi)^\s*\**Size:\**\s*([SML])\b", json.dumps((_first_user or {}).get("message") or {})
                   .replace("\\n", "\n"))
    _size = _m.group(1).upper() if _m else None
except (OSError, ValueError):
    pass
_budget = {"S": 15, "M": 45, "L": 90}.get(_size or "", None)


# v3.2.2: the size check counts worked time. Waiting for GitHub runs and for the worker's own background commands is
# left out: in the Weekly-Planner Stage 3a round 2 (size S, two GitHub runs of about 9 minutes each) the stop for a plan
# came at 30 minutes, while the worker waited for the second run, just before its proof.
_GH_WAIT = _re.compile(r"\bgh\s+(run\s+watch|pr\s+checks\b.*--watch|run\s+view\b.*--exit-status)")


def _waited_minutes(path):
    from datetime import datetime as _d2

    def _t(r):
        try:
            return _d2.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None
    total, prev, fg = 0.0, None, {}
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return 0.0
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = _t(r)
        c = (r.get("message") or {}).get("content")
        if r.get("type") == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                    inp = b.get("input") or {}
                    if not inp.get("run_in_background") and _GH_WAIT.search(str(inp.get("command") or "")):
                        fg[b.get("id")] = t
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in fg:
                    t0 = fg.pop(b["tool_use_id"])
                    if t0 and t:
                        total += t - t0     # a GitHub wait in the foreground
        if r.get("type") != "assistant" and "task-notification" in line and prev and t:
            total += t - prev               # idle until the worker's own background command finished
        if t:
            prev = t
    return max(total, 0.0) / 60


_worked = minutes - (_waited_minutes(rf) if rf else 0.0)
if _budget and _worked > 2 * _budget and not a.get("over_signalled"):
    a["over_signalled"] = True
    _signal(f"a stage sized {_size} (about {_budget} min) has worked {round(_worked)} min, over twice its size "
            f"({round(minutes - _worked)} min of waiting for GitHub or background commands left out)")
if say in ("time stop", "tests stop", "stop") and not a.get("stop_signalled"):
    a["stop_signalled"] = True
    _signal({"time stop": "a worker reached its time limit", "tests stop": "a worker reached its test-run limit",
             "stop": "a worker reached its step limit"}[say])
try:
    json.dump(state, open(path, "w", encoding="utf-8"))
except OSError:
    pass
# v3.2.1: a worker's own background full test run, measured when its notice arrives in the worker's record
try:
    from _common import background_test_note as _btn
    _tmsg = _btn(cfg, [json.loads(l) for l in open(rf, encoding="utf-8", errors="replace")]) if rf else ""
except Exception:
    _tmsg = ""
if _tmsg and tool not in NEVER_REFUSE:
    deny_tool(_tmsg + " Retry this step only if it is not a full test run.")
# v3.2.5: a one-time warning is advice, not a refusal. A refused step still re-reads the whole memory (100–250 k tokens in
# the Weekly-Planner Stage 7 helpers) and gets nothing done; the same words reach the model with the tool's result
# (real Claude Code 2.1.293: PreToolUse added text reaches the model). Refusals stay for real stops and for test runs.
from _common import add_context as _advise
if say == "wrap up":
    log("worker-budget", {"agent": aid, "steps": n, "source": a["source"], "said": say})
    _advise("PreToolUse", f"[worker budget] Step {n} of this worker run. Finish the fix you are on in about "
            f"{stop - n if stop > n else 5} steps. Then stop and report what is done and what is left. A fresh worker "
            "continues; that costs less.")
if say == "stop":
    log("worker-budget", {"agent": aid, "steps": n, "source": a["source"], "said": say})
    deny_tool(f"Step limit reached ({stop}). Stop now and write your report: what is done (with evidence), what is "
              "left, and anything half-finished. The main session sends a fresh worker for the rest.")
if say:
    log("worker-budget", {"agent": aid, "kind": kind, "steps": n, "minutes": round(minutes), "tests": tests,
                          "open_runs": open_runs, "said": say})
    try:
        from _common import live_proof
        live_proof("worker-budget", {"said": say, "kind": kind, "minutes": round(minutes), "tests": tests})
    except ImportError:
        pass
if say == "runs open":
    deny_tool("Your own test runs are still going (" + ", ".join(open_runs[:4]) + "). Ending now stops them and their "
              "results are lost. Wait for them, or stop them and say so in your report. Then hand back.")
if say == "time warn":
    _advise("PreToolUse", f"[worker budget] This worker run is at {round(minutes)} minutes; the limit is {lim[1]}. "
            "Finish the fix you are on. Then report what is done and what is left.")
if say == "time stop":
    deny_tool(f"Time limit reached ({lim[1]} minutes). Stop your own runs if any still go. Then write your report: "
              "what is done (with evidence), what is left, and anything half-finished.")
if say == "tests warn":
    deny_tool(f"You ran {tests} test runs. Find all, fix all, check once: list every open problem, fix them together, "
              "then run the tests one time. Retry this step if it is that run.")
if say == "tests stop":
    deny_tool(f"Test-run limit reached ({tests}). Stop and write your report: what passes, what still fails, and your "
              "fix for each. The main session decides the next step.")
if say == "memory":
    _advise("PreToolUse", f"[worker budget] This worker re-reads about {round(ctx / 1000)} k tokens per step; the budget is "
            f"{round(int(cfg.get('worker_memory_max', 250000)) / 1000)} k. Finish the fix you are on and report what is done "
            "and what is left. A fresh worker continues with a small memory.")
if say == "batch reads":
    _advise("PreToolUse", "[worker budget] Your last 5 steps each read one thing, and every step re-reads your whole "
            "memory. From now on read all the files or parts you need in one step: several Read or Grep calls together.")
if say == "screenshot":
    _advise("PreToolUse", "[worker budget] Opening a screenshot costs many tokens. Compare pictures in code (compare "
            "instructions); open one only when the task is a visual check.")

# v3.2.7: slow test runs repeated after small changes. Weekly-Planner 8 Oct: one Sonnet worker ran the same one-test smoke
# run 6 times in a row, each about 3 minutes, with one debug line changed between runs (17 of its 26 minutes). Advice
# once, before the third slow run: gather every debug print in one change, change once, run once, run it in the background.
def _slow_runs(path, limit=120):
    from datetime import datetime as _dt
    def _t(r):
        try:
            return _dt.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None
    out, pend = [], {}
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return out
    for line in lines:
        if '"tool_' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        c = (r.get("message") or {}).get("content")
        for b in c if isinstance(c, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") == "Bash" and _is_test(str((b.get("input") or {}).get("command") or "")):
                pend[b.get("id")] = _t(r)
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pend:
                t0, t1 = pend.pop(b["tool_use_id"]), _t(r)
                if t0 and t1 and t1 - t0 >= limit:
                    out.append(t1 - t0)
    return out


if tool == "Bash" and rf and not a.get("slow_tests_advised") and _is_test(str((data.get("tool_input") or {}).get("command") or "")):
    _sr = _slow_runs(rf)
    if len(_sr) >= 2:
        a["slow_tests_advised"] = True
        try:
            json.dump(state, open(path, "w", encoding="utf-8"))
        except (OSError, NameError):
            pass
        log("worker-budget", {"agent": aid, "said": "slow tests", "runs": len(_sr)})
        _advise("PreToolUse", f"[worker budget] Your last {len(_sr)} test runs took about {round(sum(_sr) / len(_sr) / 60, 1)} "
                "min each. Before the next one: put every debug print you need into one change, make one change, and run "
                "once. Run it in the foreground with a 10-minute timeout (timeout 600000) and let it finish.")
