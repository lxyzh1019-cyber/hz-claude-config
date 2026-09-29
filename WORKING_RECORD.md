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
| 3 | 2026-09-28 | Sonnet 5.5 subagent; roles per model | built | v3.1.7; live check = ROUTING-TEST step 2b (alias → 5.5, marker) |
| 4 | 2026-09-28 | suggest planner model (A + B); completion % vs plan; auto-fix when not done | built | v3.1.8; live check = Step F test 4 |
| 5 | 2026-09-29 | version at the top of the first reply; plain Result / I need from you / Next top; stub check; health check; multi-repo fallback (user: yes) | built | v3.1.11; live check = Step B in default mode, then Step F |
| 6 | 2026-09-29 | fewer Step B rounds: checks switched on centrally | built | v3.1.12; live check = Step F in a repo after Step B |
| 7 | 2026-09-29 | reduce rework: build in the repo, test first, one batch | built | v3.1.13 rules text; live check = the next change goes through Step E |

## Hotspot counter
| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |
|---|---|---|---|---|---|---|
| rules distribution | 5 | 0 | 0 | 1 | v4 relied on cloud behaviour the docs rule out | yes 2026-09-25 (Plan v5, probe-verified) |
| record guard | 2 | 0 | 1 | 0 | lost shell-write detection (regression vs local v2) | yes 2026-09-25 (repair chosen over rewrite; comparison in chat) |
| hotspot table reader | 2 | 0 | 0 | 0 | escaped pipe inside a cell shifted the columns (false alert) | no |
Thresholds: 3 fix rounds, 2 recurrences, 1 regression caused by a fix, or 3 workarounds/exceptions → no further patch until the rewrite-vs-repair comparison is presented; then set the last cell to "yes <date>". The hooks read this table: keep the header words.

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| central v3.1.0 + stub built | COMPLETE | replay 41/41; install-stub simulated on 3 repo states |
| v3.1.1: installer keeps repo sections of a v2 CLAUDE.md; central version bump as update test | COMPLETE | 4 repo states incl. Weekly-Planner copy; re-runs unchanged; replay 41/41 |
| hz-claude-config updated on main | BLOCKED — merge is the user's step (rules: user merges on GitHub; git-guard blocks push to main) | v3.1.13 contents pushed on claude/ecstatic-sagan-dajv62, PR #10 open ready for review, replay 114/114; `central/MANIFEST.txt` on main still reads 3.1.10 until that merge |
| Pilot app repo | BLOCKED — Step B denied by the auto-mode classifier ("code from external"); rerun in default permission mode | main of Weekly-Planner still has the 3.1.6 stub (checked 2026-09-29) |
| Other app repos | BLOCKED — same as the pilot: Step B in default mode | Figure-Skate, Swimming: 3.1.6 stub on main; spelling-pronun: Step B denied in auto mode (2026-09-29) |

## Checks and evidence
- 2026-09-29 v3.1.13 into the repository (Step A): `hz-claude-config-v3.1.13.zip` unpacked into the root with Python, replacing every tracked file, zip removed. New `central/hooks/dispatch.py` and `stubcheck.py`; RULES.review-rev12 → rev13; claude-ai-preferences-carve-out.txt → claude-ai-preferences.txt. Replay 114/114. PR #10 opened ready for review; main is 3.1.10 until the user merges.
- 2026-09-29 v3.1.13 (same undeployed release as 3.1.11/3.1.12; 3.1.10 still on main): rule "Changing hz-claude-config" — test the riskiest live assumption first, one agreed batch, build in the repository (Step E paste), deploy and health-check before the next design. Root cause of today's rework: six versions built on untested live assumptions and stacked undeployed. README Step E gets a paste template; this record gets a "Next batch" list. Replay 114/114.
- 2026-09-29 v3.1.12 (same undeployed release as 3.1.11): user asked why Step B keeps coming back. Stub now registers one central switchboard (`dispatch.py`) per hook event instead of one entry per check; `config.json` → `dispatch` lists the checks. Adding or changing a check no longer needs Step B; model, advisor, permissions, workers, pointer, new event types and the loader still do. Stub check now looks for the switchboard on each event. Replay 114/114.
- 2026-09-29 v3.1.11: user feedback — version not at the top of the first reply; reports too technical for a non-programmer; Step B denied twice in auto mode. Added: first-line version check and plain three-line top (Result / I need from you / Next) in validation-line; `[stub]` check at session start (plain list of what is missing, fix = Step B in default mode); `[update]` notice in hz-claude-config; pointer multi-repo fallback (read rules as text, never run a script; "hooks inactive" opener); installer refreshes an existing pointer in place; README Step F health check; docs/claude-ai-preferences.txt replaces the one-line carve-out. Replay 105/105.
- 2026-09-28 v3.1.10: pull requests open ready for review, not as drafts (sessions had opened draft PRs, an extra click before merging). git-guard denies `gh pr create --draft/-d`; stub allows `gh pr ready`; rules require a draft made by any other route to be marked ready before the final report. Replay 94/94.
- 2026-09-28 v3.1.9: Step A of 3.1.8 in an auto-mode cloud session — `git add -A && git commit && git push` denied by the auto-mode classifier ("Instruction Poisoning": the commit replaces `.claude/settings.json`/hooks, and this repo's own CLAUDE.md said not to edit them here). Fix: narrow `permissions.allow` for git status/add/commit/push and gh pr create (resolve before the classifier; deny list and git-guard unchanged), CLAUDE.md of this repo reworded, README: run Steps A/B/E in default or plan mode. Replay 90/90.
- 2026-09-28 v3.1.8 (same release as 3.1.7, not yet deployed): user problem "session said done, completion % showed items open". Added completion-guard Stop hook (ledger-driven Completion line; auto-fix loop max 3 rounds/turn keyed on the turn uuid — this hook deliberately ignores stop_hook_active; evidence required for COMPLETE; "stop here"/"pause here" lets one report stand), `[completion]` line at session start and prompt, `[planner]` suggestion in plan-gate (Fable on strong signals only; the hook cannot switch models), `advisorModel: fable` in the stub (Opus 5.5 main + Fable advisor is an accepted pairing per the advisor docs; workers inherit; sonnet-worker told never to consult). Replay 89/89.
- 2026-09-28 v3.1.7: Sonnet 5.5 released (Claude Code v2.1.284: `sonnet` alias → 5.5, default effort medium). Session model `fable` → `opus` (Opus 5.5 planner; Anthropic HAProxy rewrite: Opus 5.5 9.5 h vs Fable 5.1 12 h, 51% cheaper; user switches to Fable manually when needed). Added `sonnet-worker` (stub change → Step B re-run in installed repos): Routine/micro-plan assignments to Sonnet, Diagnostic/Redesign/shared state to Opus, escalation blocker, fallback relaxed for Routine only, plan-gate names the default executor per tier, worker reports its model, ROUTING-TEST gains step 2b. Rules §Routing rewritten (Rev 12), guidance sources extended. Replay 69/69.
- 2026-09-27 v3.1.6: ask prompts for commit/push/merge removed (user merges on GitHub; auto mode must not stop for branch pushes); deploy asks removed too; gh pr merge denied; git-guard blocks commit on / push to main. Re-run test on an installed repo removes the old asks; found and fixed: the installer guard treated the stub's own worker file as a local v2 change. Plan-gate now honours explicit "skip the plan" wording (Step A and B prompts include it). Replay 67/67.
- 2026-09-27 Weekly-Planner "Looks Calm and Pop": interim update while workers 1B/1C ran was forced into final format by the Stop hook. v3.1.5 adds progress reports (Progress line, accepted only after a worker was dispatched; record update still required, no regression table). Replay 55/55.
- 2026-09-27 Local session works on `main` (older branch had loaded v2.1). v3.1.4 adds: My Environment rewritten for local sessions on GitHub Desktop clones, plan-numbering rule (Plan vN per conversation, R-numbers per repo), README local-branch note. Replay 50/50.
- 2026-09-26 Weekly-Planner: cloud session loaded v3.1.3 with no repo change (central update proven). False hotspot alert on Sister Sync: reader split on escaped pipes inside a cell; fixed in 3.1.4 with a malformed-row notice (replay 50/50).
- 2026-09-25 Weekly-Planner pilot: INSTALL OK, smoke line v3.1.0, npm test green, PR #98. Found 3 regressions versus that repo's locally improved v2 hooks (ARCHITECTURE.md exemption, shell-updated record, **yes review cells) — central was built without reading the repo's current hooks. Fixed in 3.1.3 (replay 48/48); installer now refuses when v2 files were locally changed.
- 2026-09-25 Weekly-Planner: safety check refused `curl | bash` without explicit permission (expected; Step B prompt now includes it). v2 record-guard flagged a turn that changed nothing (plan file outside the repo + worker attempt) — same logic was in central; fixed in 3.1.2, replay 44/44.
- 2026-09-25 Weekly-Planner session read the installer first and found its CLAUDE.md had a repo section under the v2 rules; installer fixed in v3.1.1 to keep such sections.
- 2026-09-25 cloud probe (user): SessionStart hook ran (python 3.11.15, cloud=true); raw fetch from hz-claude-config OK; Stop hook forced a correction once.
- 2026-09-25 replay-hooks.sh 41/41.

## Next batch
Ideas raised mid-work, not in the current build. Agree the list, then build once.
- (proposed 2026-09-29) Revision markers: colour square only at the start of each changed line, with a one-line legend at the top, instead of "🟦 **Rev 1**" on every line — awaiting user decision.

## Open questions / blockers
- Cross-repo raw fetch from an app repo's session (pilot's install smoke test answers it).
- Local PC: Python and bash present? (optional local check)
