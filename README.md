# hz-claude-config — central working rules (hz-rules v3)

One repository holds the rules, hooks, executor agent and audit skills. They are **installed centrally**, never copied into app repos:

- **Cloud sessions** (desktop app, claude.ai/code): the cloud environment's **setup script** installs a pinned release into the cloud machine's `~/.claude`.
- **Local sessions** (GitHub Desktop clones): the **`hz-rules` plugin**, installed once at user scope, with auto-update.
- **Each app repo** keeps only a short pointer `CLAUDE.md`, plus its own `FEATURES.md` and `WORKING_RECORD.md`.

These instructions live only here. Chat replies point here instead of restating them.

Labels marked *(unverified)* were not confirmed against current docs; if one doesn't match what you see, follow the intent and tell Claude.

## Layout
| Path | What it is |
|---|---|
| `plugins/hz-rules/` | the plugin: `rules/`, `hooks/`, `agents/`, `skills/`, `seed/` templates, `.claude-plugin/plugin.json` (**the only place the version lives**) |
| `.claude-plugin/marketplace.json` | marketplace `hz-config`, used by local installs |
| `cloud/` | `setup-script.txt` (paste into the environment), `install-cloud.sh`, `settings-template.json` |
| `repo-stub/CLAUDE.md` | the pointer each app repo gets |
| `docs/local-user-settings.json` | model and permissions for your PC's user settings |
| `scripts/`, `retired.txt`, `repos.txt`, `workflow-migrate.yml` | **one-time** migration of app repos; retire after use |
| `docs/` | rules review copy (revision markers), skill-trigger tuning procedure, claude.ai preference line |

## A. One-time: set up this repo
1. On github.com open `hz-claude-config` → **Add file → Upload files** → drag in `hz-claude-config-v3.0.0.zip` → commit. Start a cloud session on this repo and paste:
   > Unzip `hz-claude-config-v3.0.0.zip` with Python into the repo root so `README.md`, `plugins/`, `.claude-plugin/`, `cloud/`, `repo-stub/`, `scripts/`, `docs/`, `FEATURES.md`, `WORKING_RECORD.md`, `repos.txt`, `retired.txt`, `workflow-migrate.yml` sit at the root, replacing the v2 files. Delete the zip and the old v2 folders `shared/` and `seed/`, and `workflow-sync-rules.yml`. Run `bash plugins/hz-rules/hooks/replay-hooks.sh` and show the last line. Commit and push.

   Expect `passed=37 failed=0`. If the session pushed to a branch, merge its pull request.
2. **Make the repo public** (it holds no secrets; cloud sessions and local installs fetch it without credentials): repo **Settings** → **Change visibility** → Public *(unverified label)*.
3. **Publish release `v3.0.0`:** repo → **Releases** → create a new release → tag `v3.0.0` on `main` → publish *(unverified labels)*. The tag must match `version` in `plugins/hz-rules/.claude-plugin/plugin.json`.

## B. One-time: cloud environment
1. Go to claude.ai/code and open the **environment selector**. Create an environment (for example `hz-rules`), network access **Trusted**.
2. Open `cloud/setup-script.txt`, replace `REPLACE_WITH_YOUR_GITHUB_USERNAME` with your GitHub username, and paste the whole file into the environment's **Setup script** field. Save.
3. Use this environment for your cloud sessions. The "Default" environment cannot hold a setup script. *(How to make it the default in the desktop app: unverified — check the environment picker when starting a cloud session.)*

## C. One-time: local (PC, GitHub Desktop clones)
1. In the desktop app, open a **local** session on any GitHub Desktop clone and type:
   > /plugin marketplace add YOUR_GITHUB_USERNAME/hz-claude-config

   Then install the plugin: click **+** next to the prompt box → **Plugins** → **Add plugin** → `hz-rules` → scope **your user account**.
   *(If the desktop app does not accept the `/plugin` command, say so in the session; the plugin browser is the documented desktop route, but adding a new marketplace there is unverified.)*
2. Turn on auto-update: `/plugin` → **Marketplaces** → `hz-config` → **Enable auto-update** (third-party marketplaces start with it off).
3. In the same session, paste:
   > Merge `docs/local-user-settings.json` from github.com/YOUR_GITHUB_USERNAME/hz-claude-config into my user settings file `C:\Users\Heng Z\.claude\settings.json`: set `model`, set `permissions.defaultMode`, add the `ask` and `deny` entries, keep every existing key. Then run `python --version` and `bash --version` and show both.

   The hooks need Python and bash. Without them the rules still load, but the hook checks don't run locally; install Python from python.org if it's missing.

## D. One-time: migrate the app repos
Check each app repo's `main` on github.com.

**If no repo has rules-v2 files on `main`** (no `.claude/` folder, `CLAUDE.md` is not "Global Working Rules"): skip the workflow. In each repo, close any `rules-v2` / `rules-sync/*` pull requests and delete those branches. Optionally add the pointer: **Add file → Create new file** → `CLAUDE.md` → paste `repo-stub/CLAUDE.md` → commit to a new branch → merge.

**If any repo has them on `main`**, run the migration once:
1. **Add file → Create new file** in this repo, name `.github/workflows/migrate.yml`, paste `workflow-migrate.yml`, commit to `main`.
2. Create a fine-grained token at https://github.com/settings/personal-access-tokens/new — **Only select repositories** (the app repos), **Contents: Read and write**, **Pull requests: Read and write**. Copy it.
3. This repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → name `RULES_SYNC_TOKEN` → paste → **Add secret**.
4. Edit `repos.txt`: one `owner/repo` per line, only the pilot uncommented. **Actions** → **Migrate app repos to central rules (one-time)** → **Run workflow**. Merge the pilot's PR, verify (section E), then uncomment the rest, run again, merge.
5. In every GitHub Desktop clone: **Fetch origin** → **Pull origin**, so the old local copies are removed. Otherwise local sessions run the old repo hooks **and** the plugin hooks.
6. After all repos are migrated: delete `.github/workflows/migrate.yml` and the token. The migration files can stay in this repo as a record.

## E. Pilot checks (one repo, before the rest)
- New cloud session: first reply states **Rules v3.0.0 loaded** and the branch.
- Delete the validation line in a test reply → the Stop hook makes Claude add it.
- Local session on a GitHub Desktop clone: same two checks; `/plugin` lists `hz-rules` enabled.
- A cloud session in an environment **without** the setup script stops and says "Central rules not loaded in this session."

Record results in this repo's `WORKING_RECORD.md`.

## F. Every future update
1. Change files under `plugins/hz-rules/` in this repo (Claude delivers edits here only).
2. Bump `version` in `plugins/hz-rules/.claude-plugin/plugin.json`. Without the bump, Claude Code skips the update.
3. Run the hook tests (a cloud session on this repo: `bash plugins/hz-rules/hooks/replay-hooks.sh`), commit, publish a release with the same version tag.
4. Cloud: change `V=` in the environment's setup script to the new tag and save; editing the script rebuilds the environment.
5. Local: auto-update installs it; the next session loads it.

No app repo changes, no pull requests, no pulls for rules.

## Troubleshooting
| You see | Cause | Fix |
|---|---|---|
| "Central rules failed to install" | setup script could not download the release | check the tag exists, the repo is public, and the environment's network allows github.com and codeload.github.com |
| "Central rules not loaded in this session" | session ran in an environment without the setup script, or plugin not installed locally | pick the hz-rules environment / install the plugin |
| Rules load but hook checks never fire in cloud | hooks from `~/.claude/settings.json` not run in the cloud VM | report it; this is the pilot's open question |
| Hook errors locally | Python or bash missing on the PC | install Python from python.org |
| Hooks fire twice | an app repo or clone still has rules-v2 copies | run section D for that repo; Pull origin in its clone |
