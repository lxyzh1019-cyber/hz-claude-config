# FEATURES — hz-claude-config — manifest v2 — confirmed 2026-09-25

## Central content (central/) — fetched by every repo's loader at session start
- `MANIFEST.txt`: first line `version: X.Y.Z` (the only place the version lives), then every file the loader fetches; rebuilt with `tools/build_manifest.py`
- Rules text `rules/CLAUDE-rules.md`, injected at session start
- Hooks: session-start (rules, version, worker/skills paths, per-repo checks, hotspot alerts), plan-gate, skill-router (points to central skill files), routing-guard (observe mode), record-guard, validation-line
- Worker instructions `agents/opus-worker-instructions.md`
- Skills `hz-guarantee-audit`, `hz-plan-regression-guard`; seed templates `FEATURES.md`, `WORKING_RECORD.md`
- Test suite `hooks/replay-hooks.sh` (isolated temp project; manifest consistency; loader fetch, cache, offline and refusal paths)

## Stub (stub/) — installed once per repository, stable
- `hz-loader.py`: fetch MANIFEST + files from public raw GitHub, cache per version (keep 3), run hook scripts, offline fallback, stop message when nothing cached
- `settings.json` (model, permissions, hooks → loader), thin `opus-worker.md`, `CLAUDE-pointer.md`
- `install-stub.sh`: one-command install per repo — retire v2 copies and probe files, restore an overwritten README, unmerge v2 settings, merge stub settings, pointer CLAUDE.md, seed per-repo files, smoke test

## This repository
- Carries the same stub at its root, so rules apply when editing it

## Regression table format
| Feature | vOld → vNew | Note |
|---|---|---|
