# Feature list conversion (central, v3.1.30) — one plan per app, run once when the owner asks

Goal: a feature list that proves each feature is still there, and record files small enough to read. This file is general for every app. The app's own extras go in its `## References`.

1. **Coverage first.** Before you rewrite, list every current feature line of `FEATURES.md` with a search phrase in `docs/archive/features-coverage.txt`. The new list must contain every phrase or mark the line "removed — owner OK".
2. **By screen.** One section per screen (and one for data and rules). Each feature is one line: what you see or what it does. Then add `— Proof: <test name>` or `— Proof: picture tests/reference/<screen>-<size>.png`. Start the file with `<!-- feature-list: by-screen -->`. From then on, the record check asks every Kept row for a proof.
3. **References.** Add `## References` to `FEATURES.md`, one line each: the screen sizes and looks (`Sizes:`, `Looks:`), and the figures to compare (compare instructions). Add any rule documents the app's tests must cover. Add a test map: `Tests: <area or files> → <tests it needs>`, one line per area, so a fix runs only its tests.
4. **History out.** Build history, old plans, audits and hand-overs move to `docs/archive/` (git keeps the rest). The record files keep only the current state. Workers do not read `docs/archive/` unless the task names it. Notes that repeat the central rules become one line pointing to hz-claude-config.
5. **Rules with checks.** If the app has its own rules file, mark each rule `checked by <script>` or `text only`. A new rule needs one of the two.
6. **Rule documents to tests.** Each line of a rule document named in `## References` names the test that proves it; a line without a test is listed to the owner.
7. **Data rules.** Add a test of the database access rules only after the test tool runs in this repository. Else list it as open.
8. **Reference pictures.** Take the first reference pictures of every screen at every size and look named in `## References`, and commit them.
9. Open one pull request, last, with the coverage result: `<n> of <n> feature lines kept or approved for removal`.
