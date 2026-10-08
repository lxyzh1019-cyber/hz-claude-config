#!/usr/bin/env python3
"""PreToolUse hook on Edit/Write: log every edit attempt; in enforce mode, block source edits that
do not come from the executor subagent unless the main session is explicitly authorized.
observe mode only logs — run ROUTING-TEST.md (hz-claude-config) to learn which input fields mark a subagent
before switching to enforce."""
import os, sys
from _common import read_hook_input, load_config, is_governance_path, deny_tool, log, STATE_DIR

data = read_hook_input()
cfg = load_config()
mode = cfg.get("routing_guard_mode", "observe")
if mode == "off":
    sys.exit(0)
inp = data.get("input") or data.get("tool_input") or {}
path = inp.get("file_path") or inp.get("path") or ""
# Fields observed in the hook input that could identify a subagent; recorded for the test.
subagent_markers = {k: data.get(k) for k in ("agent_id", "agent_name", "agent_type", "subagent", "parent_session_id", "session_id") if k in data}
env_markers = {k: v for k, v in os.environ.items() if "AGENT" in k.upper()}
log("routing-guard", {"mode": mode, "tool": data.get("tool_name"), "path": path,
                      "hook_keys": sorted(data.keys()), "markers": subagent_markers, "env": env_markers})
if mode != "enforce":
    sys.exit(0)
if is_governance_path(path, cfg):
    sys.exit(0)
# v3.2.0: Claude's own scratch folder (…/Temp/claude/…) is not app code. In the
# Weekly-Planner consistency pass two writes there were refused for nothing.
if path and __import__("re").search(r"[\\/]temp[\\/]claude[\\/]", path.replace("\\", "/").lower()):
    sys.exit(0)
if os.path.exists(os.path.join(STATE_DIR, "main-session-edit-authorized")):
    sys.exit(0)
is_worker = any(v for v in subagent_markers.values() if v and str(v) != str(data.get("session_id")))
marker_fields = cfg.get("subagent_marker_fields") or []
if marker_fields:
    is_worker = any(data.get(f) for f in marker_fields)
if is_worker:
    # Hard rule: sonnet-worker never changes the files that hold shared data rules, settings, build or deploy set-up.
    if str(data.get("agent_type") or "") == "sonnet-worker":
        norm = path.replace("\\", "/").lower()
        hit = next((g for g in cfg.get("sonnet_protected_paths", []) if g.lower() in norm), None)
        if hit:
            deny_tool(f"sonnet-worker may not change '{path}' (shared data rules, settings, build or deploy set-up). Stop "
                      "and return: 'Escalate to opus-worker: this task needs " + hit + "'.")
    sys.exit(0)
deny_tool(f"Routing rule: a worker makes source edits, opus-worker or sonnet-worker ({path}). Send this change to a "
          "worker. Or ask me to allow main-session edits (touch .claude/state/main-session-edit-authorized).")
