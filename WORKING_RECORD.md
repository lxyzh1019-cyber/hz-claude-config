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
| 3 | 2026-09-26 | replace repo with hz-claude-config-v3.1.3.zip, run replay, PR | done | draft PR #3; replay 48/48 |
| 4 | 2026-09-26 | (found) hotspot table rows malformed as shipped in v3.1.3 zip | open | awaiting user decision: repair before merging PR #3 |

## Hotspot counter
| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |
|---|---|---|---|---|---|---|
| rules distribution | 5 | 0 | 0 | 1 |
| record guard | 2 | 0 | 1 | 0 | lost shell-write detection (regression vs local v2) | no | v4 relied on cloud behaviour the docs rule out | yes 2026-09-25 (Plan v5, probe-verified) |
Thresholds: 3 fix rounds, 2 recurrences, 1 regression caused by a fix, or 3 workarounds/exceptions → no further patch until the rewrite-vs-repair comparison is presented; then set the last cell to "yes <date>". The hooks read this table: keep the header words.

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| central v3.1.0 + stub built | COMPLETE | replay 41/41; install-stub simulated on 3 repo states |
| v3.1.1: installer keeps repo sections of a v2 CLAUDE.md; central version bump as update test | COMPLETE | 4 repo states incl. Weekly-Planner copy; re-runs unchanged; replay 41/41 |
| hz-claude-config updated on main | PARTIAL | v3.1.3 on branch claude/quirky-wozniak-mhtuai, draft PR #3 (commit 2b48572); not merged |
| Pilot app repo | NOT STARTED | |
| Other app repos | NOT STARTED | |

## Checks and evidence
- 2026-09-26 v3.1.3 zip extracted over the tracked tree: files byte-identical to zip, no git mode changes, replay-hooks.sh passed=48 failed=0. Hotspot table as shipped: "rules distribution" row has 5 cells, "record guard" row fused with old row tail; hooks now alert on both rows. Not a fix round (release install), counts unchanged.
- 2026-09-25 Weekly-Planner pilot: INSTALL OK, smoke line v3.1.0, npm test green, PR #98. Found 3 regressions versus that repo's locally improved v2 hooks (ARCHITECTURE.md exemption, shell-updated record, **yes review cells) — central was built without reading the repo's current hooks. Fixed in 3.1.3 (replay 48/48); installer now refuses when v2 files were locally changed.
- 2026-09-25 Weekly-Planner: safety check refused `curl | bash` without explicit permission (expected; Step B prompt now includes it). v2 record-guard flagged a turn that changed nothing (plan file outside the repo + worker attempt) — same logic was in central; fixed in 3.1.2, replay 44/44.
- 2026-09-25 Weekly-Planner session read the installer first and found its CLAUDE.md had a repo section under the v2 rules; installer fixed in v3.1.1 to keep such sections.
- 2026-09-25 cloud probe (user): SessionStart hook ran (python 3.11.15, cloud=true); raw fetch from hz-claude-config OK; Stop hook forced a correction once.
- 2026-09-25 replay-hooks.sh 41/41.

## Open questions / blockers
- Cross-repo raw fetch from an app repo's session (pilot's install smoke test answers it).
- Local PC: Python and bash present? (optional local check)
