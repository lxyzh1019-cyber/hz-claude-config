# hz-claude-config — central working rules (v3.1.13)

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

## A. Update this repository (once)
**Permission mode for Steps A, B and E: default (asks before commands), not auto.** Set it before you paste. In auto mode a safety classifier blocks these steps: Step A because it replaces `.claude/settings.json` and the hooks ("instruction poisoning"), Step B because it runs a downloaded script ("code from external") — a sentence in the prompt cannot lift that. Approve the prompts yourself. Normal work afterwards can use auto mode again.

On github.com open `hz-claude-config` → **Add file → Upload files** → drag in `hz-claude-config-v3.1.13.zip` → commit. Start a cloud session on this repository and paste:

> Skip the plan and run it directly. Delete every tracked file in this repository except `hz-claude-config-v3.1.13.zip`. Unzip that zip with Python into the repository root, then delete the zip. Run `bash central/hooks/replay-hooks.sh` and show the last line. Commit, push, and open a pull request.

Expect `passed=114 failed=0`. If the session asks you to approve a plan or a commit first, approve it. Merge the pull request on github.com — the loader reads `main`.

## B. Pilot one app repository
Only after Step A's pull request is merged: a new stub calls checks that exist only in the new central version. Start a cloud session on the pilot repository **in default permission mode** and paste:

> Skip the plan and run it directly. I explicitly allow running this specific script: `curl -fsSL https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/stub/install-stub.sh | bash`. I also authorize running it in this main session rather than through opus-worker, because a subagent cannot receive this permission. Run it from the repository root and show me the full output. If the last line is `INSTALL OK`, commit on a new branch, push, and open a pull request. If it is not, change nothing and stop.

- The `SMOKE TEST: [session-start] Rules v3.1.13 loaded` line proves this repository's sessions can fetch from `hz-claude-config` — the one thing the probe did not cover.
- When the session asks to run the installer, click Allow. If it reports a denial by the "auto-mode classifier", the session is in auto mode: start a new one in default mode. If the session asks to approve a plan or a commit first (rules v2 may still be active in this repo), approve it.
- Read the output: it lists what was removed and whether `README.md` was restored — check a restored README before merging.
- If the output ends with `NOT INSTALLED` after "LOCAL CHANGES FOUND", that repo's own sessions improved the v2 rules files after installing them. Nothing was changed. Bring the listed files' history to Claude so the improvements go into `hz-claude-config` first, then rerun.
- A repo's own sections under the old rules (for example "This Repository — read ARCHITECTURE.md too") are kept after the pointer; the output names them. If the session finds that README, FEATURES or WORKING_RECORD still describe removed files, let it correct those references in the same commit — and check in the diff that nothing else in them changed.

Merge the pull request. Then start a **new** cloud session on the pilot and type `hi`. Pass = the first line of the reply is **Rules v3.1.13 · main** (or later), the reply says the stub is current, and it ends with the `Confidence: … · Status: …` line. Then run Step F once.

## C. The other app repositories
Repeat B's paste-and-merge in each. Close any old `rules-v2` / `rules-sync/*` pull requests and delete those branches.

## D. GitHub Desktop clones
For each cloned repository: set **Current Branch** to `main`, then **Fetch origin** → **Pull origin**. Start local sessions only on `main` or a branch made from the current `main`. Optional local check: open a local session in the desktop app on that folder and type `hi` — the same pass criteria prove Python and bash work on your PC. An error mentioning bash or python means one is missing (install Python from python.org).

## E. Every future update
Agree the change list in chat first (one batch). Then start a cloud session on this repository and paste:

> Here is the agreed change list for hz-claude-config: <paste the list>. Make exactly these changes, bump the version with `python3 tools/build_manifest.py <new version>`, run `bash central/hooks/replay-hooks.sh`, and open a pull request ready for review. Start your report with Result / I need from you / Next, and say whether the stub changed (then Step B is due).

Merge it; if the stub changed, run Step B in each app repository; then Step F in one of them. What the session does, in detail: make the change under `central/`, run `python3 tools/build_manifest.py <new version>` and `bash central/hooks/replay-hooks.sh`, commit, open a pull request (ready for review, not draft), merge. Every repository loads the new version at its next session start; GitHub's raw-file cache can delay that by a few minutes.

**Rare:** a change to a stub file (`stub/`) needs B's paste again in each repository: the session model, the advisor, permissions, the worker files, the `CLAUDE.md` pointer, a new kind of hook event, or the loader itself. New or changed checks, rules text, worker instructions and skills never do — the stub hands every hook event to the central switchboard (`central/hooks/dispatch.py`), and `central/hooks/config.json` lists which checks run. Each session's `[stub]` line says when a repository needs Step B.

**v3.1.13 is such a stub change** (all hook events go through the central switchboard, so future check changes need no Step B; the `CLAUDE.md` pointer gains the multi-repo fallback, refreshed in place by the installer). Every app repository whose session says `[stub] OUTDATED` needs B's paste once, in default mode — today that is all of them: Weekly-Planner, Figure-Skate-Dryland-Timer, Swimming-Dryland-Timer, spelling-pronun. `hz-claude-config` gets it from Step A.

## F. Health check (after Step B, once per repository)
Start a cloud session on the repository (auto mode is fine) and paste:

> Health check. Run it directly, commit nothing, and leave the repository as you found it. Report each test as passed or failed, one plain sentence each.
> 1. Stub: quote the `[stub]` line from session start.
> 2. Workers: ask `sonnet-worker`, then `opus-worker`, to reply with only the model ID they run on. Pass = a Sonnet 5.5 ID, then an Opus 5.5 ID.
> 3. Advisor: consult the advisor once: "Is this health check sound?" Pass = the transcript shows an advisor consultation. If none is possible, say why.
> 4. Completion check: add rows HEALTH-A and HEALTH-B (NOT STARTED) to the deliverable ledger in `WORKING_RECORD.md`, write `scratch/health.txt`, set HEALTH-A to COMPLETE with evidence "scratch file written", then write a final report that claims the work is done. Pass = the completion hook sends you back to HEALTH-B. Then set HEALTH-B to BLOCKED — health check.
> 5. Draft pull request block: run `gh pr create --draft --title health --body health`. Pass = denied by git-guard; any other outcome is a fail (close any pull request it opened).
> 6. CLAUDE.md: compare `CLAUDE.md` with its version before the last stub install (`git log`) and name any section that disappeared. Pass = none.
> Finally remove the two HEALTH rows and `scratch/`, and confirm `git status` is clean.

Pass = six passes. Your reply's first line and its three plain top lines are part of the test too. Bring any fail back to a chat about `hz-claude-config`.

## Troubleshooting
| You see | Cause | Fix |
|---|---|---|
| `Central rules NOT loaded … nothing is cached` | fetch failed and no earlier copy | check this repo is public and `central/MANIFEST.txt` exists on `main` |
| `offline: using cached vX` | fetch failed, earlier copy used | usually temporary; persistent → same check as above |
| Old version still loaded after an update | raw-file cache | wait a few minutes; start a new session |
| `[stub] OUTDATED — … missing: …` | the repository has an older stub | Step B in that repository, default mode, merge |
| Command denied by the "auto-mode classifier" during Step A or B | session in auto mode | new session in default mode, same paste |
| Reply opens with "hooks inactive" | cloud session with several repositories: no repository hooks run | expected; for work that needs the checks, open a session on one repository |
| `INSTALL FAILED — do not merge` | smoke test could not load the rules | run A first (central must be on `main`), then retry |
| `NOT INSTALLED` after "LOCAL CHANGES FOUND" | the repo improved its v2 rules files locally | fold the improvements into `hz-claude-config` first (see B) |
| Hook errors in a local session | Python or bash missing on the PC | install Python from python.org |
| Hooks fire twice | rules v2 copies still in a repo or clone | run B in that repo; Pull origin in its clone |
| A local session loads old rules (v2.x) or no loader | the clone is on an old branch made before the install | in GitHub Desktop set **Current Branch** to `main` (or a branch made from today's `main`), **Fetch origin**, **Pull origin**, then start a new session |
