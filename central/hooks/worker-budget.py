#!/usr/bin/env python3
"""PreToolUse (all checked tools), v3.1.26: a worker's memory grows with every step, and every step re-reads it.
At worker_step_warn steps the worker is told once to finish its current fix and report; past worker_step_stop it
must report what is done and what is left, so the main session sends a fresh worker (empty memory) for the rest.
The main session is never limited here."""
import json, os
from _common import read_hook_input, deny_tool, load_config, STATE_DIR, log

data = read_hook_input()
cfg = load_config()
aid = next((str(data.get(k)) for k in (cfg.get("subagent_marker_fields") or ["agent_id"]) if data.get(k)), "")
if not aid or aid == str(data.get("session_id")):
    raise SystemExit(0)
warn, stop = int(cfg.get("worker_step_warn", 120)), int(cfg.get("worker_step_stop", 150))
path = os.path.join(STATE_DIR, "worker-steps.json")
try:
    steps = json.load(open(path, encoding="utf-8"))
except (OSError, ValueError):
    steps = {}
if len(steps) > 200:
    steps = {}
n = int(steps.get(aid, 0)) + 1
steps[aid] = n
try:
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(steps, open(path, "w", encoding="utf-8"))
except OSError:
    pass
if n == warn:
    log("worker-budget", {"agent": aid, "steps": n, "said": "wrap up"})
    deny_tool(f"Step {n} of this worker run: finish the fix you are on within about {stop - warn} steps, then stop and "
              "report what is done and what is left. A fresh worker (empty memory) will continue — that costs less "
              "than carrying everything so far. Retry this step if you still need it.")
if n > stop:
    log("worker-budget", {"agent": aid, "steps": n, "said": "stop"})
    deny_tool(f"Step limit reached ({stop}). Stop now and write your report: what is done (with evidence), what is "
              "left, and anything half-finished. The main session sends a fresh worker for the rest.")
