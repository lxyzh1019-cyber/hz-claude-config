#!/usr/bin/env python3
"""PreToolUse hook on Edit/Write: log every edit attempt; in enforce mode, block source edits that
do not come from the executor subagent unless the main session is explicitly authorized.
observe mode only logs. Enforce has been the setting since the measured test (its notes are in git history)."""
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
    # v3.2.12: the main session hands record, plan-file and git work to the worker of the stage. Weekly-Planner 10 Oct:
    # 142 main steps re-read 172 k each (15.5 M, 53%), many of them record and plan updates. A notice, once per prompt.
    _pp = path.replace("\\", "/")
    if (not data.get("agent_id") and data.get("tool_name") in ("Edit", "Write", "MultiEdit") and not os.environ.get("HZ_LEAN_MAIN_OFF")
            and (os.path.basename(_pp) in ("WORKING_RECORD.md", "FEATURES.md") or "/plans/" in _pp)):
        try:
            import json as _j
            from _common import prompt_number as _pn, add_context as _ac
            _f = os.path.join(STATE_DIR, "lean-main.json")
            try:
                _s = _j.load(open(_f, encoding="utf-8"))
            except (OSError, ValueError):
                _s = {}
            _k = f"{data.get('session_id')}:{_pn(data.get('session_id'))}"
            if _s.get("last") != _k:
                os.makedirs(STATE_DIR, exist_ok=True)
                _j.dump({"last": _k}, open(_f, "w", encoding="utf-8"))
                log("routing-guard", {"lean_main": os.path.basename(path)})
                _ac("PreToolUse", "[lean main] Each step of this main session re-reads all of it. Put record rows, "
                    "plan-file changes, commits and pushes into the hand-over of the stage's worker ('Also: update the "
                    "record row, commit and push'). Do this one yourself only when no worker runs next.")
        except SystemExit:
            raise
        except Exception:
            pass
    sys.exit(0)
# v3.2.0: Claude's own scratch folder (…/Temp/claude/…) is not app code. In the
# Weekly-Planner consistency pass two writes there were refused for nothing.
if path and __import__("re").search(r"[\\/]temp[\\/]claude[\\/]", path.replace("\\", "/").lower()):
    sys.exit(0)
if os.path.exists(os.path.join(STATE_DIR, "main-session-edit-authorized")):
    sys.exit(0)
def _named_github_change(d):
    """v3.2.11: True when this worker's hand-over has a line 'Named change: .github/<file> ...'. A redesign of the
    GitHub jobs stays with opus-worker; a named one-line change (a trigger, a timeout, a path) may go to Sonnet."""
    import glob, re as _r
    tp, aid = str(d.get("transcript_path") or ""), str(d.get("agent_id") or "")
    if not tp or not aid:
        return False
    base = tp[:-6] if tp.endswith(".jsonl") else tp
    for f in glob.glob(os.path.join(base, "subagents", f"agent-{aid}.jsonl")) + glob.glob(
            os.path.join(base, "subagents", "workflows", "*", f"agent-{aid}.jsonl")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"user"' in line:
                        return bool(_r.search(r"Named change:\s*\S*\.github/", line.replace("\\n", "\n"), _r.I))
        except OSError:
            pass
    return False


is_worker = any(v for v in subagent_markers.values() if v and str(v) != str(data.get("session_id")))
marker_fields = cfg.get("subagent_marker_fields") or []
if marker_fields:
    is_worker = any(data.get(f) for f in marker_fields)
if is_worker:
    # Hard rule: sonnet-worker never changes the files that hold shared data rules, settings, build or deploy set-up.
    if str(data.get("agent_type") or "") == "sonnet-worker":
        norm = path.replace("\\", "/").lower()
        hit = next((g for g in cfg.get("sonnet_protected_paths", []) if g.lower() in norm), None)
        if hit == ".github/" and _named_github_change(data):
            hit = None   # v3.2.11: a change in .github/ that the hand-over names exactly ('Named change: .github/...')
        if hit:
            deny_tool(f"sonnet-worker may not change '{path}' (shared data rules, settings, build or deploy set-up). Stop "
                      "and return: 'Escalate to opus-worker: this task needs " + hit + "'.")
    sys.exit(0)
deny_tool(f"Routing rule: a worker makes source edits, opus-worker or sonnet-worker ({path}). Send this change to a "
          "worker. Or ask me to allow main-session edits (touch .claude/state/main-session-edit-authorized).")
