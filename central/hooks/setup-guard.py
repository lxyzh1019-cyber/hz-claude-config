#!/usr/bin/env python3
"""Stop hook: when session start updated this repository's setup files, no other answer may go out until the
setup-update branch holds the update commit (v3.2.4; pushed for the pull request). A micro-plan for it (Status: Proposed) may go out."""
import json, os, re, subprocess, sys
from _common import read_hook_input, load_config, read_transcript, last_assistant_text, block, use_round, PROJECT_DIR

data = read_hook_input()
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
text = last_assistant_text(read_transcript(data.get("transcript_path")))
m = re.search(cfg["validation_line_pattern"], text or "")
if m and m.group(2).split()[0] == "Proposed":
    sys.exit(0)
r = use_round("setup", data.get("session_id"), 2)
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
block(f"Do the setup update first, as the session start says. Put the updated setup files on the branch {branch} "
      "from origin/main. Push it. Open the pull request, ready for review. Switch back. In the 'I need from you' "
      "line, ask me to merge it. Send only that. The branch must hold the commit of the updated files: an empty branch "
      "does not count.", kind="work")
