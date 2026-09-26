# FEATURES — hz-claude-config — manifest v1 — confirmed 2026-09-25

## Central rules plugin (plugins/hz-rules)
- Rules text in `rules/CLAUDE-rules.md`; version lives only in `.claude-plugin/plugin.json`
- Hooks: session-start (rules injection unless loaded natively, version, per-repo checks, hotspot alerts), plan-gate (plan tier, read-history, fix-count reminder, hotspot alerts), skill-router, routing-guard (observe mode), record-guard (manifest, record, regression table), validation-line
- Agent `opus-worker` (model opus, effort medium)
- Skills `hz-guarantee-audit`, `hz-plan-regression-guard`
- Seed templates `FEATURES.md`, `WORKING_RECORD.md`
- Hook test suite `hooks/replay-hooks.sh`, isolated temp project, all checks must pass

## Delivery
- Marketplace catalog `.claude-plugin/marketplace.json` (name `hz-config`) for local user-scope install
- Cloud installer `cloud/install-cloud.sh` + `cloud/setup-script.txt`: pinned release, installs into every home's `~/.claude`, idempotent, keeps user keys, writes a stop-and-report CLAUDE.md on failure
- Local user settings `docs/local-user-settings.json` (model, permissions)

## One-time migration (retire after all repos migrated)
- `scripts/sync.sh` + `workflow-migrate.yml`: removes rules-v2 copies (`retired.txt`), unmerges v2 settings, adds pointer `CLAUDE.md` (keeps a repo's own content), restores an overwritten README, seeds per-repo files, one PR per repo

## Regression table format
| Feature | vOld → vNew | Note |
|---|---|---|
