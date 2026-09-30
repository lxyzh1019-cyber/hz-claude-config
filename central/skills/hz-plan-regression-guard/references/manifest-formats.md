# Manifest formats and bootstrapping

## Bootstrapping a manifest on an artifact that has none

Most existing plans won't have a manifest yet — that's why features have been getting lost. To create one:

1. Read the current version completely.
2. List every distinct feature, rule, section, behavior, constraint, special case, data field, and capability. Err toward over-listing; a manifest with too many items is safe, one with too few leaks.
3. Group related items so the list stays scannable (e.g. "Scoring", "UI tabs", "Data/export", "Special rules").
4. Present the list to the user: "Here's what I read as the locked features of the current version. Confirm or correct, and I'll pin this so nothing drops in future edits."
5. Once confirmed, embed it using the format below that matches the artifact.

## Templates by format

### Markdown / text doc
Pin at the very top:

```markdown
<!-- FEATURE MANIFEST — v3 — confirmed 2026-05-28
Scoring: accuracy-based star ratings; tiered grade lock/mastery gate
Daily: date-seeded daily shuffle
Special: Chinese restricted to parent-reference only
-->
```

Or, if the user wants it human-visible, a collapsible section:

```markdown
## 🔒 Locked Features (v3)
- Accuracy-based star ratings
- Tiered grade lock / mastery gate
- Date-seeded daily shuffle
```

### App / code (single-file HTML, etc.)
Header comment at the top of the main file:

```html
<!--
FEATURE MANIFEST v28b
- Persistent CRQ_DB cache table
- SELECT INTO materialization
- Post-materialization indexes
- Two-export workflow
-->
```

Keep it updated in the same edit that changes behavior, so the manifest and the code never drift apart.

### Spreadsheet
Either freeze rows 1–N as a manifest block above the data, or add a sheet named `_Manifest` with one feature per row and a "confirmed" date column. The frozen-row approach is more visible; the separate sheet keeps the data area clean.

### Pasted-in-chat (no file)
No storage location exists, so:
- Restate the manifest as a short block at the top of every new version you output.
- Run the regression table in chat each turn.
- If the plan is getting large, suggest moving it to a file so the manifest can be pinned and the cost of restating drops.

## Keeping the manifest honest

- Update it in the SAME edit that adds or removes a feature — never in a separate pass.
- When the user intentionally removes a feature, delete it from the manifest AND note the removal in that turn's regression table.
- Periodically (every few versions) re-read the full artifact against the manifest to catch drift — a feature present in the file but missing from the manifest is just as dangerous as the reverse.
