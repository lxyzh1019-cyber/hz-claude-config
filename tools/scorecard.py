#!/usr/bin/env python3
"""v3.3.7 (piece 9): the scorecard of one job. Usage: python3 tools/scorecard.py <session.jsonl>
It reads only the session file and its subagents folder and prints one line per check: name · PASS or FAIL · numbers.
The logic is central/hooks/scorecard.py (the hook writes the same lines into the pull request text)."""
import os, runpy, sys

sys.argv = [sys.argv[0]] + sys.argv[1:]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "central", "hooks", "scorecard.py"),
               run_name="__main__")
