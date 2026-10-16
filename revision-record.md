# Revision record — hz-claude-config

Version: 3.3.2
Built on: 3.3.1
Owner: the newest "Claude Code Plan Work Strategy" chat (only the owner builds the next package; other chats send P-lines here)

Run before every package: `python3 /mnt/skills/plugins/hz-change-guard/scripts/revision_gate.py <new-folder> <fresh clone of GitHub main>`. Any FAIL stops the zip.
Every package: Windows line endings (CRLF); the dry-run starts from a Windows-style copy of the owner's real folder state, and its count must match GitHub Desktop.

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
F15 Skill copy (central) hz-change-guard (renamed in v3.2.3; was hz-plan-r | hz-change-guard
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

## Removed (approved, with reason)
- Soft hand-back notice for a worker at 150 k tokens (3.2.11 list item 3) | reason: 3.2.9 switched the memory limit off because restarts re-read the same files and cost more; on 10 Oct only 1 of 5 workers passed 150 k | approved: owner, 10 Oct ("yes, drop item 3")

## Open problems (stay until fixed with proof or he drops them)
P02 Model-dependent solutions (one review per pull request, lean main session, Part names, report link copied, short test output) are proven only by a live session | found: 2026-10-11 campaign | next: the live scorecard in each end report shows works / does not work

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
X10 No revision record | fixed in 3.2.12 | proof: this file; revision_gate.py PASS

## Change log
- 3.2.12: record started; second part added items X11–X15; features listed from FEATURES.md; shipped 3.2.11 items recorded as X-lines; the 150 k hand-back under Removed.
- 3.2.13: items X16–X19; features listed again from FEATURES.md.
- 3.2.14 (built on 3.2.12 main; it also carries 3.2.13, which was never installed): X06 reopened and fixed with foreground workers; P02 added; the live scorecard.
- 3.2.14, second part: X20–X24 from session c7347d6a.
- 3.2.15: X25; P01 mitigated (waits for its live proof).
- 3.2.16: X27.
- 3.3.2: X42 (owner 13 Oct: "agree", "approve" — default first).
- 3.3.1: X38–X41 (HZ_Trout_Map session start, 13 Oct).
- 3.3.0: X34–X37 (owner 13 Oct: pieces 1–2 approved, 1A, 2A, A A).
- 3.2.17: P01, X29–X33 (owner 12 Oct: 1A, 2B with fallback A after 1 trial, 3A, then A A); P01 fixed (Fixed list); P03 found while testing and fixed in the same version (owner: "A").
