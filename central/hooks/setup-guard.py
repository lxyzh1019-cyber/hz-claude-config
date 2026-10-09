#!/usr/bin/env python3
"""Stop hook: when session start updated this repository's setup files, no other answer may go out until the
setup-update branch holds the update commit (v3.2.4; pushed for the pull request). A micro-plan for it (Status: Proposed) may go out."""
import json, os, re, subprocess, sys
from _common import read_hook_input, load_config, read_transcript, last_assistant_text, block, use_round, PROJECT_DIR

data = read_hook_input()

# v3.2.8: the session opens (or links) the setup pull request, so Claude Code shows its card. One reminder at most.
_pr_path = os.path.join(PROJECT_DIR, ".claude", "state", "setup-pr.json")
try:
    _pr = json.load(open(_pr_path, encoding="utf-8"))
except (OSError, ValueError):
    _pr = None
if _pr and str(_pr.get("session") or "") == str(data.get("session_id") or ""):
    _b = re.escape(str(_pr.get("branch") or ""))
    _recs = read_transcript(data.get("transcript_path"))
    _done = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash"
                and re.search(r"\bgh\s+pr\s+(create|edit)\b[^\n]*" + _b, str((b.get("input") or {}).get("command") or ""))
                for r in _recs if r.get("type") == "assistant" and not r.get("isSidechain")
                for b in (((r.get("message") or {}).get("content")) or []) if isinstance(((r.get("message") or {}).get("content")), list))
    from _common import refused_by_safety_check as _rsc8, last_turn as _lt8
    if _done or _rsc8(_lt8(_recs)):
        try:
            os.remove(_pr_path)
        except OSError:
            pass
    elif ((lambda r: r[1] if r is not None else not data.get("stop_hook_active"))(use_round("setup-pr", data.get("session_id"), 1))):
        block(f"Open the setup pull request now with the gh command from the session start (gh pr create … --head "
              f"{_pr.get('branch')} …, or gh pr edit {_pr.get('branch')} … if it exists). Claude Code then shows its card. "
              "Then answer again, with 'merge it' in the 'I need from you' line.", kind="work")
path = os.path.join(PROJECT_DIR, ".claude", "state", "setup-pending.json")
try:
    branch = json.load(open(path, encoding="utf-8")).get("branch")
except (OSError, ValueError):
    sys.exit(0)


def exists():
    # v3.2.4: the branch must hold the update commit. An empty branch (same commit as main) used to release the session
    # (Weekly-Planner 2026-10-08), and the setup then never reached the repository.
    from _common import setup_branch_state
    return setup_branch_state(PROJECT_DIR, branch) in ("pending", "unknown")   # v3.2.5: a branch not pushed does not count


if exists():
    try:
        os.remove(path)
    except OSError:
        pass
    sys.exit(0)
cfg = load_config()
_records = read_transcript(data.get("transcript_path"))
from _common import refused_by_safety_check, last_turn
if refused_by_safety_check(last_turn(_records)):
    sys.exit(0)   # v3.2.6: the safety check refused the commit; a send-back cannot help and would repeat the reply
text = last_assistant_text(_records)
m = re.search(cfg["validation_line_pattern"], text or "")
if m and m.group(2).split()[0] == "Proposed":
    sys.exit(0)
r = use_round("setup", data.get("session_id"), 1)   # v3.2.6: one send-back at most (two made three replies)
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
block(f"Do the setup update first, as the session start says. Put the updated setup files on the branch {branch} "
      "from origin/main. Push it. Open the pull request, ready for review. Switch back. In the 'I need from you' "
      "line, ask me to merge it. Send only that. The branch must hold the commit of the updated files: an empty branch "
      "does not count.", kind="work")
