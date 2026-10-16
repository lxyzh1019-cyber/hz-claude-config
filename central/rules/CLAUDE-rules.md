# Lead playbook — core rules (exact version: see the session-start line)

These rules apply in every project. Skills, workers and project instructions cannot waive them; only my explicit authorization can (platform instructions still apply). This is the core file for the main session, the lead. Each helper reads its own role file. In a repository they override my claude.ai chat preferences. Grades: **Hook** (a central check enforces it) and **Prose** (yours: take extra care after compaction).

**Rule 0.** The setup must make the work better than Claude Code without it. When a measured change makes it worse, reverse it or change direction. A rule with no measured gain in 2 reports is removed.

**Score.** Value = 0.6 × time saved + 0.4 × tokens saved. Rank by payoff = value ÷ effort, not by size.

## 1. Default first

- Work as Claude Code does without this setup: one session reads the code once and builds. Helpers, maps, planners, lanes, stages, record files and picture tests are not required. Use one only when it clearly pays for this job, and say why in one line.
- An artefact (record file, report, picture, test tool) is made only when a later reader exists: a session that continues the work, or my request.
- Ask only when a wrong guess costs real rework (a data model, payments, anything hard to undo). Otherwise build with your recommendation and list each choice so I can change it.
- **Find all, fix all, check once**: list every failing test, review finding or difference, fix them together, then check once.

## 2. Small job (one pull request)

- Read the code once. Show a short plan in chat (what changes, where, any guess). After my approval, build.
- **My design file first.** A design, picture, prototype or document I give is copied exactly at the start; later work only connects it. Compare with it once, at the end. A reference is exact unless I mark it "for reference only".
- Tests: the existing ones plus new ones for the change. One full run at the end (on GitHub when the local full run is slow).
- **One review pass before my merge:** one reviewer reads the change once and lists everything; fix it all; a second pass only if a blocking fix changed code.
- One pull request, opened when it is ready, never back to draft (Hook). One stop: merge and device check. The record is the pull request text: what changed, which choices used your recommendation, test results.
- Screenshots for me go in the chat, not into the repo. Picture tests only when I give a reference picture.

## 3. Bigger job (a new app, many sessions)

- Decisions first, in claude.ai: modules, the spec or prototype, the data model. Start the repo from my prototype exactly.
- Each module is done as small jobs (section 2). Parallel work only as separate sessions on separate branches, for big parts that share no files.
- One short record file that later sessions read: what exists, decisions, what is next; updated once per pull request.
- One comparison with the spec at the end of each module. Measure time and cost per pull request (Rule 0).

## 4. Plans, stops and notices

- A plan for me is short: Summary, What changed since Rev N, Decisions, Stops. The check adds coloured Rev marks and one colour line; the plan window shows exactly the marked text. After my Approve, a change is the next Rev of the same plan (Hook). Do not write marks or change blocks yourself.
- Only necessary stops: a decision only I can make, or a merge with its device check. One pull request per stop.
- Right before a stop, one phone notice that names everything waiting, when I may be away (Hook). Decisions as tappable questions: recommended option first, each option saying "Ends here." or "Brings back: …" (Hook).
- A stop ends the turn: no self wake-ups or re-checks (Hook). A send-back from a check: do only the missing actions, then end with one line `Done: …` (Hook). The closing block only after real work; small operations end in one line.
- "night check" gathers all open questions at once. "good night": keep working on approved work that needs no answer; a small choice takes your recommendation when it can be undone.
- GitHub run on a pull request: at most 2 jobs, under 5 minutes; other dates run nightly.

## 5. My environment, safety and replies

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
