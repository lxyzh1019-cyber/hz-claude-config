#!/usr/bin/env python3
"""PostToolUse on Bash (v3.2.0): measure how long each full test run takes, in the main session and in workers.
A full run is a test run without a subset marker (SMOKE_ONLY=, --grep, -g, --shard, a single test file).
When a full run takes longer than the limit (default 5 minutes), the session is told once per app to add a stage
"split the test suite into parts that run side by side" to the current plan, before other build stages.
Weekly-Planner's smoke suite took about 9.5 minutes per run; test runs were about half of all worker time.
State: .claude/state/test-speed.json {"slowest_full_minutes", "command", "told", "split_done"}."""
import json, os, re, sys, time
from datetime import datetime
from _common import (read_hook_input, load_config, add_context, log, read_transcript, live_proof, is_full_test_run,
                     test_speed_note)

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
cmd = str(inp.get("command") or "")
if inp.get("run_in_background"):   # v3.2.1: background runs are measured at their notice (plan-gate, worker-budget)
    sys.exit(0)
if not is_full_test_run(cmd, cfg):
    sys.exit(0)
# when did this command start? the newest tool call with this exact command in this transcript
start = None
for rec in reversed(read_transcript(data.get("transcript_path"))):
    if rec.get("type") != "assistant":
        continue
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_use" and
                                   str((b.get("input") or {}).get("command") or "") == cmd for b in c):
        try:
            start = datetime.fromisoformat(str(rec.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            pass
        break
if start is None and data.get("duration_ms") is None:
    sys.exit(0)
start = start or time.time()
minutes = (time.time() - start) / 60
if data.get("duration_ms") is not None:      # v3.2.1: the real run time from Claude Code (2.1.293 sends it)
    minutes = float(data.get("duration_ms") or 0) / 60000
log("test-speed", {"full_run_minutes": round(minutes, 1)})
live_proof("test-speed", {"full_run_minutes": round(minutes, 1)})
_msg = test_speed_note(cfg, minutes, cmd)
if _msg:
    add_context("PostToolUse", _msg)
