# hz-claude-config — central working rules (v3.1.6)

Everything central lives here: the rules, the hook logic, the executor's instructions and the audit skills (`central/`). Each app repository keeps only a small **stable stub** — `.claude/settings.json`, `.claude/hz-loader.py`, `.claude/agents/opus-worker.md`, a pointer `CLAUDE.md` — plus its own `FEATURES.md` and `WORKING_RECORD.md`.

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
| `docs/` | rules review copy (revision markers), skill-trigger tuning procedure, claude.ai preference line |

## A. Update this repository (once)
On github.com open `hz-claude-config` → **Add file → Upload files** → drag in `hz-claude-config-v3.1.6.zip` → commit. Start a cloud session on this repository and paste:

> Skip the plan and run it directly. Delete every tracked file in this repository except `hz-claude-config-v3.1.6.zip`. Unzip that zip with Python into the repository root, then delete the zip. Run `bash central/hooks/replay-hooks.sh` and show the last line. Commit, push, and open a pull request.

Expect `passed=41 failed=0`. If the session asks you to approve a plan or a commit first, approve it. Merge the pull request on github.com — the loader reads `main`.

## B. Pilot one app repository
Start a cloud session on the pilot repository and paste:

> Skip the plan and run it directly. I explicitly allow running this specific script: `curl -fsSL https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/stub/install-stub.sh | bash`. I also authorize running it in this main session rather than through opus-worker, because a subagent cannot receive this permission. Run it from the repository root and show me the full output. If the last line is `INSTALL OK`, commit on a new branch, push, and open a pull request. If it is not, change nothing and stop.

- The `SMOKE TEST: [session-start] Rules v3.1.6 loaded` line proves this repository's sessions can fetch from `hz-claude-config` — the one thing the probe did not cover.
- The permission sentence is there because Claude Code's safety check refuses a downloaded script piped into bash without your explicit say-so; if it still asks, give it in your own words. If the session asks to approve a plan or a commit first (rules v2 may still be active in this repo), approve it.
- Read the output: it lists what was removed and whether `README.md` was restored — check a restored README before merging.
- If the output ends with `NOT INSTALLED` after "LOCAL CHANGES FOUND", that repo's own sessions improved the v2 rules files after installing them. Nothing was changed. Bring the listed files' history to Claude so the improvements go into `hz-claude-config` first, then rerun.
- A repo's own sections under the old rules (for example "This Repository — read ARCHITECTURE.md too") are kept after the pointer; the output names them. If the session finds that README, FEATURES or WORKING_RECORD still describe removed files, let it correct those references in the same commit — and check in the diff that nothing else in them changed.

Merge the pull request. Then start a **new** cloud session on the pilot and type `hi`. Pass = the first reply states **Rules v3.1.6 loaded** (or later) and the branch, and ends with the `Confidence: … · Status: …` line.

## C. The other app repositories
Repeat B's paste-and-merge in each. Close any old `rules-v2` / `rules-sync/*` pull requests and delete those branches.

## D. GitHub Desktop clones
For each cloned repository: set **Current Branch** to `main`, then **Fetch origin** → **Pull origin**. Start local sessions only on `main` or a branch made from the current `main`. Optional local check: open a local session in the desktop app on that folder and type `hi` — the same pass criteria prove Python and bash work on your PC. An error mentioning bash or python means one is missing (install Python from python.org).

## E. Every future update
In a cloud session on this repository: make the change under `central/`, run `python3 tools/build_manifest.py <new version>` and `bash central/hooks/replay-hooks.sh`, commit, open a pull request, merge. Every repository loads the new version at its next session start; GitHub's raw-file cache can delay that by a few minutes.

**Rare:** a change to a stub file (`stub/`) — model, permissions, the loader itself — needs B's paste again in each repository. Everything else never does.

**v3.1.6 is such a stub change** (no commit/push prompts, `git-guard`). Re-run B's paste once in every repository installed before v3.1.6 — Weekly-Planner so far; `hz-claude-config` gets it from Step A. Repositories installed later get it automatically.

## Troubleshooting
| You see | Cause | Fix |
|---|---|---|
| `Central rules NOT loaded … nothing is cached` | fetch failed and no earlier copy | check this repo is public and `central/MANIFEST.txt` exists on `main` |
| `offline: using cached vX` | fetch failed, earlier copy used | usually temporary; persistent → same check as above |
| Old version still loaded after an update | raw-file cache | wait a few minutes; start a new session |
| `INSTALL FAILED — do not merge` | smoke test could not load the rules | run A first (central must be on `main`), then retry |
| `NOT INSTALLED` after "LOCAL CHANGES FOUND" | the repo improved its v2 rules files locally | fold the improvements into `hz-claude-config` first (see B) |
| Hook errors in a local session | Python or bash missing on the PC | install Python from python.org |
| Hooks fire twice | rules v2 copies still in a repo or clone | run B in that repo; Pull origin in its clone |
| A local session loads old rules (v2.x) or no loader | the clone is on an old branch made before the install | in GitHub Desktop set **Current Branch** to `main` (or a branch made from today's `main`), **Fetch origin**, **Pull origin**, then start a new session |
