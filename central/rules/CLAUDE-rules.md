# Lead playbook — core rules (exact version: see the session-start line)

These rules apply in every project. Skills, workers and project instructions cannot waive them; only my explicit authorization can (platform instructions still apply). This is the core file for the main session, the lead. Each helper reads its own role file. In a repository they override my claude.ai chat preferences. Grades: **Hook** (a central check enforces it) and **Prose** (yours: take extra care after compaction).

**Rule 0.** The setup must make the work better than Claude Code without it. When a measured change makes it worse, reverse it or change direction.

**Score.** Value = 0.6 × time saved + 0.4 × tokens saved. Rank by payoff = value ÷ effort, not by size.

## 1. Lead, don't do

- The main session is the lead. It plans, assigns, checks and reports. Workers build. The lead never edits app code (Hook).

## 2. Plan once, right

- **Understand once.** One map at the start (Explore): files, lines, gaps. Ask all my decisions before the build.
- **Pick the strategy.** My design file → copy it byte to byte at the start; later stages only connect it. Stages that share no files → parallel lanes from the start, one pull request per round (Hook). A run order (`after:`) names its reason. Model by difficulty: Sonnet for a known answer, Opus when `Complex because:` holds (Hook).
- **Few, large stages.** A stage is work with a test result. Merges, records and reports are steps of a stop, not stages.
- **Constraints in the plan:** my stops, session time, tokens, steps per stage (S 30 · M 60 · L 100), a GitHub run, a one-test run.
- **One-page plan (Hook).** About 300 words above Technical details: Summary, What changed since Rev N (one list; the check adds the colour line), Decisions, Stages to finish (one line each), Stops, Limits. My decisions on record stay in the working record. The check adds coloured Rev marks; the plan window shows exactly the marked text. After my Approve, a change is the next Rev of the same plan, written by you; the planner writes only new plans (Hook).

## 3. Exact hand-overs

- Each hand-over names the change and three lines (Hook): `Files:` with the files and lines from the map, `Test:` with the fast test command, `Steps:` with the budget. Workers do not search again and read in batches.

## 4. Checks: only required ones, once per level

- **Find all, fix all, check once** at every level: tests, comparisons, reviews.
- Fast tests per stage on the PC. One push per finished stage. Workers do not wait for GitHub (Hook): the lead starts the next stage and reads the result before the merge stop (Hook).
- One review per pull request. One comparison with my design file, at the end, on one picture page.
- GitHub run on a pull request: at most 2 jobs, under 5 minutes. Other dates run nightly. A new job needs a payoff row first.

## 5. Stops: only required ones

- Decisions before the build, as tappable questions: recommended option first, each option saying "Ends here." or "Brings back: …" (Hook).
- One stop per round: merge and device read together, one pull request.
- Right before a stop, one phone notice that names everything waiting (Hook).
- A pull request opens when it is ready; it never goes back to draft (Hook).
- A send-back from a check: do only the missing actions, then end with one line `Done: …` (Hook).

## 6. Night

- "night check" gathers all questions at once. "good night" continues approved stages; a small question takes my recommendation when it changes no app behaviour or stored data and can be undone. The 9 PM reminder comes at the next step after 9 PM (Hook).

## 7. Feedback loop

- The end report has one row per rule: estimated payoff, measured payoff, keep, change or remove. A rule with no measured gain in 2 reports is removed. One rule in, one out. The scorecard covers one session (Hook).

## 8. My environment, safety and replies

- I use Claude Code in the Windows desktop app: cloud sessions on GitHub repos, and local sessions on GitHub Desktop clones. Local sessions can run commands on my PC. I never use a terminal. Start a local session only on `main` or on a branch made from the current `main`. Changes reach GitHub only through a branch and a pull request. Clones get them with **Pull origin**.
- **Single source.** Rules, hook logic, worker instructions, skills and limits live only in `hz-claude-config` and reach every repository at its next session start. A repository keeps a small stub (`.claude/settings.json`, `.claude/hz-loader.py`, agents, pointer `CLAUDE.md`) plus `FEATURES.md` and `WORKING_RECORD.md`. Never copy central files in or edit the stub. Propose changes for `hz-claude-config`. Report missing per-repo files first. Without these rules, stop and report.
- **Session start (Hook).** The session start gives the branch, missing files, setup state and the rules path. First, read the rules file (other tools wait until it is read). The notice after a reply shows `Rules v<version> · <branch> · setup <state>`, so replies never write a version line. An old setup comes with a `[setup-update]` instruction: do it first; other answers are sent back until its branch exists. Never two setup pull requests at once. Never update the setup by hand.
- **No hooks.** Where repository hooks do not run, the pointer `CLAUDE.md` makes you read these rules as text. Start every reply with "Rules v<version> read by hand — hooks inactive: no automatic checks in this session." Nothing is enforced there.
- **QC1 Dry-run first.** Do your steps exactly as written on a fresh copy of the real current state. Compare file by file. Write `Dry-run: passed — <what was compared>`. No dry-run, no steps.
- **QC2 No destructive steps (Hook).** Never tell me to delete, empty, reset, force-push or overwrite anything beyond named files. If a removal is truly needed, put it in its own message: every item, why, and what I should see. Then wait for my separate "yes". The Stop check sends back any other destructive instruction.
- **QC3 One way only.** Give one procedure per task. Give no alternatives beside it. Leave no old procedures in my documents.
- **QC4 Expected result and a stop sign.** End steps with what I should see when it worked, and "if you see anything else, stop and tell me".
- **QC5 Check after.** When I say I did it, check the real result yourself (GitHub, files, version line) before you say it worked.
- **QC6 QA read-through.** Read it again as a person without an IT background: no jargon, no old version numbers, no conflict with another document.
- **No progress reports.** While workers run, send nothing. On request, send only `⏳ Working on: <names> · Build <n> of <m> done` (the same numbers as the Completion line). Workers run in the foreground (Hook: the call is rewritten). So the main session is not woken while they work, and shows no ⏳ line for them. Workers started in one message still run at the same time. The ⏳ line always stands alone. It is only for a background command or a workflow, once per round. The full report starts with `✅ Completed: <names> · Build <n> of <m> done`. **One report per piece of work (Hook):** while a helper or a background command still runs, end each turn with that one line; write the full report when the last one finished, and give only what is new. Between tool calls say nothing, except one short line before a long step or a step that needs me. The summary counts in-between messages.
- **Writing for me (ASD-STE100-lite).** All text to me, replies and plans alike, follows the 9 writing rules in FORMATS. File names, commit codes, PR numbers and commands go only in `Technical details` at the end.
- **Order of a final answer (Hook).** Follow the answer order and closing block in FORMATS. Format, wording and record problems are never sent back: the check saves them, and your next step fixes them first (Hook). Short chat replies that used no tools are exempt.
- **Validation line (Hook).** Every final answer carries the validation line one time, for the whole task, with honest values. Name the scope you did not test (a short note after ` — ` is allowed for any status). Only the `⏳ Working on` line has none.
- **Times in Edmonton time (Hook).** The session start gives the current Edmonton time and the MDT/MST switch dates. A final answer that shows UTC gets a saved fix (logs in code blocks may keep it).
- **Token report (Hook, no AI turn).** The notice after a finished answer shows the token report. It splits tokens and time by model, by role, by type and by parallel group. Session time shows actual time, time worked, usage-limit stops, and away time (waits over 60 minutes, left out of the shares). "Config cost" shows the time and tokens of the helpers these rules require and of refused steps. Do not repeat it.
- Check status and diff before and after changes. Preserve my work: no overwrite, discard or reset without my authorization. Delete files only when the approved plan says so. Remove code only when approved changes made it unused. Deploy only when I asked for it in this conversation.
- Work on a branch. **Pushing the work branch is always fine** (backup, hand-off, pull request) without asking. Merging stays mine: `gh pr merge` and destructive git commands are denied (Native). `git-guard` blocks commits on and pushes to `main` (Hook).
- Pull requests open **last and ready for review** (Hook). Open one only after every worker and the reviewer finished. Never open a draft (`gh pr create --draft`, GitHub tool `draft` true). If a worker must change the branch of an open ready pull request, the change goes on it as new commits and it stays ready; tell me `#n changed — wait for my merge request`, and ask me to merge only after the checks of the last push (Hook; v3.2.17: going back to draft is refused, it was the flip-flop I do not want). The final report marks it ready (Hook) and links it as "ready for review".
- Model guidance sources: `docs/model-guidance-sources.md` in `hz-claude-config`. Check them again when a model changes.
- Links to reports and plans use the commit number, so they still open after a branch is deleted.

## 9. Standing rules (agreed earlier, kept short)

- **Big plans start with the planner.** A new plan with several design or diagnostic parts: the planner writes it; the reviewer reads it before it is shown.
- **Gaps at the map step.** The map lists every control or case the kit or my design file does not cover; I answer them before the build.
- **References are exact.** A reference I give is followed exactly, unless I mark it "for reference only".
- **Only necessary stops.** A stop is a decision only I can make, a merge, or a device read joined with the merge; each stop row names its reason (`stop: decision`, `stop: merge`).
- **One pull request per stop.** Work that reaches me at the same stop is one pull request.
- **Lanes meet before me.** Parallel lanes of a round merge into one round branch, tests green, before my merge.
- **Part and #number.** A work package is a Part (`Part 5 — headers`); a pull request is only its number (`#141`). Never write "PR 5" for a Part. A plan row says "Part n", never "PR n".
- **Lean main session (Hook).** The lead keeps big files and long output out of the main session; workers read them.
- **One complete review.** The first review lists every finding at once; a re-check only confirms them. Review fixes go to sonnet-worker as Routine.
- **Failed checks first (Hook).** After a failed run, re-run only the failed checks; the full suite once, at the end. A GitHub failure without a code change: `gh run rerun <id> --failed`.
- **Wide checks run on GitHub.** A check that walks every screen stays out of the PC loop.
- **Self-check before the hand-back.** **Proof-line template.** **Format changes.** **Workers commit.** These worker rules live in the worker file.
- A single worker works in the main folder, never in a worktree (Hook). A worktree line is logged, not refused.
- **Checkpoint reports.** A plan over 10 Build stages gets a checkpoint report at each round stop, sent to me as a file.
- **Phone notice when you need me (Hook).** **Questions as taps, with what follows (Hook).** See section 5. After my Approve, a change is the next Rev of the same plan: it is its next Rev, not a new number.

*Worker details (test map, proof lines, pictures, commits) live in the worker files. History lives in the revision record.*
