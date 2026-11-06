# Revision record — hz-claude-config

Version: 3.3.7
Built on: 3.3.6
Owner: the newest "Claude Code Plan Work Strategy" chat: the owner chat writes the paste block; Claude Code builds and tests (owner D2, 28 Oct). Other chats send P-lines here.

Run before every pull request: `revision_gate.py <new-folder> <fresh clone of GitHub main>` from the account skill `anthropic-skills:hz-change-guard`. Any FAIL stops the pull request.
Every package: Windows line endings (CRLF); the dry-run starts from a Windows-style copy of the owner's real folder state, and its count must match GitHub Desktop.

Proof rule (owner, 5 Nov): every fix's test starts from real files (an app's real settings, the owner's real session files). It must fail on the old version and pass on the new one.
Fix-round limit (owner, 5 Nov): a fix that failed is "attempt N" of its item; attempt 3 needs a rewrite-or-repair comparison before any code.
Owner rule (5 Nov): the plan title is not the identity of a plan and not part of its revision. A plan is known by its file; a reworded title is the same plan, and the title line is never marked.

## Features (each phrase must stay in this repo's files; one line per FEATURES.md item)
F01 MANIFEST.txt: first line version: X.Y.Z (the only place the version li | MANIFEST.txt
F02 Rules text rules/CLAUDE-rules.md, injected at session start | rules/CLAUDE-rules.md
F03 All text read from subprocesses and hook input is UTF-8 whatever the P | All text read from subprocesses and hook input is
F04 End-of-task summary (stats.py, Stop, systemMessage — no AI turn): toke | stats.py
F05 Version line Rules vX · branch · setup <state> shown in the Stop notic | Rules vX · branch · setup <state>
F06 Hand-off and plan versions (v3.1.24): handoff-guard.py (Stop) sends ba | handoff-guard.py
F07 setup-guard (Stop): no other answer before the setup-update branch exi | setup-guard
F08 Completion counted by plan (<plan name> · Stage k of M rows) with QUEU | <plan name> · Stage k of M
F09 Plan check: framed Summary table, changes box whenever Rev labels exis | Plan check: framed Summary table, changes box when
F10 Skill router v2: hz-reviewer, hz-planner, hz-chat-handoff, hz-designer | Skill router v2: hz-reviewer, hz-planner, hz-chat-
F11 QA/QC: rules section for everything handed to the user; qc-guard (Stop | QA/QC: rules section for everything handed to the
F12 Switchboard hooks/dispatch.py: the stub registers it for UserPromptSub | hooks/dispatch.py
F13 Hooks: session-start (rules, version, worker/skills paths, per-repo ch | [stub]
F14 Worker instructions agents/opus-worker-instructions.md (shared by opus | agents/opus-worker-instructions.md
F15 Skill hz-change-guard: the account skill anthropic-skills:hz-change-guard since v3.3.7 (D7 = B; the central copy is removed) | hz-change-guard
F16 Test suite hooks/replay-hooks.sh (isolated temp project; manifest cons | hooks/replay-hooks.sh
F17 hz-loader.py: fetch MANIFEST + files from public raw GitHub, cache per | hz-loader.py
F18 settings.json (plansDirectory: ./plans — plan files land in the reposi | settings.json
F19 install-stub.sh: one-command install per repo — retire v2 copies and p | install-stub.sh
F20 Pointer CLAUDE.md with the multi-repo fallback (rules read as text, "h | CLAUDE.md
F21 docs/claude-ai-preferences.txt: the claude.ai preferences block (quote | docs/claude-ai-preferences.txt
F22 README Step F: live health check per repository; Step E paste template | README Step F: live health check per repository; S
F23 Rules "Changing hz-claude-config": test first, one batch, build in the | WORKING_RECORD.md
F24 Carries the same stub at its root, so rules apply when editing it | Carries the same stub at its root, so rules apply
F25 v3.1.25: plan-guard sends back file names, line numbers, commit codes | Technical details
F26 v3.1.26: plans right the first time — session start gives the plan sha | PLAN_TEMPLATE
F27 v3.1.26: 'Find all, fix all, check once' — rule, session-start fact an | Test runs: n
F28 v3.1.26 (fewer re-reads and send-backs): rules-read-guard (a shell rea | Read(~/.cache/hz-rules/**)
F29 v3.1.26: build state first in the 📌 Result line; no code changes, file | v3.1.26: build state first in the 📌 Result line; n
F30 v3.1.27: shape first, then one plan version — agreed points live in ## | ## Design decisions
F31 v3.1.28: worker step limit counts the worker's own record (distinct st | waiting
F32 v3.1.29: session start sends only short facts (under 10,000 characters | .claude/state/session-facts.md
F33 v3.1.30: planner helpers (planner.md on Fable 5.1, planner-opus.md on | planner.md
F34 v3.1.31: only "work" problems are sent back; other Stop problems are s | .claude/state/pending-fixes.json
F35 v3.1.32: each app names its picture sizes and looks in FEATURES.md ## | FEATURES.md
F36 v3.1.33: a plan keeps its number while discussed, with a Round <k> cha | Round <k>
F37 v3.2.0: core rules plus role files, no character cap; one format file | formats.py
F38 v3.2.1: finished background workers are counted as finished, so new wo | v3.2.1: finished background workers are counted as
F39 v3.2.2: one full report per piece of work — report-timing.py (PreToolU | report-timing.py
F40 v3.2.3: hz-designer added to the skill router; the unused hz-guarantee | hz-guarantee-audit
F41 v3.2.4: setup update fixes — a setup branch is "waiting" only when it | _common.setup_branch_state
F42 v3.2.5: notices — _common.is_notice_text covers <task-notification> an | _common.is_notice_text
F43 v3.2.6: stubupdate._publish — the session start commits the staged set | stubupdate._publish
F44 v3.2.7: per-session state (sess_get/sess_set: rules-read, prompt numbe | sess_get
F45 v3.2.8: the session opens the setup pull request (gh pr create --base | gh pr create --base main --head <branch>
F46 v3.2.8 (also): git-guard reads cd/git -C folders in the Git Bash form | git -C
F47 v3.2.9: plan Quick read (formats.PLAN_TEMPLATE, quick_read_words; the | formats.PLAN_TEMPLATE
F48 v3.2.9 (also): worker memory limit off by default (worker_memory_max 0 | worker_memory_max
F49 v3.2.9 (also): the report ranks the Top 3 time sinks and Top 3 token s | v3.2.9 (also): the report ranks the Top 3 time sin
F50 v3.2.10: dynamic workflows (worker-budget.py finds workflow helper rec | worker-budget.py
F51 v3.2.11: Routine defined by a known answer (worker-guard.py text; 'ref | worker-guard.py
F52 v3.2.12: one ⏳ line per round (plan-gate.py and report-timing.py share | plan-gate.py
F53 v3.2.13: restart lines checked against GitHub (branch_merged_on_github | branch_merged_on_github
F54 v3.2.14: workers run in the foreground (foreground-workers.py rewrites | foreground-workers.py
F55 v3.2.15: reads no longer start the checks (app hook list without Read | event_matchers_absent
F56 v3.2.16: only necessary stops and one pull request per stop (rules, pl | [stops]
F57 v3.2.17: plan colours through the plan file, Rev after approval, notice | notice-guard.py
F58 v3.2.17: tappable questions with notice first and what follows each op | ask-guard.py
F59 v3.3.0: lead playbook with Rule 0, payoff score and the feedback loop | **Rule 0.**
F60 v3.3.0: hand-overs carry Files lines, Test and Steps; workers do not wait | A hand-over carries the map
F61 v3.3.0: plan window shows the marked text you approve; one colour line | Read that file and show the plan again
F62 v3.3.0: scorecard one session by default, lead rows, rule rows in reports | ## Rule rows (feedback loop)
F63 v3.3.1: no self wake-ups after a stop | wake-guard.py
F64 v3.3.2: default first: one session builds; old method only with HZ_FULL_RULES | ## 1. Default first
F65 v3.3.3: green and red per section, change list in words, report and numbers | def session_table
F66 v3.3.3: read-only steps never wait for the rules; changes still do | _read_only_bash
F67 v3.3.3: plan marks added when the plan file is written; no extra showing | plan-write-marks.py
F68 v3.3.4: the report in the checkpoint shape with the measured part and the approved plan | def measured_part
F69 v3.3.4: a cd before git never makes Claude Code ask | a cd and a git command in one step
F70 v3.3.4: plans/ in the local git ignore list | --git-common-dir
F71 v3.3.4: browser pictures in the chat for screen changes | Those pictures stay visible in the chat.
F72 v3.3.5: the summary in the Weekly-Planner shape, bold lines, no tables | def summary_block
F74 v3.3.6: safe git steps on the work branch are approved | def _safe_git_only
F76 v3.3.7: the settings merge removes the retired ask rules (deploy asks kept) | RETIRED_ASK
F77 v3.3.7: git-guard approves the real git step shapes on the work branch | _GIT_ENV
F78 v3.3.7: a plan is known by its file; the title is no revision | "identity": "plan file"
F79 v3.3.7: a reason line when no earlier showing exists | NO_BASE_LINE
F80 v3.3.7: merge state from git or GitHub REST | def merged_on_main
F81 v3.3.7: permission waits, send-backs and helper time from the session file | def permission_waits
F82 v3.3.7: the check writes the report into the pull request text | <!-- hz-report -->
F83 v3.3.7: checks read with GitHub REST | def state(repo, sha)
F84 v3.3.7: test speed per script | def test_script_key
F85 v3.3.7: the feature check in the app's GitHub test run | feature_check.py
F86 v3.3.7: the scorecard in the pull request text | <!-- hz-scorecard -->
F87 v3.3.7: the clear-context option at plan approval | showClearContextOnPlanAccept

## Removed (approved, with reason)
F73 v3.3.6: the rules version at the end of the status line | reason: its fix-first fired 4 times in 3 sessions; the Stop notice already shows the version | approved: owner, 5 Nov paste block (piece 5)
F75 v3.3.6: a merge request needs the code-made summary after the checks (the paste send-back) | reason: Build 4 was sent back twice and the summary landed after the closing lines; the check now delivers the summary and the report itself | approved: owner, 5 Nov paste block (piece 4)
- The central copy of hz-change-guard (central/skills/hz-change-guard) | reason: D7 = B, the account skill anthropic-skills:hz-change-guard loads in local and cloud sessions | approved: owner, 5 Nov paste block (piece 7)
- Soft hand-back notice for a worker at 150 k tokens (3.2.11 list item 3) | reason: 3.2.9 switched the memory limit off because restarts re-read the same files and cost more; on 10 Oct only 1 of 5 workers passed 150 k | approved: owner, 10 Oct ("yes, drop item 3")

## Open problems (stay until fixed with proof or he drops them)
X49 Re-showings after a send-back got no colour marks when the title was reworded (Build 3: 0 marks at 9:02 and 9:08 PM), and the session's own "What changed since Rev N" gave a second number | attempt 1 (3.3.7): plan-guard knows a plan by its file; the title is no change and never marked; "What changed since Rev N" follows the marks; a reason line when the plan names an earlier Rev the check has not seen; at most one marks refusal per showing; an edit of the approved plan file is its next Rev (no refusal) | proof: tools/real-harness/replay_plan_showings.py — Build 3 on 3.3.6: 0 and 0 marks; on 3.3.7: 19 and 33, each "since" one below the newest mark; Build 4: 8 and 18 on both; synthetic 4 showings: Rev 1, Rev 1 no marks, Rev 2 (1 mark), Rev 3 (1 mark), Plan v2 at Rev 1, title never marked (3.3.6: 0 marks on all) | Open until scorecard check 2 passes in the first real job
P04 X48 G1 reopened (git questions on the work branch): the 3.3.6 proof wrote a settings.json with no ask rules, a setup no app has. Builds 2–4: 10 questions, 260 min, all reasonCode rule:projectSettings; the real steps carried "2>&1 | tail", "GIT_AUTHOR_EMAIL=…", "git -c user.email=…" or a here-document, so the hook approved none of them and the old ask rule asked | found: 2026-11-05 | attempt 1 (3.3.7): the settings merge removes the retired ask rules (deploy asks kept, gh pr merge stays denied); git-guard approves those real shapes | proof so far: tools/real-harness/scenario_v337_git.py 7/7 on the real Trout settings d70bc8a (3.3.6 asks on 4 of 4 real step shapes, 3.3.7 on 0 of 4 and pushes) | stays Open until scorecard check 1 passes in the first real job
P02 Model-dependent solutions (one review per pull request, lean main session, Part names, report link copied, short test output) are proven only by a live session | found: 2026-10-11 campaign | next: the live scorecard in each end report shows works / does not work

X50 The completion line and the summary used the hooks' own state: Build 4's session start said "0 of 2 done — Build 2, Build 3" after #19 and #20 had merged; Build 3's "Slowest steps" listed two git questions (17.6 and 12.4 min); send-backs showed 0; Build 4's Explore helper showed 0.0 min | attempt 1 (3.3.7): merge state from git (git fetch origin, merge commits on origin/main) or gh api REST, never gh pr; permission waits (source user_temporary or user_permanent) are waits for me; send-backs and refusals counted from the session file; helper time from the helper's own file (central/hooks/session_facts.py) | proof: Build 4 session start replayed on a clone at main d3e3c0d, branch build-2 8909ad3: 3.3.6 "0 of 2 done", 3.3.7 "2 of 2 merged on GitHub main", also with CLAUDE_CODE_REMOTE=true and a gh that answers 403; Build 3 summary: the two git questions are gone from Slowest steps, send-backs 3 (2 hook refusals, 1 Stop block); Build 4: Explore 1.8 min | Open until scorecard check 4 passes in the first real job

X51 The Stop check sent the session back to paste .claude/state/pr-summary.md (Build 4: twice, at 1:25 and 1:39 PM), and the summary landed after the closing lines | attempt 1 (3.3.7): the paste send-back is removed; the check writes the report and the scorecard into the pull request text itself with GitHub REST (gh api -X PATCH, between <!-- hz-… --> markers) and shows the summary as its own notice after the checks are read (pr_checks.py waits with REST); when REST fails, one note asks the session to write the saved text with the GitHub tool | proof: tools/real-harness/replay_stops.py on Build 4 records 2188 and 2243: 3.3.6 sends back both, 3.3.7 neither; simulated cloud session (CLAUDE_CODE_REMOTE=true, gh pr and gh issue answer 403): the report reaches the pull request text (tools/test_v337_items.py) | Open until the first real job's pull request carries the report with no send-back

X52 Send-back list (36 points in the 21 default hooks: 20 keep, 12 replace, 4 remove): notices sent back although they named the number waiting (Build 3 11:38 AM, Build 4 1:25 PM); a ledger edit piped to tail refused as a rules read (Build 2 4:19 PM); 6 false full-test refusals (a slow npm test refused npm run check); the 'Rules v' fix-first fired 4 times in 3 sessions; gh pr and gh issue in hooks and instructions answer 403 in a cloud session | attempt 1 (3.3.7): notice-guard accepts the number of waiting decisions; rules-read-guard looks for the rules path after the read verb; ask-guard and validation-line save fixes instead of sending back; no ' · Rules v<version>' in the status line; test speed is measured per script; git-guard's notes-only commit reads git's staged list; 'worker running', 'reviewer first', 'wait for GitHub tests' and the plan reviewer gate only in the old method (HZ_FULL_RULES); merge-guard reads checks with GitHub REST; every gh pr and gh issue call or instruction replaced by git, gh api REST or the GitHub tool (git-guard, merge-guard, notice-reminder, stubupdate, setup-guard, session-start, plan-gate, pr-ready-guard, _common, opus-worker-instructions); in a cloud session the setup pull request opens with the GitHub tool | proof: tools/real-harness/replay_stops.py on the 4 real notice Stops: 3.3.6 sends back 4, 3.3.7 2 (Build 2 8:29 and 8:41 PM); tools/test_v337_items.py | Open until scorecard checks 3 and 5 pass in the first real job

X53 D5 (clear the context at plan approval, same session): setting shipped in 3.3.7 ("showClearContextOnPlanAccept": true in the stub settings, so cloud sessions get it too); hooks link the session across a clear only after a live job, local or cloud, shows the clear option (scorecard watch line) | proof: stub/settings.json; tools/test_v337_items.py | Open until a live job shows the clear option

X54 Rules and skills against the owner's Settings Rev 4 (D7 = B): the central copy of hz-change-guard is removed and every reference points to the account skill anthropic-skills:hz-change-guard (skill-router.json, record-guard text, opus-worker-instructions, session start, replay-hooks.sh, test_v3212_items.py, FEATURES.md, CLAUDE.md, this record); helpers get the feature list in the hand-over (they cannot load skills); FORMATS said "run workers in the background … end your turn with ⏳" while the rules say foreground — one text now; rules section 5 "Answers (from my Settings Rev 4)" replaces the STE line "Start with the result…"; the one-repository rule for cloud sessions | attempt 1 (3.3.7) | record guard (redesign limit): repair, text only (one skill name), no logic | proof: replay-hooks.sh v3.3.7 checks (FORMATS and the rules agree on foreground workers; no central copy); tools/superseded-v337.txt | Open until the scorecard watch line shows the account skill loaded in a cloud session

X55 Audit backbone (D4 = B): Build 3 changed js/lake-sheet.js, and Escape in the 3D view then also closed the lake panel; no check tied a changed file to the feature it carries | attempt 1 (3.3.7): rules — feature audit before a change (Covered, Overlap, Conflict, Untouched; each touched feature names its check and it passes on the old code first); FEATURES.md map lines end with "— files: <files> — test: <test name>"; central/checks/feature_check.py in the app's GitHub test run (changed files from git diff, the map, the pull request text; never the plan) | proof: HZ_Trout_Map merge d3e3c0d with a sample map (lake panel → js/lake-sheet.js, no test): red ✗ naming the lake panel; no map: a notice and a pass (tools/test_v337_items.py) | Open until an app's next real job adds the map and the step

X56 Scorecard (D8 = B): no code judged a version on the owner's own jobs | attempt 1 (3.3.7): central/hooks/scorecard.py (tools/scorecard.py runs it by hand) reads only the session file and its subagents folder; 5 checks (git prompts on a work branch, plan re-showings, phone notices, summary vs session file, config waste) plus the review pass and watch lines; the hook writes the lines into the pull request text between <!-- hz-scorecard --> markers when the pull request opens and at the merge stop, also in a cloud session | proof on the 3.3.6 sessions: check 1 FAIL (Build 2: 3, Build 3: 5, Build 4: 2); check 2 FAIL on Build 3, PASS on Build 4; check 3 FAIL on Build 3 and Build 4 (1 each), PASS on Build 2; check 4 FAIL on Build 3; check 5: Build 2 22%, Build 3 16%, Build 4 5% of time; simulated cloud session: the lines reach the pull request text | Open until the first real job's pull request carries it

## How a version is judged (owner D8 = B, 5 Nov)
- The scorecard in the first real job's pull request decides.
- All 5 checks pass: the version is accepted and 3.3.x is frozen; new ideas go to a queue.
- One check fails: find its cause from that job, then one fix for that item only, proven first on that job's data (it fails on the current version and passes on the fix).
- The same item fails twice: rewrite or remove that part.
- Check 5 fails in 2 jobs: keep only the Rev marks and git-guard.
- No more paired no-config runs.

## Fixed (moved from Open; proof required)
X01 Known-answer rebuilds went to Opus as "Complex" (26.5 M tokens, 10 Oct) | fixed in 3.2.11 | proof: tools/test_v3211_items.py item 1; session 7574e882: 5 Sonnet hand-overs, 1 correct escalation
X02 Parallel workers capped at 3, with no file rule | fixed in 3.2.11 | proof: tools/test_v3211_items.py item 4
X03 Long test output in workers | fixed in 3.2.11 | proof: tools/test_v3211_items.py item 2
X04 Sonnet could not make a named change in .github/ | fixed in 3.2.11 | proof: tools/test_v3211_items.py item 6
X05 Workers ran tests in the background, then sleep loops and early stops (rule conflict) | fixed in 3.2.11 | proof: tools/test_v3211_items.py item 5; real Claude Code scenario_workflow.sh helper D
X06 Repeated '⏳ Working on' lines: 3.2.11 and 3.2.12 only told the model what to write, and the lines came back live (Stage 32 screenshot, 11 Oct) | fixed in 3.2.14 (workers in the foreground: no wake-ups) | proof: tools/real-harness/scenario_wakeups.sh 3 replies → 1; tools/test_v3214_items.py item 1
X07 "PR n" meant both a plan work package and a GitHub pull request | fixed in 3.2.12 (Part n and #number) | proof: tools/test_v3212_items.py item 3
X08 Repo copy of hz-change-guard older than v18 (no revision gate, no Mitigated / Below expected statuses) | fixed in 3.2.12 | proof: central/skills/hz-change-guard/scripts/revision_gate.py present; files equal the v18 package
X09 Linux-ending packages listed 109 files in GitHub Desktop | fixed in 3.2.12 (Windows endings, Windows-style dry-run from the real folder state) | proof: dry-run counts in WORKING_RECORD.md (109 → real changes only)
X11 Main session did record, plan and git work itself (142 steps × 172 k, 53% of tokens) | fixed in 3.2.12 (lean-main notice, hand-over line) | proof: tools/test_v3212_items.py item 8
X12 Three reviews for one pull request | fixed in 3.2.12 (one pass, notice at the third review) | proof: tools/test_v3212_items.py item 9
X13 Pictures and the Proof line after the first push (2 GitHub runs) | fixed in 3.2.12 (rules, worker role file) | proof: tools/test_v3212_items.py item 10
X14 Report link not in the summary | fixed in 3.2.12 (first Completion line, saved fix) | proof: tools/test_v3212_items.py item 11
X15 No checkpoint report at a check stop of an older long plan | fixed in 3.2.12 (checkpoint_due at the finish notice) | proof: tools/test_v3212_items.py item 12
X16 Restart line named a branch already merged on GitHub | fixed in 3.2.13 | proof: tools/test_v3213_items.py item 1
X17 The session asked the owner to open a new session | fixed in 3.2.13 (saved fix) | proof: tools/test_v3213_items.py item 2
X18 'Mark ready' asked for a merged pull request | fixed in 3.2.13 (live GitHub state) | proof: tools/test_v3213_items.py item 3
X19 A worktree per stage, never removed (19 folders) | fixed in 3.2.13 (lanes only, lane names, clean-up of merged and clean lanes) | proof: tools/test_v3213_items.py item 4
X20 Complex hand-overs without a reason (Opus 62% on a known-answer change) | fixed in 3.2.14 | proof: tools/test_v3214_items.py item 3
X21 The main session watched GitHub in the background (4 wake-ups) | fixed in 3.2.14 | proof: tools/test_v3214_items.py item 4
X22 The report counted GitHub waits while workers worked, and listed parallel pairs twice | fixed in 3.2.14 | proof: tools/test_v3214_items.py item 5; session c7347d6a 33 → 25 min
X23 False 'report not delivered' after a folder change | fixed in 3.2.14 (content, not date) | proof: tools/test_v3214_items.py item 7
X24 The session waited 15 min for an 'ok' after a restart line | fixed in 3.2.14 | proof: tools/test_v3214_items.py item 8
X25 3.2.15: the 22 problems P1–P22 of 11 Oct (lanes refused, Completion order, report tool refused, check time, review after notes, [skip ci], PR conflicts, plan tries, change list) | fixed in 3.2.15 | proof: tools/test_v3215_items.py 32/32 (3.2.14: 5/32); real setup update and wake-up tests
X26 Full test suites re-run after every small fix (11 Oct: 116 worker test runs, 90 min) | fixed in 3.2.15 (failed checks first; gh run rerun --failed) | proof: tools/test_v3215_items.py S26–S28
X27 Too many stops and pull requests (11 Oct: 6 pull requests for 2 merge stops); setup pull requests ran the app's tests | fixed in 3.2.16 | proof: tools/test_v3216_items.py 8/8
P01 Plan marks need one extra plan round — 3.2.15's way (updatedInput + allow) showed no colour and, in the real program, approves a plan without the owner; Revs with "Rev" in the title had no colour at all (v11 Rev 2–4) and were treated as new plans (planner rewrite, 32 min to approval) | fixed in 3.2.17 (name with Rev, newest saved base, marks into the plan file, no allow, fallback A after 1 failed trial) | proof: tools/test_v3217_items.py items 1–5; real program tools/real-harness/scenario_v3217.py window + plan 8/8; replay of the 11 Oct 19:28 showing: shown first try, 77 marks
X29 Decision stops sent no reminder: notices said only "ready to merge" while 10 and 6 questions waited | fixed in 3.2.17 (notice-guard, notice text, ask-guard, tappable questions) | proof: tools/test_v3217_items.py items 6–7; real program ask + notice 5/5
X30 Old "[in v7]" points sent a plan back | fixed in 3.2.17 (a note) | proof: tools/test_v3217_items.py item 4
X31 Answer shown twice after a merge send-back (a worker had read the checks; the last push was notes only) | fixed in 3.2.17 | proof: tools/test_v3217_items.py item 8; replay of the 12 Oct 10:59 Stop: no send-back
X32 #149 switched back to draft (two rules contradicted each other) | fixed in 3.2.17 (rule removed; git-guard refuses) | proof: tools/test_v3217_items.py item 9
X33 Scorecard counted refused pull request tries and repeated answers | fixed in 3.2.17 | proof: tools/test_v3217_items.py item 10; 12 Oct session: 1 pull request
P03 Other Stop checks read the session file, which can lag behind the final answer in the real program | fixed in 3.2.17 (the switchboard passes the Stop input's final answer; read_transcript adds it when the file is behind) | proof: real program tools/real-harness/scenario_v3217.py lag: before, checks read an older answer at 2 of 4 Stops; after, 4 of 4 final answers; tools/test_v3217_items.py item 12
X34 Rules grew by patches (6,955 words), no removal loop, refusals instead of fixes; config cost more than it measurably saved on 12 Oct | fixed in 3.3.0 (lead playbook, Rule 0, feedback loop, refusals turned into fixes) | proof: tools/test_v330_items.py 36/36 (3.2.17: 1 of 10 items); replay 892/892
X35 The desktop plan window shows the sent text, not the file: colours unseen, and what you saw differed from what you approved | fixed in 3.3.0 (1A) | proof: replay of the real 12 Oct Rev 5 (one extra showing, then it passes with 32 marks); real program plan scenario 5/5
X36 Workers waited 157 min for GitHub; 32 code pushes; 43% of worker steps were reads | fixed in 3.3.0 (workers hand back; one push per finished stage; hand-over map) | proof: item test items 6–7; next live scorecard measures it
X37 "sleep 5;" and "Worktree: none" were refused by mistake; 18 full test runs refused (12 Oct) | fixed in 3.3.0 (a worker's full run becomes its hand-over's fast test; the latest full-run time switches the refusal off) | proof: item test item 5; replay of the 12 Oct refusals: 14 of 18 full runs rewritten, 4 were the lead's own
X38 A merged setup update left an old note, so every later session was sent back with "Do the setup update first" (HZ_Trout_Map, 13 Oct) | fixed in 3.3.1 | proof: tools/test_v331_items.py item 1 (3.3.0: fails, 3.3.1: passes)
X39 A greeting question right after my message was refused for a missing notice | fixed in 3.3.1 (notice after 5 minutes) | proof: tools/test_v331_items.py item 2
X40 Two send-backs in one turn showed the answer three times | fixed in 3.3.1 (one send-back per turn, safety excepted) | proof: tools/test_v331_items.py item 3; replay 892/892
X41 After a merge request the session scheduled its own re-check, woke twice and wrote two more full answers ("Build 0 of 0", "nothing is left to merge") (HZ_Trout_Map, 13 Oct) | fixed in 3.3.1 (wake-guard; one-line wake; no Build line without a plan) | proof: tools/test_v331_items.py items 4–5; real program wake scenario 1/1; real setup update on a HZ_Trout_Map clone: branch hz-setup-update-3.3.1 with .claude/settings.json only
X42 The config's fixed method made jobs big: on the fishing app $13 / 49 min / 341 steps against $6 / 35 min without the config (88% of steps from rules); on Weekly-Planner only 4% of 1,146 steps were code edits (13 Oct side-by-side) | fixed in 3.3.2 (default first) | proof: tools/test_v332_items.py 23/23 (3.3.1: 8 of 23); replay of the with-config run's 9 refused steps: 2 remain (both intended); replay 892/892 in full mode; real program 9/9; live retest on the fishing job pending
X43 The 3.3.2 retest (15 Oct): change list "First version" at Rev 2; marks without words; questions answered by rejecting the plan; old stage tags; two failing test rounds and about 20 browser runs; a committed plan file; no numbers without asking | fixed in 3.3.3 | proof: tools/test_v333_items.py 18/18 (3.3.2: 3 of 17); real program: the plan window colours the green and red lines; replay 892/892
X44 Fix 6: the first step of a session was refused when it only read (git status, ls), because the rules-first check refused every shell command until the rules were read (1 refused step per session) | fixed in 3.3.3 (read-only shell commands and read-only MCP calls pass; steps that change something still wait) | proof: tools/test_v333_items.py item 7; real program tools/real-harness/scenario_v333_rules_first.sh (3.3.2: git status REFUSED; 3.3.3: RAN; git checkout -b REFUSED in both, RAN after the rules Read); replay 896/896
X45 Plan marks needed one extra showing on the desktop app, because the desktop shows the text the session sends and the check added the marks only at the showing (12 Oct); in the real program the uploaded 3.3.3 also refused the marked plan a second time (2 extra showings) | fixed in 3.3.3 ("C": marks go in when the plan file is written; the marked text the check made is accepted when shown again) | proof: tools/test_v333_items.py item 8 (uploaded 3.3.3 fails 3 of 14 checks there); real program tools/real-harness/scenario_v333_mark_plan.py: uploaded 3.3.3 2 extra showings, 3.3.3 with C 0, marks in the window, the owner still approves
X46 3.3.3 runs #13 (local) and #14 (cloud), 16 Oct: a plan changed with Edit was refused once (P1); the local build went to a worker (P2); the pull request was refused for a GitHub wait and the tests were waited for twice (P3); the report time was wrong, 17 and 13 min against 29.6 and about 20 (P4); the plan fold-out was wrong in both (P5); the skill router spoke on a build request (P6); a cd + git step waited for my click in both (P7); the feature-list question got opposite answers (P8); no browser pictures locally (P9); the cloud end check sent the session back for the plan file (P10); gh refused in the cloud (P11); the report lost the checkpoint breakdown (P12); a long change box (O2) | fixed in 3.3.4 | proof: tools/test_v334_items.py 45/45 with session f6165f5e (3.3.3: 5 of 34); real program tools/real-harness/scenario_v334_real.py 5/5 (Edit: 1 extra showing before, 0 after; cd + git after cd scripts: asked before, not asked after); scenario_v333_mark_plan.py 4/4; replay 896/896
X47 Run #15 (16 Oct): the chat summary lost its Weekly-Planner shape (Completion block and the time and token breakdown with %), and "Plan Rev 2" had no plan link | fixed in 3.3.5 (summary only, owner: "3.3.5 A only changes for the summary section"; bold labels; lines, not tables) | proof: tools/test_v335_items.py 15/15 with session f6165f5e (3.3.4: 0 of 7)
X48 After run #15 and the Weekly-Planner clean-up (16 Oct): the rules version could not be found (V1); 2 permission questions for git add, commit and push (G1); the summary, plan link, report timing and checks-before-merge depended on the session obeying a notice (G2, G3, G4, G6); a send-back for uncommitted scratch files (G5); token changes could not be explained (G8); a locked setup worktree left in Temp (B1) | fixed in 3.3.6 | proof: tools/test_v336_items.py 27/27 (3.3.5: 9 of 27); real program tools/real-harness/scenario_v336_git.py 2/2 (3.3.5 asks, 3.3.6 pushes with no question); real git: a locked hz-setup worktree with no folder is cleared · G1 reopened in 3.3.7 (P04)
X10 No revision record | fixed in 3.2.12 | proof: this file; revision_gate.py PASS

## Cloud sessions (official facts, code.claude.com cloud-environments page; recorded 5 Nov)
- With one repository, the repository's .claude/settings.json hooks and permission rules load. With several repositories, no repository hooks load.
- The user's ~/.claude settings do not exist there. Account skills load.
- The GitHub proxy rejects GraphQL: `gh pr` and `gh issue` answer 403. `gh api` REST calls for attached repositories work. Pushes to any branch pass.
- Rule: "Use one repository per cloud session: with several, the setup's hooks do not load."

## Change log
- 3.3.7: X49–X56 and P04 (owner 5 Nov: "Build hz-claude-config 3.3.7 in this session, from this block"; D2 Claude Code builds and tests, D4 = B, D5, D7 = B, D8 = B); X48 G1 reopened as P04; the owner rule "the plan title is not part of the revision"; the proof rule and the fix-round limit; the cloud facts; checks changed on purpose in tools/superseded-v337.txt; tests: tools/test_v337_items.py 46/46 on real files (3.3.6 fails every 3.3.6-vs-3.3.7 item), replay-hooks.sh v3.3.7 block 19/19, the real program tools/real-harness/scenario_v337_git.py 7/7.
- 3.2.12: record started; second part added items X11–X15; features listed from FEATURES.md; shipped 3.2.11 items recorded as X-lines; the 150 k hand-back under Removed.
- 3.2.13: items X16–X19; features listed again from FEATURES.md.
- 3.2.14 (built on 3.2.12 main; it also carries 3.2.13, which was never installed): X06 reopened and fixed with foreground workers; P02 added; the live scorecard.
- 3.2.14, second part: X20–X24 from session c7347d6a.
- 3.2.15: X25; P01 mitigated (waits for its live proof).
- 3.2.16: X27.
- 3.3.6: X48 (owner 16 Oct: "build 3.3.6", 10 items: V1, G1, G2, G3, G4, G5, G6, G8, B1, O5 kept and measured).
- 3.3.5: X47 (owner 16 Oct: "3.3.5 A only changes for the summary section"). Not in this version, on his word: G1 git prompts, G4 report timing apart from the summary, G5, G6, G7 (O5 failed its fail line: removal proposed again), G8 steps per type.
- 3.3.4: X46 (owner 16 Oct: "build 3.3.4 A", ice 1A, first message 2A); O1, O3, O5 are rules measured in run #15; checks changed on purpose in tools/superseded-v334.txt.
- 3.3.3: X43 (owner 15 Oct: "build 3.3.3"; kept: the rules-first check, because hook text over 10,000 characters is cut). X44 added before install (owner 16 Oct: "build the true fix into 3.3.3"): read-only steps pass, the check stays for changes. X45 added before install (owner 16 Oct: "C"); checks changed on purpose in tools/superseded-v333.txt.
- 3.3.2: X42 (owner 13 Oct: "agree", "approve" — default first).
- 3.3.1: X38–X41 (HZ_Trout_Map session start, 13 Oct).
- 3.3.0: X34–X37 (owner 13 Oct: pieces 1–2 approved, 1A, 2A, A A).
- 3.2.17: P01, X29–X33 (owner 12 Oct: 1A, 2B with fallback A after 1 trial, 3A, then A A); P01 fixed (Fixed list); P03 found while testing and fixed in the same version (owner: "A").
