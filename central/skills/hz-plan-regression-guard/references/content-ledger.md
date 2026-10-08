# Content ledger

The feature manifest says what an artifact *does*. The content ledger says what it must *say*: every point agreed in the conversation that the artifact has to carry. It exists because content drops silently when a new version is built from a summary, and no "does it work" test can see a missing paragraph.

## When to build it

- At the first build of any plan, doc, page or app made from a discussion or a research report.
- On the first edit of an existing artifact that has no ledger yet: read the artifact, sweep the whole conversation and every earlier source, and list what was agreed.
- After that, add a line in the same turn a new point is agreed. Never batch it for later.

## Line format

```
L07 Refund window is 30 days                 | 30-day refund
L12 Two contact routes shown                 | Call us; Email us
```

- `L` + number, a short plain-language label, a bar, then the search phrase.
- Several phrases on one line are separated by `;` — all of them must be present.
- Number lines in order and never reuse a number, so a removed item stays traceable.

## Choosing search phrases

- Use a phrase that appears **verbatim** in the artifact's own text, at least two words long, and unique to that point.
- Avoid bare numbers. A short number such as "1.7" can match inside "11.7" and give a false pass; anchor it with words ("1.7× the injury risk").
- For a bilingual artifact, the phrase in the primary language is enough; checking the translation is part of the normal review.
- If the gate reports a hit you doubt, look at the match in context before trusting it.

## Where it lives

Right after the feature manifest, in the same place:

- **Single-file HTML / code:** inside the same header comment, under a line starting `CONTENT LEDGER`.
- **Markdown / text doc:** in the top HTML comment, the same way.
- **Spreadsheet:** a `_Ledger` sheet beside `_Manifest`, one item per row, phrase in its own column.
- **Office files (docx, pptx, xlsx):** keep the ledger as a small separate `.md` file and pass it to the gate as the second argument, after extracting the artifact's text.
- **Chat-only plan:** restate the ledger with the manifest at the top of each version and check it by hand.

## Running the gate

```
python scripts/coverage_gate.py page.html            # ledger inside the file
python scripts/coverage_gate.py page.txt ledger.md   # ledger in a separate file
```

It searches the artifact text (the ledger block itself excluded), prints `Ledger items: N  Missing: M`, lists each missing phrase, and exits with code 1 if anything is missing. A missing item means STOP: restore it, or put it under "Left out — OK?" for the user to decide.

## Keeping it honest

- When the user removes a point on purpose, delete its line in the same edit and note the removal in that turn's regression table.
- When a point is reworded, update its phrase in the same edit, or the gate will (correctly) fail.
- If the gate passes but the user still finds a gap, the gap was never put in the ledger. Add the line first, then fix the artifact.
