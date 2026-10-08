# Real-session harness (v3.2.1)

Runs the real Claude Code program against a scripted stand-in model, with the real central checks as hooks.
The program runs its real tools, writes real session files and sends real notices; only the model's answers are scripted.

- `stand_in_model.py` — answers `/v1/messages` with scripted steps; a hand-over with `Task: W<n>` is answered as a worker.
- `scenario_workers.sh <hooks dir> <label>` — four background workers started one after another (the Weekly-Planner
  consistency pass case). Prints `started` or `REFUSED` per worker.

Needs: the Claude Code program (`CLAUDE_BIN`, e.g. from `npm pack @anthropic-ai/claude-code-linux-x64`), Python 3, git.
Result on 2026-10-08 with Claude Code 2.1.293: 3.2.0 refused all four ("Another worker is running" — it counted the
worker being started); 3.2.1 started all four.

- `scenario_early_report.sh <hooks dir> <label>` (v3.2.2) — a background helper still runs when the session would
  write its report. `OBEY=1`: the scripted model follows the wait text. Prints closing lines shown, summaries shown,
  early reports logged, and whether the wait and report texts reached the model.

Result on 2026-10-08 with Claude Code 2.1.293: 3.2.1 — closing lines 2, summaries 2, no text reached the model;
3.2.2 — the texts reached the model at the helper start and at the finish notice; summaries 1; closing lines 1 when
the model follows. Also seen: PreToolUse added text reaches the model; SessionStart runs again on `--resume`.

Cannot test: the real model's choices, the desktop app screens, phone notices, GitHub.
