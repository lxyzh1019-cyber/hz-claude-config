# hz-claude-config — central working rules

The current version is line 1 of `central/MANIFEST.txt`. This README carries no version number, so it does not go out of date.

Everything central lives here: the rules, the hook logic, the executors' shared instructions and the audit skills (`central/`). Each app repository keeps only a small **stable stub**: `.claude/settings.json`, `.claude/hz-loader.py`, six helper files in `.claude/agents/` and a pointer `CLAUDE.md`. It also keeps its own `FEATURES.md` and `WORKING_RECORD.md`. The six helpers are opus-worker, sonnet-worker, planner, planner-opus, reviewer and explore.

At every session start, cloud or local, the stub's loader fetches the current `central/` from this repository (public raw files) and the session-start hook injects the rules. **Updating = change `central/` here and merge. No app-repo changes.**

Verified by the cloud probe on 2026-09-25: repository hooks run in cloud sessions, a hook can fetch from this repository, and a Stop hook can force a correction.

These instructions live only here; chat replies point here. This repository must stay **public**.

## Layout
| Path | What it is |
|---|---|
| `central/` | what the loader fetches; `central/MANIFEST.txt` line 1 is the **only** place the version lives |
| `stub/` | the stable per-repo files (settings, loader, the six helpers: opus-worker, sonnet-worker, planner, planner-opus, reviewer, Explore) and `install-stub.sh` (one-time install per repo) |
| `central/stub-files/` | a copy of the `stub/` files that the loader fetches; the app sessions update their setup from it (Step B) |
| `tools/build_manifest.py` | rebuilds `central/MANIFEST.txt` after any change under `central/` |
| `tools/replay_sessions.py` | replays real session files through the checks |
| `tools/real-harness/` | runs the real Claude Code with a stand-in model, to test the checks live |
| `tools/ste_check.py` | checks text against the ASD-STE100-lite writing rules |
| `tools/rules-coverage.txt` | every rule with the phrase that proves it is still in the rules text |
| `.claude/`, `CLAUDE.md` | this repository's own stub, so the rules apply when editing it too |
| `docs/` | your claude.ai preferences (`claude-ai-preferences.txt`: paste into claude.ai Settings > Profile when an update says so) and the model guidance sources (`model-guidance-sources.md`) |
| `central/hooks/replay-hooks.sh` | the replay test of every check (run before each package) |

## B. App repositories update their own setup files (automatic)
A few setup files live inside each app repository (which helper runs on which model, which checks switch on). They cannot be downloaded at session start like the rules. So the session start **updates them itself**. The first session after a change commits them on a branch named `hz-setup-update-<version>`, in a temporary folder. It pushes that branch, opens a pull request, and asks you to merge it. Your own folder is not touched. If the push fails, the session does the commit itself. Auto mode can refuse that and ask for your "yes". Merge it; the next session there shows `[stub] current`. While that pull request waits, later sessions only remind you — they never open a second one.

Fallback, only if a session reports that it could not update automatically (for example a helper file someone edited by hand): ask the chat for a package for that repository and add it with GitHub Desktop as in Step E.

## C. New app repositories
A repository without the setup yet needs the installer once: ask the chat for a package for it (give its name) and add it with GitHub Desktop as in Step E.

## D. GitHub Desktop clones
For each cloned repository: set **Current Branch** to `main`, then **Fetch origin** → **Pull origin**. Start local sessions only on `main` or a branch made from the current `main`. Optional local check: open a local session in the desktop app on that folder and type `hi` — the same pass criteria prove Python and bash work on your PC. An error mentioning bash or python means one is missing (install Python from python.org).

## E. Every update of this repository (no Claude session, no credits)
The claude.ai chat builds and tests every update and gives you one **full** package (every file of the new version). Before handing it over, it follows these same steps itself on a copy of what is on GitHub now (QA/QC rules). With GitHub Desktop:
1. Open **hz-claude-config**, stay on **main**, press **Pull origin**.
2. **Branch → New branch** (any name).
3. Right-click the zip → **Extract All** → set the destination to the repository folder itself → **Replace** when asked.
4. Commit, **Publish branch**, **Create Pull Request**, merge on github.com.

What you should see: in step 4, GitHub Desktop lists the number of added / changed files the chat told you, and **0 deleted**. When the chat names files to remove, the deleted number equals the named files. After the merge, `central/MANIFEST.txt` on github.com shows the new version. If you see anything else, stop and tell the chat.

Never use github.com's **Upload files** for these packages (it flattens folders and skips `.claude`).

**Rollback.** If a new version causes trouble in the apps:
1. On github.com, open the merged pull request of that version in **hz-claude-config**.
2. Click **Revert** (unverified button name on your screen), then create and merge the pull request it makes.
3. Every app loads the previous version at its next session; nothing changes in the app repositories.

What you should see: `central/MANIFEST.txt` on github.com shows the previous version. If you see anything else, stop and tell the chat.

## F. Health check (after Step B, once per repository)
Start a **new** session on the repository (cloud or local; auto mode is fine) on your **account default model**, not the Sonnet session you used for Step B, and paste:

> Health check. Skip the plan for the check itself (only test 5d uses plan mode), commit nothing, and leave the repository as you found it. Report every test by its number — 1, 2, 3, 4, 5, 5b, 5c, 5d, 5e, 6 — as passed, failed or not applicable, one plain sentence each. You cannot see the notices Claude Code shows me, so for 1 and 5e write "for you to check".
> 1. Stub: quote the `[stub]` line from session start. I also check that the notice after your first reply starts `Rules v… · <branch> · setup current`.
> 2. Workers: hand `sonnet-worker` the task "Task: Health check / Level: Routine — reply with only the model ID you run on", then `opus-worker` the same with "Level: Complex". Pass = a Sonnet 5.5 ID, then an Opus 5.5 ID (even if this session plans on Fable). Also try handing `opus-worker` a "Level: Routine" task: Pass = refused. Then hand `Explore` and `reviewer` (Moment: Before done) the task "reply with only the model ID you run on": Pass = a Sonnet 5.5 ID, then an Opus 5.5 ID. Also hand `opus-worker` a "Level: Complex" task without a `Map:` line: Pass = refused.
> 3. No advisor: check that `.claude/settings.json` has no `advisorModel`. Pass = none (sessions never consult Fable on their own).
> 4. Completion check: on a new branch add rows HEALTH-A and HEALTH-B (NOT STARTED) to the deliverable ledger in `WORKING_RECORD.md` (rows added on the branch are the ones counted), write `scratch/health.txt`, set HEALTH-A to COMPLETE with evidence "scratch file written", then write a final report that claims the work is done and has the line "Confidence: High · Status: Checked" (the check only reacts to a report marked Checked or Validated). In that report, include a regression table and every other line the checks ask for, so only the completion check can send you back. Pass = the completion hook sends you back to HEALTH-B, and the count covers only the two HEALTH rows. Then set HEALTH-B to BLOCKED — health check.
> 5. Draft pull request block: run `gh pr create --draft --title health --body health`, then try the same through the GitHub tool that creates pull requests, with its draft field set to true. Pass = both denied by git-guard; any other outcome is a fail (close any pull request it opened). If this session has no GitHub tool for creating pull requests (local sessions usually don't), that half is "not applicable", not a fail.
> 5b. Model: quote the `model` line from `.claude/settings.json`. Pass = there is none.
> 5c. Hand-over: without a worker, add the comment line `<!-- health -->` to the top of the app's main HTML file yourself. Pass = refused by the routing guard; then hand it to `sonnet-worker` ("Task: Health check / Level: Routine"), which passes; then remove it.
> 5d. Plan check: present, in plan mode, a two-line test plan with no Summary and a `<span>` in it. Pass = sent back before the Approve button, naming both. Then stop: do not fix or redraft the plan, leave plan mode, and delete its file from `plans/`.
> 5e. Summary at the end: after your final report (marked Checked), a notice "Session summary" (first line `Rules v…`, then tokens with the re-read part, time by model, hand-overs, send-backs) appears below the reply without the session writing it. Pass = it appears; its percentages add up to about 100.
> 6. CLAUDE.md: compare `CLAUDE.md` with its version before the last stub install (`git log`) and name any section that disappeared. Pass = none.
> Finally remove the two HEALTH rows, `scratch/` and any test plan file in `plans/`, switch back to `main`, and confirm `git status` is clean. Your last report has no Completion line: no ledger rows are left.

Pass = every test passed or not applicable. The three closing lines at the end of each reply are part of the test too. Bring any fail back to a chat about `hz-claude-config`.

**Short re-test** (when the chat names only some tests): put one line above the prompt — "Run only tests <numbers>; skip the others." It costs far fewer tokens than the full run.

## Troubleshooting
| You see | Cause | Fix |
|---|---|---|
| `Central rules NOT loaded … nothing is cached` | fetch failed and no earlier copy | check this repo is public and `central/MANIFEST.txt` exists on `main` |
| No notice starting `Rules v… · setup …` after the first reply | the checks did not run in this session | tell the chat |
| The notice says `vX is on GitHub: start a new session to load it` | the session started before the newer rules were merged. A session keeps its rules; reopening it does not load new ones | start a new session (the "+" next to the repository). Continue from the restart line in the record |
| `setup waiting for your merge`, but no open pull request on GitHub | before v3.2.4, an empty setup branch counted as waiting. A helper file in an older published version was skipped. | update to v3.2.4. The next session opens a real setup pull request; merge it |
| The session says the safety check refused the setup commit | the push from the session start failed, so the session had to commit | answer "yes, commit and push the setup update" in that session. Tell the chat if it refuses again |
| The notice says this PC's main is behind | GitHub Desktop has not pulled the merged setup. | click **Pull origin**, then start a new session |
| `offline: using cached vX` | GitHub could not be reached, earlier copy used | usually temporary; start a new session later |
| `hz-claude-config is incomplete on GitHub … using cached vX` | files are missing in this repository on GitHub | tell the chat; it sends a full package (Step E) |
| Old version still loaded after an update | raw-file cache | wait a few minutes; start a new session |
| `[stub] OUTDATED — … missing: …` | the app's setup files are older | the session updates them itself and asks you to merge (Step B) |
| Reply opens with "hooks inactive" | cloud session with several repositories: no repository hooks run | expected; for work that needs the checks, open a session on one repository |
| `INSTALL FAILED — do not merge` | smoke test could not load the rules | tell the chat |
| `NOT INSTALLED` after "LOCAL CHANGES FOUND" | the repo improved its v2 rules files locally | tell the chat |
| Hook errors in a local session | Python or bash missing on the PC | install Python from python.org |
| Hooks fire twice | rules v2 copies still in a repo or clone | Pull origin in its clone; if it persists, tell the chat |
| A local session loads old rules (v2.x) or no loader | the clone is on an old branch made before the install | in GitHub Desktop set **Current Branch** to `main` (or a branch made from today's `main`), **Fetch origin**, **Pull origin**, then start a new session |
