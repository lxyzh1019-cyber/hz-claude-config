---
name: hz-plan-regression-guard
description: Prevent silent feature loss when editing a plan, document, app, or spreadsheet from one version to the next. Use this skill WHENEVER the user asks to edit, revise, update, refactor, or produce a new version of an existing exercise plan, training plan, design doc, app, or any artifact that has accumulated features across versions — even if they don't say "regression" or "don't lose anything." Trigger on phrases like "update the plan", "v3 of this", "add X to the training plan", "revise this", "make these changes", or any version-to-version edit where features could quietly disappear. Especially trigger when the user has a history of features getting lost between versions.
---

# Plan Regression Guard

## The problem this solves

When an artifact is edited version-to-version, features get lost silently. This happens because an edit regenerates the artifact from whatever is in working attention — not from a diff against the prior version. A feature that isn't actively re-stated can fall out, and nobody notices until much later. The user explicitly has no reliable way to catch this. This skill IS that reliable way.

## The core discipline

Every edit follows the same three-phase loop. Do not skip a phase, even for small edits — small edits are where features quietly drop.

### Phase 1 — Extract the manifest (BEFORE editing anything)

A **manifest** is the list of locked, non-negotiable features the current version has. Before making any change:

1. Locate the manifest if one exists (see "Where the manifest lives" below).
2. If no manifest exists yet, BUILD one by reading the current version end-to-end and listing every distinct feature, behavior, rule, section, or capability. State this list to the user and ask them to confirm/correct it before proceeding. This one-time cost prevents every future regression.
3. Hold the manifest as the checklist for this edit.

A feature is anything a future reader would miss if it vanished: a scoring rule, a UI tab, a section, a formula, a constraint, a phase of the plan, a special case ("Chinese restricted to parent-reference only"), a data field, an export option.

### Phase 2 — Make the requested change

Apply exactly what the user asked for. If the change intentionally *removes* a manifest feature, that's fine — but call it out explicitly in Phase 3 as an intentional removal, not a silent one. Update the manifest to reflect intentional additions and removals.

### Phase 3 — Verify against the manifest (BEFORE delivering)

Walk the manifest item by item against the new version. For each item, confirm it is present and intact. Then report using the regression table format below. NEVER deliver a new version without this check.

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

Any `❌ MISSING` line means STOP — surface it to the user and fix or confirm before considering the edit done. A `⚠️` line is allowed only if the user explicitly asked to remove that feature this turn.

## Where the manifest lives (by format)

The discipline is identical across formats; only the storage location changes.

- **Text/markdown/Word doc** → an HTML comment block or a "Locked Features" section pinned at the top. See `references/manifest-formats.md`.
- **App / code** → a header comment block at the top of the main file, e.g. `<!-- FEATURE MANIFEST v28b: persistent CRQ_DB cache; SELECT INTO; post-materialization indexes; ... -->`.
- **Spreadsheet** → a frozen top block or a dedicated `_Manifest` sheet.
- **Pasted-in-chat plan with no file** → there's nowhere to pin it, so hold the manifest in the conversation, restate it at the top of each new version, and run the regression check in chat every turn.

Read `references/manifest-formats.md` for the exact template per format and for how to bootstrap a manifest on an artifact that doesn't have one yet.

## Versioning

Always label versions explicitly (v1, v2, v28b — match whatever scheme the user already uses). The regression table header references the old and new version numbers so the user can trace what changed when.

## What NOT to do

- Do not regenerate the whole artifact from memory and hope features survive. Diff against the manifest.
- Do not assume a feature is unimportant because the current edit doesn't touch it. Untouched features are exactly the ones that vanish.
- Do not skip the check on "trivial" edits.
- Do not silently improve or "clean up" features the user didn't ask you to change.
