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

- `scenario_setup_update.sh <central dir> <label> <app repo folder>` (v3.2.4) — the real Claude Code starts a session in a
  copy of a real app repository. The loader fetches the rules from a local web server (`HZ_CENTRAL_URL`), so the
  session-start setup check of the served version runs for real. Prints what the session was told and whether
  `reviewer.md` changed on disk. Weekly-Planner main on 2026-10-08: 3.2.3 left it at effort medium; 3.2.4 wrote effort high.

- `scenario_v325.sh <hooks dir> <label>` (v3.2.5) — a worktree holds the real plan, a command is moved to the background after
  its time limit, and the session ends with a restart line for the real plan. Prints the program's own message for the
  moved command, whether the Stop check noticed it, and what the hand-off check saved for the next step.
- `scenario_handback_prompt.sh <hooks dir> <label>` (v3.2.5) — a helper's hand-back text arrives as the prompt; prints the
  log of the prompt check (3.2.4: tier full and a planner suggestion; 3.2.5: skipped as a hand-back).

Not reproducible here: helpers get no `SubagentHandback` tool in this harness, so hand-backs are tested as prompts.

  With `HZ_LOCAL_REMOTE=1` (v3.2.6) origin is a local bare copy and `gh` is a stand-in: it prints the branch, the files and the
  message of the commit that the session start pushed, the pull request call, and the state of the working folder.
  Older Weekly-Planner main (6e04104): 3.2.5 left 6 changed files in the folder for the model to commit; 3.2.6 pushed the
  branch itself and left the folder clean.

Result on 2026-10-08 with Claude Code 2.1.293: 3.2.1 — closing lines 2, summaries 2, no text reached the model;
3.2.2 — the texts reached the model at the helper start and at the finish notice; summaries 1; closing lines 1 when
the model follows. Also seen: PreToolUse added text reaches the model; SessionStart runs again on `--resume`.

Cannot test: the real model's choices, the desktop app screens, phone notices, GitHub.
