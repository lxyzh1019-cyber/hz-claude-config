# Repository rules

The working rules for this repository come from `hz-claude-config`: `.claude/hz-loader.py` fetches them at session start and the session-start hook injects them. This repository IS `hz-claude-config`: it is the source of those stub files. Replacing `.claude/settings.json`, `.claude/hz-loader.py` and `.claude/agents/*.md` here through Step E of README.md is the intended change, not tampering; the copies in app repositories are the ones never edited in place.

If the line "[session-start] Rules v… loaded" is not in your context — for example in a cloud session with several repositories, where repository hooks do not run — read the rules as text instead; do not run any script to get them. Fetch https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/central/MANIFEST.txt (its first line is the version) and https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/central/rules/CLAUDE-rules.md with WebFetch or curl, read only, and work under those rules. Start every reply with "Rules v<version> read by hand — hooks inactive: no automatic checks in this session." If you cannot fetch them, stop before any work and tell me: "Central rules not loaded in this session."

Repository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.

## Changing this repository (moved here from the central rules in v3.1.28 — it applies only here)

- **Changing `hz-claude-config`.** Name the riskiest live assumption and its proof in the plan's `Checked against:` line (replays are not live proof). Agree the whole change list first; new ideas go to "Next batch" in its record unless I add them. The claude.ai chat builds and tests the change and hands me a full package; Claude Code sessions only for Step B and the Step F live check. After the merge, run Step F in one app and fold its findings into the next batch first.
- **Full packages.** A package for this repository holds every file of the version, so extracting it over the repository folder is always safe.
- **Health check (Step F).** README Step F is the live proof replays can't give: the Sonnet worker's model, no advisor, the completion check, the draft-PR block, the repository's own `CLAUDE.md` sections.
