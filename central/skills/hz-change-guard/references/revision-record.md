# Revision record — hz-change-guard

Version: 2026-10-11.2
Built on: 2026-10-11.1
Owner: the newest "skill Rewrite" chat (only the owner builds the next package)

Run before every package: `python3 /mnt/skills/plugins/hz-change-guard/scripts/revision_gate.py <new-folder> <installed-folder>`.

## Features (each phrase must stay in this skill's files)
F01 Open with one line | Open with one line
F02 When it runs (full trigger list) | When it runs (full trigger list)
F03 The problem this solves | The problem this solves
F04 The core discipline | The core discipline
F05 Phase 1 — Extract the manifest (BEFORE editing anything) | Phase 1 — Extract the manifest (BEFORE editing anything)
F06 Phase 2 — Make the requested change | Phase 2 — Make the requested change
F07 Phase 3 — Verify against the manifest (BEFORE delivering) | Phase 3 — Verify against the manifest (BEFORE delivering)
F08 Revision gate (every package for an hz- skill or a repo) | Revision gate (every package for an hz- skill or a repo)
F09 Output format | Output format
F10 Findings closed (when the change applies review fixes) | Findings closed (when the change applies review fixes)
F11 Where the manifest lives (by format) | Where the manifest lives (by format)
F12 Versioning | Versioning
F13 What NOT to do | What NOT to do
F14 Checks reminder | Checks reminder
F15 Stop after 3 tries | Stop after 3 tries
F16 Evidence before "done" | Evidence before "done"
F17 Revision record | Revision record
F18 Add his Mandatory requests | **Add his Mandatory requests.**
F19 Impact list | **Impact list.**
F20 Review findings | **Review findings.**
F21 Check every changed file | **Check every changed file.**
F22 Measure the result | **Measure the result.**
F23 Find all, fix together, check once | **Find all, fix together, check once.**
F24 Base check | **Base check.**
F25 Feature check | **Feature check.**
F26 Problem check | **Problem check.**
F27 One owner | **One owner.**
F28 Plan discussion rounds keep one version | **Plan discussion rounds keep one version.**
F29 file content-ledger.md | content-ledger.md
F30 file manifest-formats.md | manifest-formats.md
F31 file coverage_gate.py | coverage_gate.py
F32 file revision_gate.py | revision_gate.py
F33 Impact list relies-on | also list what reads or relies on it
F34 Mandatory from repeat check | Mandatory (said N×)
F35 Left out — OK? | Left out — OK?
F36 Coverage gate --help usage | sys.argv[1].startswith("-")

## Removed (approved, with reason)
none

## Open problems (stay until fixed with proof or he drops them)
P01 Repo copy is older: hz-claude-config `central/skills/hz-change-guard/SKILL.md` has no Mitigated / Below expected statuses and no revision gate | found: 2026-10-10 skill Rewrite Rev5 | next: owner of hz-claude-config copies it in its next version

## Fixed (moved from Open; proof required)
X01 revision_gate.py read lines under "Removed" as features, so an approved removal failed the gate | proof: hz-designer 2026-10-11.2 removal passes; planted test (removed ID not listed) still fails

## Change log
- 2026-10-11.1: record started; features listed from the installed copy; revision gate added (hz-change-guard).
- 2026-10-11.2: revision_gate.py fix: lines under "Removed" are not read as features.
