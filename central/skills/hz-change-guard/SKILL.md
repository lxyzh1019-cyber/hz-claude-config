---
name: "hz-change-guard"
description: "Stop features and agreed content silently disappearing when a plan, document, app, prompt or spreadsheet goes to a new version, or when a discussion or research report is turned into one. Lists what the current version has and must say, makes the change, then proves every item is still there (regression table plus coverage gate). Use this skill WHENEVER the user says \"update the plan\", \"revise this\", \"make these changes\", \"apply fixes 2 and 4\", \"new version\", \"update the file\", \"update the page / app / doc\", \"fix it in the file\", \"apply the fixes\", \"build it from what we discussed\", \"put the research into the page\", \"按这个改\", \"改这个文件\", \"出新版本\", \"更新\", \"修改一下\", or when hz-reviewer hands over because he now wants the change made. Do NOT trigger for judging whether the thing works (hz-reviewer) or for designing something new (hz-designer)."
---

# Plan Regression Guard

## Open with one line
"I'll list what the current version has and what it must say, make the change, then show you a kept / changed / removed check and a content-coverage result so nothing is lost."

## When it runs (full trigger list)
The description carries the main phrases; this is the full list, kept for the
trigger tests. Edit, revise, update or make a new version of something that
already exists: "update the plan", "v3 of this", "add X to the training plan",
"revise this", "make these changes", "new version", "apply fixes 2 and 4",
"update the file", "update the page / app / doc", "fix it in the file",
"apply the fixes", "更新", "修改一下", "改这个文件", "出新版本", "按这个改".
A discussion or research report turned into a plan, doc, page or app: "build it
from what we discussed", "put the research into the page". A hand-over from
hz-reviewer when he now wants the change made.

## The problem this solves

When an artifact is edited version-to-version, features get lost silently. This happens because an edit regenerates the artifact from whatever is in working attention — not from a diff against the prior version. A feature that isn't actively re-stated can fall out, and nobody notices until much later. The user explicitly has no reliable way to catch this. This skill IS that reliable way.

There is a second leak. Content agreed across a long conversation (a rule, a number, a caveat, a section) lives in many earlier messages, documents and reports. When a new version is built from the latest summary, points with no home in that summary fall out — and tests that check the artifact *works* cannot see that it is *incomplete*. So the guard keeps two lists, not one:

- **Feature manifest** — what the artifact *does* (tabs, rules, formulas, behaviors).
- **Content ledger** — what the artifact must *say*: every point agreed in the conversation, each with a search phrase that must appear in the artifact. See `references/content-ledger.md`.

There is a third leak, after a review: a problem shown in a review table can be
left out of the fixes, fixed only in part, or "fixed" without getting better,
and he cannot tell. When the change applies review fixes, the guard also proves
each finding's result (see "Findings closed" below).

## The core discipline

Every edit follows the same three-phase loop. Do not skip a phase, even for small edits — small edits are where features quietly drop.

### Phase 1 — Extract the manifest (BEFORE editing anything)

A **manifest** is the list of locked, non-negotiable features the current version has. Before making any change:

1. Locate the manifest if one exists (see "Where the manifest lives" below).
   **For a skill package** (an hz- skill): first compare with the installed copy
   (`/mnt/skills/plugins/<skill>`) and search past chats for a newer package of
   the same skill (`conversation_search "<skill> package"`). If another chat built
   a newer one, name it and merge its changes first; never build on an older base.
   Deliver only the new package as a card. Never share a rollback as a card: keep
   the rollback file in the chat and send it only when he writes "roll back <skill>".
2. If no manifest exists yet, BUILD one by reading the current version end-to-end and listing every distinct feature, behavior, rule, section, or capability. State this list to the user and ask them to confirm/correct it before proceeding. This one-time cost prevents every future regression.
3. **Add his Mandatory requests.** Run steps 1–3 of the repeat check
   (`/mnt/skills/plugins/hz-reviewer/references/check-repeat.md`; if missing:
   read all his messages in this chat, group the same request in any words,
   count, and mark 3+ mentions Mandatory). Add each Mandatory request to the
   manifest as `Mandatory (said N×)`. A Mandatory item can only leave the
   manifest if he reverses it in a later message.
4. Hold the manifest as the checklist for this edit.
   **Impact list.** Before editing, name every file and section this change will
   touch, and show it in one line. A file or section touched outside that list
   is a regression, the same as a lost feature. Never delete, empty or rename a
   file that is not on the list.
   For each item you remove, rename or make stricter (a rule, a check, a
   feature, a version name), also list what reads or relies on it: checks,
   tests, documents, messages, version mentions. Prove each still works, or
   change it in the same version.
   **Review findings.** When the change applies review fixes, copy every finding
   ID from the review (R1, F2, L3…) onto the impact list, each with its type
   (fix or mitigation) and its expected result. Measure the "before" number now
   for every ID that has one.
5. Build or update the **content ledger**. Sweep the WHOLE conversation and every earlier source (earlier versions, docs, research reports, notes, and earlier chats this work came from: a handoff, or chats he names — search and read them) — never only the latest summary — and give each agreed point one line with a search phrase that must appear in the artifact. From then on, add a ledger line in the same turn a new point is agreed.

A feature is anything a future reader would miss if it vanished: a scoring rule, a UI tab, a section, a formula, a constraint, a phase of the plan, a special case ("export only for admins"), a data field, an export option.

### Phase 2 — Make the requested change

Apply exactly what the user asked for. If the change intentionally *removes* a manifest feature, that's fine — but call it out explicitly in Phase 3 as an intentional removal, not a silent one. Update the manifest to reflect intentional additions and removals.

Whenever a ledger item will not be in the new version (cut while condensing or simplifying, or found missing and not restored), list it under **Left out — OK?** and ask each one as a line in the answer's decision list. Never drop an agreed point silently; a cut is the user's decision, not a side effect of shortening.

### Phase 3 — Verify against the manifest (BEFORE delivering)

Compare what changed with the impact list: any file or section changed outside it is `❌ MISSING`-level and must be undone or confirmed. Walk the manifest item by item against the new version. For each item, confirm it is present and intact. Then report using the regression table format below. NEVER deliver a new version without this check.

**Check every changed file.** Run the artifact's own check (layout check for a page, tests for code) on every file the change touched, not only the main one. A file changed but not checked is unproven.

**Measure the result.** For every review ID, measure the "after" number the
same way as the "before" number, and compare it with the expected result.

Then run the coverage gate on the content ledger: `python3 /mnt/skills/plugins/hz-change-guard/scripts/coverage_gate.py <artifact-file> [ledger-file]` (in chat; elsewhere use this skill's own `scripts/` folder). It prints every ledger phrase missing from the artifact and exits with an error if any is missing. Any MISSING line means STOP — fix it or move it to "Left out — OK?" for the user to confirm.

**Find all, fix together, check once.** Finish the whole manifest walk and the whole gate run before fixing anything. Collect every `❌` row and every MISSING line into one list. Fix them all in one pass, then run the walk and the gate once more. One pass counts as one try for "Stop after 3 tries". For an artifact that only exists in chat, run the same check by hand against the ledger. Tests showing the artifact works are not proof it is complete; only the gate is.

## Revision gate (every package for an hz- skill or a repo)
Runs before any package, zip or pull request is handed over, in every chat,
whether or not a trigger phrase started this skill. Each artifact keeps a
revision record inside it (`references/revision-record.md` for a skill;
`FEATURES.md` plus its open-problems list for a repo): version, the version it
was built on, owner, features with search phrases, open problems, fixed problems.

Run `python3 /mnt/skills/plugins/hz-change-guard/scripts/revision_gate.py <new> <base>`.
`<base>` is the newest real copy: the installed skill (`/mnt/skills/plugins/<skill>`)
or a fresh clone of GitHub main. Never a copy from this chat's memory or uploads.
1. **Base check.** "Built on" in the new record must equal the base's Version.
   A newer base means another build happened: stop, rebuild on the base.
2. **Feature check.** Every feature in the base record is in the new record (or
   under "Removed (approved, with reason)"), and every phrase is in the new files.
3. **Problem check.** Every open problem in the base record is still open in the
   new record or moved to Fixed with its proof. None is dropped.
Any FAIL means STOP: fix it, or ask him as a decision. Show the gate's last line.

**One owner.** Only the chat named in "Owner" builds the next package of that
artifact. Another chat that finds a problem or a new point does not build: it
gives him one open-problem line to paste into the owner chat. He can move the
owner by saying so.

## Output format

End every edit with this block:

```
## Regression check — v{old} → v{new}
| Feature | Status |
|---|---|
| {feature 1} | ✅ kept |
| {feature 2} | ✅ kept |
| {feature 3} | ➕ added this version |
| {feature 4} | ⚠️ intentionally removed (you asked to drop X) |
| {feature 5} | ❌ MISSING — was this meant to go? |
```

Under the table, add two lines:

```
Content ledger: {present}/{total} present (coverage gate)
Left out — OK?: {cut items for the user to confirm, or "none"}
```

A Mandatory row reads `✅ kept (Mandatory, said N×)`; one that is weakened or gone is `❌`.

A missing ledger item counts exactly like a `❌ MISSING` feature.

Any `❌ MISSING` line means STOP — surface it to the user and fix or confirm before considering the edit done. A `⚠️` line is allowed only if the user explicitly asked to remove that feature this turn.

### Findings closed (when the change applies review fixes)
Add one more table, one row per finding ID from the review, none skipped:

```
| ID | Problem | Type · how | Expected | Actual | Status | Proof |
|---|---|---|---|---|---|---|
| F2 | open item answer goes nowhere | Fix · 4-step rule | 100% | 100% | ✅ Closed | phrase found |
| R2 | 27 cost blanks | Mitigation · web prices | 30% fewer | 30% fewer (27 → 19) | ⚠️ Mitigated: 19 wait for quotes | count |
| T1 | 18 min per check run | Fix · changed pages only | 65% faster (est.) | 40% faster (18 → 11 min) | ⚠️ Below expected: big page still slow | timer |
| R6 | upload the Project file | Your action | — | — | 👤 Your action | — |
| G1 | nothing saves | Not fixing · needs the repo | — | — | ⏭ Roadmap | — |
```

- **Status** is one of ✅ Closed · ⚠️ Mitigated (say what remains) ·
  ⚠️ Below expected (say why, and the next step) · 👤 Your action ·
  ⏭ Not fixing (reason and when it comes back).
- **Actual** is measured, not copied from Expected. When it can't be measured
  yet, write "not measured" and say when and how it will be.
- Under the table add one count line: "Findings N · closed N · mitigated N ·
  below expected N · your action N · not fixing N".
- The edit is not done while any review ID is missing from this table.

## Where the manifest lives (by format)

The discipline is identical across formats; only the storage location changes.

- **Text/markdown/Word doc** → an HTML comment block or a "Locked Features" section pinned at the top. See `references/manifest-formats.md`.
- **App / code** → a header comment block at the top of the main file, e.g. `<!-- FEATURE MANIFEST v3: offline cache; weekly reset; parent PIN; ... -->`.
- **Spreadsheet** → a frozen top block or a dedicated `_Manifest` sheet.
- **Pasted-in-chat plan with no file** → there's nowhere to pin it, so hold the manifest in the conversation, restate it at the top of each new version, and run the regression check in chat every turn.

The content ledger sits right next to the manifest, in the same place and the same format family (see `references/content-ledger.md`).

Read `references/manifest-formats.md` for the exact template per format and for how to bootstrap a manifest on an artifact that doesn't have one yet.

## Versioning

Always label versions explicitly (v1, v2, v3b — match whatever scheme the user already uses). The regression table header references the old and new version numbers so the user can trace what changed when.

**Plan discussion rounds keep one version.** While a plan is still being discussed, each new round keeps the same version number and adds one change-log line ("Round 2: …"). Never make v2, v3, v4 before execution. The version closes only when he approves or says there are no more changes; the next change after that gets the next number. During rounds the table header reads `v{n} round {k} → round {k+1}`.

## What NOT to do

- Do not regenerate the whole artifact from memory and hope features survive. Diff against the manifest.
- Do not assume a feature is unimportant because the current edit doesn't touch it. Untouched features are exactly the ones that vanish.
- Do not skip the check on "trivial" edits.
- Do not silently improve or "clean up" features the user didn't ask you to change.
- Do not build a new version from the latest source alone (a summary, a research report). Points agreed earlier in the conversation live elsewhere; the ledger sweep finds them.
- Do not treat "it renders" or "the tests pass" as proof the content is complete.
- Do not report review fixes by fix number alone; report each finding ID, its expected and actual result, and its status.
- Do not call a mitigation a fix: say what remains.

## Checks reminder
After every new version of an app or design, end with one line listing the
checks not run this turn: "Checks not run: flow ☐ logic ☐ repeat ☐ — say
'run all checks' to run all three at once." (Repeat counts as run when the
manifest step above ran it.)

## Stop after 3 tries
If the same check (gate, test, layout check) fails 3 times on the same item,
stop fixing. Report the item, the 3 attempts, and the likely cause, then wait.
A new approach needs his OK; repeating the same fix is not a 4th try.

## Evidence before "done"
A version is "done" only when the proof is shown, not claimed: the regression
table with every item ticked, plus the artifact-specific proof — test output,
a row count, a screenshot, a rendered page — plus the coverage gate output
for the content ledger, plus the revision gate output for a package, plus the findings-closed table with measured results
when review fixes were applied. No proof, no "done"; say what is still
unproven and how to prove it.

## Revision record
Approved features, open problems and fixes: `references/revision-record.md`.
Any change to this skill updates that record in the same build, and the
hz-change-guard revision gate runs before the package is handed over.
