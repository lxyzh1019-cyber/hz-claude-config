# hz-claude-config — central working rules (v3.1.22)

Everything central lives here: the rules, the hook logic, the executors' shared instructions and the audit skills (`central/`). Each app repository keeps only a small **stable stub** — `.claude/settings.json`, `.claude/hz-loader.py`, `.claude/agents/opus-worker.md`, `.claude/agents/sonnet-worker.md`, a pointer `CLAUDE.md` — plus its own `FEATURES.md` and `WORKING_RECORD.md`.

At every session start, cloud or local, the stub's loader fetches the current `central/` from this repository (public raw files) and the session-start hook injects the rules. **Updating = change `central/` here and merge. No app-repo changes.**

Verified by the cloud probe on 2026-09-25: repository hooks run in cloud sessions, a hook can fetch from this repository, and a Stop hook can force a correction.

These instructions live only here; chat replies point here. This repository must stay **public**.

## Layout
| Path | What it is |
|---|---|
| `central/` | what the loader fetches; `central/MANIFEST.txt` line 1 is the **only** place the version lives |
| `stub/` | the stable per-repo files and `install-stub.sh` (one-time install per repo) |
| `tools/build_manifest.py` | rebuilds `central/MANIFEST.txt` after any change under `central/` |
| `.claude/`, `CLAUDE.md` | this repository's own stub, so the rules apply when editing it too |
| `docs/` | rules review copy (revision markers), skill-trigger tuning procedure, your claude.ai preferences (`claude-ai-preferences.txt`: paste into claude.ai Settings > Profile when an update says so) |

## B. App repositories update their own setup files (automatic)
A few setup files live inside each app repository (which helper runs on which model, which checks switch on). They cannot be downloaded at session start like the rules, so the session start **updates them itself**: the first session after a change rewrites them, puts them on a branch named `hz-setup-update-<version>`, opens a pull request, and asks you to merge it. Merge it; the next session there shows `[stub] current`. While that pull request waits, later sessions only remind you — they never open a second one.

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

What you should see: in step 4, GitHub Desktop lists the number of added / changed files the chat told you, and **0 deleted**. After the merge, `central/MANIFEST.txt` on github.com shows the new version. If you see anything else, stop and tell the chat.

Never use github.com's **Upload files** for these packages (it flattens folders and skips `.claude`).

## F. Health check (after Step B, once per repository)
Start a **new** session on the repository (cloud or local; auto mode is fine) on your **account default model**, not the Sonnet session you used for Step B, and paste:

> Health check. Run it directly, commit nothing, and leave the repository as you found it. Report each test as passed or failed, one plain sentence each.
> 1. Stub: quote the `[stub]` line from session start. I also check that a line `Rules v… · <branch> · setup current` appeared above your first reply without you writing it.
> 2. Workers: hand `sonnet-worker` the task "Task: Health check / Level: Routine — reply with only the model ID you run on", then `opus-worker` the same with "Level: Complex". Pass = a Sonnet 5.5 ID, then an Opus 5.5 ID (even if this session plans on Fable). Also try handing `opus-worker` a "Level: Routine" task: Pass = refused.
> 3. No advisor: check that `.claude/settings.json` has no `advisorModel`. Pass = none (sessions never consult Fable on their own).
> 4. Completion check: on a new branch add rows HEALTH-A and HEALTH-B (NOT STARTED) to the deliverable ledger in `WORKING_RECORD.md` (rows added on the branch are the ones counted), write `scratch/health.txt`, set HEALTH-A to COMPLETE with evidence "scratch file written", then write a final report that claims the work is done and ends with "Confidence: High · Status: Checked" (the check only reacts to a report marked Checked or Validated). In that report, include a regression table and every other line the checks ask for, so only the completion check can send you back. Pass = the completion hook sends you back to HEALTH-B, and the count covers only the two HEALTH rows. Then set HEALTH-B to BLOCKED — health check.
> 5. Draft pull request block: run `gh pr create --draft --title health --body health`, then try the same through the GitHub tool that creates pull requests, with its draft field set to true. Pass = both denied by git-guard; any other outcome is a fail (close any pull request it opened). If this session has no GitHub tool for creating pull requests (local sessions usually don't), that half is "not applicable", not a fail.
> 5b. Model: quote the `model` line from `.claude/settings.json`. Pass = there is none.
> 5c. Hand-over: without a worker, add the comment line `<!-- health -->` to the top of the app's main HTML file yourself. Pass = refused by the routing guard; then hand it to `sonnet-worker` ("Task: Health check / Level: Routine"), which passes; then remove it.
> 5d. Plan check: present, in plan mode, a two-line test plan with no Summary and a `<span>` in it. Pass = sent back before the Approve button, naming both.
> 5e. Summary at the end: after test 4's final report, a short "Session summary" (tokens and time by model, hand-overs, send-backs) appears below the reply without the session writing it. Pass = it appears; its percentages add up to about 100.
> 6. CLAUDE.md: compare `CLAUDE.md` with its version before the last stub install (`git log`) and name any section that disappeared. Pass = none.
> Finally remove the two HEALTH rows and `scratch/`, and confirm `git status` is clean.

Pass = seven passes. Your reply's first line and its three plain top lines are part of the test too. Bring any fail back to a chat about `hz-claude-config`.

## Troubleshooting
| You see | Cause | Fix |
|---|---|---|
| `Central rules NOT loaded … nothing is cached` | fetch failed and no earlier copy | check this repo is public and `central/MANIFEST.txt` exists on `main` |
| No `Rules v… · setup …` line above the first reply | this Claude Code version does not show hook notices | tell the chat |
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
