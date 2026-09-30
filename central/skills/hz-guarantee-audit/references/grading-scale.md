# Grading scale by artifact type

One scale, four grades. "Guaranteed" always means: a mechanism outside the model's goodwill enforces it.

| Artifact | Guaranteed | Checked | Assumed | Broken |
|---|---|---|---|---|
| Rules / config (CLAUDE.md, settings, hooks, agents) | Native feature (plan mode, permissions, `model:`) or a hook that blocks/injects deterministically | Observed working in one session; adherence-based | Prose rule never observed to fire, or unobservable (effort level) | Rule contradicts a mechanism (e.g. forbids the only working method) or observed failing |
| Training / exercise plan | Constraint built into the schedule (load ceiling, rest day, session count) that the plan cannot violate without visible change | Coach or user confirmed it once | Load, progression, or recovery assumed but never totalled or checked against both sports | Known overload, missing block, or contradiction between weeks |
| App / HTML / Firebase | Enforced by structure: single owner for shared state, data constraint, security rule, build-time check, test in CI | A test exists and passed once, or user saw it work | Feature present in code, never exercised on a real device/account | Reported failing, or a code path that cannot run |
| SQL / VBA / Excel | Constraint, index, or contract that makes the wrong result impossible; automated compare against baseline | Row counts / totals matched once | Query "looks right"; never reconciled | Wrong output, timeout, or memory failure |

## Questions that separate Assumed from Checked
- What was actually run, on which date, by whom, with what result?
- If that thing broke tomorrow, what would notice — a test, a hook, a person, or nothing?
- "Nothing" → Assumed, no matter how confident the text sounds.
