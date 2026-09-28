# FEATURES — hz-claude-config — manifest v3 — 2026-09-28

## Central content (central/) — fetched by every repo's loader at session start
- `MANIFEST.txt`: first line `version: X.Y.Z` (the only place the version lives), then every file the loader fetches; rebuilt with `tools/build_manifest.py`
- Rules text `rules/CLAUDE-rules.md`, injected at session start
- Hooks: session-start (rules, version, worker/skills paths, per-repo checks, hotspot alerts; table reader honours escaped pipes and reports malformed rows), plan-gate (tier + default executor per tier; `[planner]` Fable suggestion on strong signals; pause phrase; `[completion]` line when items are open), skill-router (points to central skill files), routing-guard (observe mode), git-guard (no commit on / push to main; no draft pull requests), record-guard (counts only changes inside the repo; worker turns only if git shows source changes; record updates by shell count; ARCHITECTURE.md exempt), validation-line (final answers: Confidence/Status line; progress reports while workers run: Progress line, only after a dispatch), completion-guard (ledger Completion line on implementation turns; auto-fix: blocks a done claim with open items, up to 3 rounds per turn; evidence required for COMPLETE; pause phrases; plans/questions/progress untouched)
- Worker instructions `agents/opus-worker-instructions.md` (shared by `opus-worker` and `sonnet-worker`; Sonnet escalation blocker; worker reports its model)
- Skills `hz-guarantee-audit`, `hz-plan-regression-guard`; seed templates `FEATURES.md`, `WORKING_RECORD.md`
- Test suite `hooks/replay-hooks.sh` (isolated temp project; manifest consistency; loader fetch, cache, offline and refusal paths)

## Stub (stub/) — installed once per repository, stable
- `hz-loader.py`: fetch MANIFEST + files from public raw GitHub, cache per version (keep 3), run hook scripts, offline fallback, stop message when nothing cached
- `settings.json` (model `opus` — Opus 5.5 session; `advisorModel: fable` — Fable 5.1 consulted at decision points; permissions: no prompts at all, allow rules for branch git add/commit/push, gh pr create and gh pr ready (classifier-free in auto mode; deny + git-guard still apply), destructive git and `gh pr merge` denied; hooks → loader incl. `git-guard`, `completion-guard`), thin `opus-worker.md` (Opus 5.5, medium: Diagnostic/Redesign/shared state) and `sonnet-worker.md` (Sonnet 5.5, medium: Routine micro-plan tier), `CLAUDE-pointer.md`
- `install-stub.sh`: one-command install per repo — retire v2 copies and probe files, restore an overwritten README, unmerge v2 settings, merge stub settings, refuses when v2 rules files were locally changed (`v2-known-files.txt`), pointer CLAUDE.md keeping any repo-specific sections of a v2 CLAUDE.md (`split_claude_md.py`), seed per-repo files, smoke test

## This repository
- Carries the same stub at its root, so rules apply when editing it

## Regression table format
| Feature | vOld → vNew | Note |
|---|---|---|
