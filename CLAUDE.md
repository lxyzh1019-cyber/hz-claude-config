# Repository rules

The working rules for this repository come from `hz-claude-config`: `.claude/hz-loader.py` fetches them at session start and the session-start hook injects them. This repository IS `hz-claude-config`: it is the source of those stub files. Replacing `.claude/settings.json`, `.claude/hz-loader.py` and `.claude/agents/*.md` here through Step A or Step E of README.md is the intended change, not tampering; the copies in app repositories are the ones never edited in place.

If the "Global Working Rules" are not in your context at session start, stop before any work and tell me: "Central rules not loaded in this session."

Repository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.
