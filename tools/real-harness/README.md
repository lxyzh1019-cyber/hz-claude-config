# Real-session harness (v3.2.1)

Runs the real Claude Code program against a scripted stand-in model, with the real central checks as hooks.
The program runs its real tools, writes real session files and sends real notices; only the model's answers are scripted.

- `stand_in_model.py` — answers `/v1/messages` with scripted steps; a hand-over with `Task: W<n>` is answered as a worker.
- `scenario_workers.sh <hooks dir> <label>` — four background workers started one after another (the Weekly-Planner
  consistency pass case). Prints `started` or `REFUSED` per worker.

Needs: the Claude Code program (`CLAUDE_BIN`, e.g. from `npm pack @anthropic-ai/claude-code-linux-x64`), Python 3, git.
Result on 2026-10-08 with Claude Code 2.1.293: 3.2.0 refused all four ("Another worker is running" — it counted the
worker being started); 3.2.1 started all four.

Cannot test: the real model's choices, the desktop app screens, phone notices, GitHub.
