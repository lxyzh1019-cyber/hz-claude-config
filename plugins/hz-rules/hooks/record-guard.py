#!/usr/bin/env python3
"""Stop hook: if files were changed (or a worker was dispatched) this turn, the working record must be
updated and a regression table produced. Governance-only edits are exempt from the regression table."""
import os, re, sys
from _common import (PROJECT_DIR, SEED_DIR, read_hook_input, load_config, read_transcript, last_turn, last_assistant_text,
                     tool_uses, is_governance_path, block)

data = read_hook_input()
if data.get("stop_hook_active"):
    sys.exit(0)
cfg = load_config()
turn = last_turn(read_transcript(data.get("transcript_path")))
edits = tool_uses(turn, {"Edit", "Write", "MultiEdit", "NotebookEdit"})
dispatched = bool(tool_uses(turn, {"Agent", "Task"}))
paths = [(e.get("input") or {}).get("file_path") or (e.get("input") or {}).get("path") or "" for e in edits]
source_paths = [p for p in paths if p and not is_governance_path(p, cfg)]
record_touched = any(p.endswith(cfg["record_file"]) for p in paths)
if not source_paths and not dispatched:
    sys.exit(0)
text = last_assistant_text(turn)
problems = []
features_path = os.path.join(PROJECT_DIR, cfg["features_file"])
try:
    features_is_template = "<app or plan name>" in open(features_path, encoding="utf-8").read()
except OSError:
    features_is_template = True
if features_is_template:
    block(f"{cfg['features_file']} is missing or still the unfilled template, so no regression check is possible. "
          f"Before finishing: if it is missing, create it and {cfg['record_file']} from the templates in {SEED_DIR}; "
          "then extract the manifest of the app's current locked features into it (hz-plan-regression-guard), "
          f"produce the regression table and update {cfg['record_file']}.")
if not record_touched:
    problems.append(f"update {cfg['record_file']} (request ledger, hotspot counter, deliverable ledger)")
if not re.search(cfg["regression_table_pattern"], text):
    problems.append("end with the regression table (kept / added / intentionally removed / missing) "
                    f"against {cfg['features_file']}, and update the manifest if features changed")
if problems:
    block("Implementation happened this turn but the record is incomplete. Before finishing: " + "; ".join(problems) + ".")
sys.exit(0)
