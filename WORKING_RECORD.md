# WORKING RECORD — hz-claude-config — rules v3

## Approved baseline
- Plan v4 approved 2026-09-25: central rules via hz-rules plugin (local, user scope) and cloud environment setup script; per-repo pointer CLAUDE.md; one-time migration then retire the sync workflow.

## Pending
- Pilot on one app repo (cloud + local); routing-guard measured test.

## Request ledger
| # | Round/date | Requirement (user's words, short) | Status | Note |
|---|---|---|---|---|
| 1 | 2026-09-25 | rules referenced from one central place, no per-repo PR per update | open | pilot pending |

## Hotspot counter
| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |
|---|---|---|---|---|---|---|
| rules distribution | 3 | 0 | 0 | 0 | per-repo copies needed a PR per update | yes 2026-09-25 (Plan v4) |
Thresholds: 3 fix rounds, 2 recurrences, 1 regression caused by a fix, or 3 workarounds/exceptions → no further patch until the rewrite-vs-repair comparison is presented; then set the last cell to "yes <date>". The hooks read this table: keep the header words.

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| hz-rules v3.0.0 built | COMPLETE | replay 37/37; cloud install simulated; migration simulated on 3 repo states |
| Cloud environment live | NOT STARTED | |
| Local plugin installed | NOT STARTED | |
| App repos migrated | NOT STARTED | |

## Checks and evidence
- 2026-09-25 replay-hooks.sh 37/37; install-cloud idempotent; setup-script success and failure paths; migration on v2-zip, v2.5 and own-CLAUDE.md repos

## Open questions / blockers
- Does the cloud VM run hooks from ~/.claude/settings.json written by the setup script? (pilot)
- Is codeload/github archive download allowed under the environment's network setting? (pilot)
