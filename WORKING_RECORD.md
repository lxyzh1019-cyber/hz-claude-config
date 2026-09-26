# WORKING RECORD — hz-claude-config — central v3.1.0

## Approved baseline
- Plan v5 approved 2026-09-25: central content in hz-claude-config fetched at session start by a stable per-repo loader stub; no setup script, no plugin; one-time stub install per repo.

## Pending
- Pilot on one app repo (confirms cross-repo fetch); rollout to the other five; routing-guard measured test.

## Request ledger
| # | Round/date | Requirement (user's words, short) | Status | Note |
|---|---|---|---|---|
| 1 | 2026-09-25 | rules referenced from one central place, no per-repo PR per update | open | pilot pending |
| 2 | 2026-09-25 | test before building ("wasted 6 hours") | done | cloud probe passed: repo hooks run, fetch works, Stop hook forces fix |

## Hotspot counter
| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |
|---|---|---|---|---|---|---|
| rules distribution | 5 | 0 | 0 | 0 | v4 relied on cloud behaviour the docs rule out | yes 2026-09-25 (Plan v5, probe-verified) |
Thresholds: 3 fix rounds, 2 recurrences, 1 regression caused by a fix, or 3 workarounds/exceptions → no further patch until the rewrite-vs-repair comparison is presented; then set the last cell to "yes <date>". The hooks read this table: keep the header words.

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| central v3.1.0 + stub built | COMPLETE | replay 41/41; install-stub simulated on 3 repo states |
| hz-claude-config updated on main | NOT STARTED | |
| Pilot app repo | NOT STARTED | |
| Other app repos | NOT STARTED | |

## Checks and evidence
- 2026-09-25 cloud probe (user): SessionStart hook ran (python 3.11.15, cloud=true); raw fetch from hz-claude-config OK; Stop hook forced a correction once.
- 2026-09-25 replay-hooks.sh 41/41.

## Open questions / blockers
- Cross-repo raw fetch from an app repo's session (pilot's install smoke test answers it).
- Local PC: Python and bash present? (optional local check)
