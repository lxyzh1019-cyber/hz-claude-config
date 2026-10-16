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
# v3.3.3 (owner, 15 Oct: "one problem, one fix, re-check again"): at the second failing test run of this prompt, one
# note: list every failure, fix them all, then run once. 15 Oct: 2 failing full runs fixed in separate rounds.
try:
    from _common import is_test_run as _itr, prompt_number as _pn, STATE_DIR as _SD
    if _itr(cmd):
        _resp = data.get("tool_response") or {}
        _out = (json.dumps(_resp, ensure_ascii=False) if not isinstance(_resp, str) else _resp)[-6000:]
        if re.search(r"\b(FAILED|FAIL:|failed|failures?=[1-9]|AssertionError|✗|[1-9]\d* failing)\b", _out):
            _p = os.path.join(_SD, "test-failures.json")
            try:
                _st = json.load(open(_p, encoding="utf-8"))
            except (OSError, ValueError):
                _st = {}
            _k = f"{data.get('session_id')}:{_pn(data.get('session_id'))}:{data.get('agent_id') or 'main'}"
            _st[_k] = _st.get(_k, 0) + 1
            os.makedirs(_SD, exist_ok=True)
            json.dump(_st, open(_p, "w", encoding="utf-8"))
            if _st[_k] == 2:
                log("test-speed", {"find_all_note": _k})
                add_context("PostToolUse", "[find all] Second failing test run. Before the next run, list every failure "
                            "this run shows, fix them all together, then run once. Pick a check's inputs (lakes, "
                            "dates, users) from the data in one step, not by trying.")
except Exception:
    pass
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
