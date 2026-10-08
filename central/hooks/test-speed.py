#!/usr/bin/env python3
"""PostToolUse on Bash (v3.2.0): measure how long each full test run takes, in the main session and in workers.
A full run is a test run without a subset marker (SMOKE_ONLY=, --grep, -g, --shard, a single test file).
When a full run takes longer than the limit (default 5 minutes), the session is told once per app to add a stage
"split the test suite into parts that run side by side" to the current plan, before other build stages.
Weekly-Planner's smoke suite took about 9.5 minutes per run; test runs were about half of all worker time.
State: .claude/state/test-speed.json {"slowest_full_minutes", "command", "told", "split_done"}."""
import json, os, re, sys, time
from datetime import datetime
from _common import read_hook_input, load_config, add_context, log, STATE_DIR, read_transcript, is_test_run, live_proof

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
cmd = str(inp.get("command") or "")
if inp.get("run_in_background") or not is_test_run(cmd):
    sys.exit(0)
SUBSET = cfg.get("test_subset_markers") or [r"SMOKE_ONLY=", r"--grep\b", r"\s-g\s", r"--shard\b", r"\.(spec|test)\.[jt]s\b",
                                            r"--testNamePattern", r"\s-t\s", r"::"]
if any(re.search(p, cmd) for p in SUBSET):
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
if start is None:
    sys.exit(0)
minutes = (time.time() - start) / 60
path = os.path.join(STATE_DIR, "test-speed.json")
try:
    st = json.load(open(path, encoding="utf-8"))
except (OSError, ValueError):
    st = {}
limit = float(cfg.get("full_test_max_minutes", 5))
if minutes > float(st.get("slowest_full_minutes") or 0):
    st["slowest_full_minutes"], st["command"] = round(minutes, 1), cmd[:200]
os.makedirs(STATE_DIR, exist_ok=True)
json.dump(st, open(path, "w", encoding="utf-8"))
log("test-speed", {"full_run_minutes": round(minutes, 1)})
live_proof("test-speed", {"full_run_minutes": round(minutes, 1)})
if minutes > limit and not st.get("told") and not st.get("split_done"):
    st["told"] = True
    json.dump(st, open(path, "w", encoding="utf-8"))
    add_context("PostToolUse", f"[test speed] This full test run took {round(minutes, 1)} minutes; the aim is {int(limit)} "
                "or less. Add a stage to the current plan, as its next Rev, before other build stages: split the test "
                "suite into parts that run side by side, locally and on GitHub, with the same checks and results. When "
                "it is done, add the line 'Test speed: full run <n> min in <k> parts' to FEATURES.md ## References.")
