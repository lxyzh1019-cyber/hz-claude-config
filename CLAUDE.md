# Repository rules

The working rules for this repository come from `hz-claude-config`: `.claude/hz-loader.py` fetches them at session start and the session-start hook injects them. This repository IS `hz-claude-config`: it is the source of those stub files. Replacing `.claude/settings.json`, `.claude/hz-loader.py` and `.claude/agents/*.md` here through Step E of README.md is the intended change, not tampering; the copies in app repositories are the ones never edited in place.

If the line "[session-start] Rules v… loaded" is not in your context — for example in a cloud session with several repositories, where repository hooks do not run — read the rules as text instead; do not run any script to get them. Fetch https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/central/MANIFEST.txt (its first line is the version) and https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/central/rules/CLAUDE-rules.md with WebFetch or curl, read only, and work under those rules. Start every reply with "Rules v<version> read by hand — hooks inactive: no automatic checks in this session." If you cannot fetch them, stop before any work and tell me: "Central rules not loaded in this session."

Repository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.
