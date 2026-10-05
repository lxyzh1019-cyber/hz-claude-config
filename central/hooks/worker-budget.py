#!/usr/bin/env python3
"""PreToolUse (all checked tools). A worker's memory grows with every step, and every step re-reads it.
v3.1.28: the step count comes from the worker's own record file (<session folder>/subagents/agent-<id>.jsonl),
so it is right however few of the worker's tool calls reach this check — in the Weekly-Planner Sunday v15 session
only file writes reached it (21 counted for a worker of 320 steps). Without that file the hook-call count is used.
At worker_step_warn steps the worker is told once to finish its current fix and report; past worker_step_stop it
must report what is done and what is left, so the main session sends a fresh worker (empty memory) for the rest.
The worker's own hand-back is never refused. The main session is never limited here.
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
NEVER_REFUSE = set(cfg.get("worker_never_refuse") or ["SubagentHandback", "TaskStop", "TodoWrite"])


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
    return None


def steps_in(path):
    """Model steps = distinct assistant message ids (one step can hold several tool calls)."""
    ids = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"assistant"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("type") == "assistant":
                    m = r.get("message") or {}
                    ids.add(m.get("id") or r.get("uuid"))
    except OSError:
        return None
    return len(ids)


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
counted = steps_in(rf) if rf else None
n = counted if counted is not None else a["calls"]
a["steps"], a["source"] = n, ("record" if counted is not None else "calls")
say = None
if tool not in NEVER_REFUSE:
    if n > stop:
        say = "stop"
    elif n >= warn and not a.get("warned"):
        say = "wrap up"
        a["warned"] = True
try:
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(state, open(path, "w", encoding="utf-8"))
except OSError:
    pass
if say == "wrap up":
    log("worker-budget", {"agent": aid, "steps": n, "source": a["source"], "said": say})
    deny_tool(f"Step {n} of this worker run: finish the fix you are on within about {stop - n if stop > n else 5} "
              "steps, then stop and report what is done and what is left. A fresh worker (empty memory) will continue "
              "— that costs less than carrying everything so far. Retry this step if you still need it.")
if say == "stop":
    log("worker-budget", {"agent": aid, "steps": n, "source": a["source"], "said": say})
    deny_tool(f"Step limit reached ({stop}). Stop now and write your report: what is done (with evidence), what is "
              "left, and anything half-finished. The main session sends a fresh worker for the rest.")
