---
name: hz-guarantee-audit
description: Before answering a question about ONE point in an existing artifact, read the WHOLE artifact and grade whether it can guarantee the outcome the user actually needs — then answer the point. Use this skill WHENEVER the user asks about, questions, or wants to fix a specific part of something that already exists — a rules file (CLAUDE.md, settings, hooks, agents), a training or exercise plan, an app or HTML file, a SQL query, a config, a spreadsheet, a prior version of anything — including phrases like "why isn't X working", "is this right", "can you check this part", "does this rule work", "fix this drill", "the colour thing doesn't happen", "what about the validation line", or pasting a file plus a narrow question. Also trigger when the user reports the SAME kind of failure a second time on the same artifact. Do NOT trigger for casual chat, general knowledge, translation, or building something new from scratch. This is the front door for artifact questions: it grades first, then hands off to hz-outcome-audit (trajectory), hz-plan-regression-guard (edits), or hz-web-app-audit (HTML/JS internals) where they fit.
---

# Guarantee Audit

## The problem this solves

The user asks about one point; the answer fixes that point; the rest of the artifact keeps failing in the same way for the same reason. Rules that were never enforceable, plans that were never load-checked, apps whose "working" features were never validated. Each narrow answer costs a round trip and leaves the structural cause untouched. This skill makes the whole-artifact pass mandatory and puts it first.

## Hard sequence — do not reorder

1. **Read the whole artifact.** Not the section the question points at. If it is in a repo, read the governing files too (rules, config, manifest). If versions exist, note which one is live.
2. **State the real need in one line.** "You asked about X; what you need is Y." The need is the outcome, not the feature. If you cannot state it, ask one question and stop.
3. **Grade every requirement the artifact carries** on the four-level scale in `references/grading-scale.md`:
   - **Guaranteed** — enforced structurally; cannot silently regress.
   - **Checked** — verified once; can regress without notice.
   - **Assumed** — never validated; works only if everyone behaves.
   - **Broken** — not delivering now.
4. **Lead with the verdict**, then the table, then the specific answer. Verdict is one sentence: "Whole artifact: N of M requirements Guaranteed; the point you asked about is <grade> because <cause>."
5. **Every item below Guaranteed gets one of two things:** a proposed mechanism that raises the grade, or an explicit "no mechanism exists — stays Assumed" so the residual risk is visible. Never leave a below-Guaranteed row without one of these.
6. **Hand off, don't duplicate.** Version-over-version questions → `hz-outcome-audit`. The user then wants the edit made → `hz-plan-regression-guard`. HTML/JS internals → `hz-web-app-audit`. Say which skill you are handing to and why.

## Proportionality

- Artifact sound, question minor → verdict sentence + the answer. No table.
- Anything Broken or Assumed on the path to the user's need → full table.
- Never pad the table with rows that are trivially Guaranteed; list them in one line ("Guaranteed: a, b, c").

## Output format

```
Whole artifact: <verdict sentence>

| Requirement | Current mechanism | Grade | Fix / residual |
|---|---|---|---|
| … | … | Guaranteed / Checked / Assumed / Broken | … |

Your point: <answer in the context of the table>
Hand-off: <skill, if any, and why> 
```

## What NOT to do

- Do not answer the point first and audit afterwards; the audit changes the answer.
- Do not grade from the section alone; a rule can look fine and be unenforceable because of another section.
- Do not call something Guaranteed because it is written down. Written ≠ enforced. See the scale.
- Do not build or edit in the audit turn unless the user's message already approves the change.

Read `references/grading-scale.md` for grade definitions by artifact type (rules files, training plans, apps, SQL) and `references/handoffs.md` for the hand-off boundaries.
