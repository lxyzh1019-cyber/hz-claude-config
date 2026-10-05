# Model guidance sources

Moved here from the central rules in v3.1.28 (the rules point to this page). Rules marked as model-specific follow these sources; re-check them when a model changes.

Anthropic's published guidance for Claude Opus 5.5 and Claude Sonnet 5.5:

- Anthropic, *Prompting Claude Opus 5.5*, Claude Platform Docs — https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5 (effort calibration, removing think-harder instructions, naming unwanted early stops, reasoning-extraction declines).
- Anthropic (Addy Osmani), *Getting the most out of Opus 5.5 in Claude and Claude Code*, claude.dev, 2026-09-22 — https://claude.dev/blog/getting-the-most-out-of-opus-5-5/ (CLAUDE.md stop rule, finish line per task, subagent split with evidence checks, task list in a file, "needs from you" first, merge-blocking review prompt, marking what couldn't be confirmed).
- Anthropic, *Introducing Claude Sonnet 5.5*, 2026-09-28 — https://www.anthropic.com/claude-sonnet-5-5 (Sonnet 5.5 for well-scoped tasks, bug fixes, polish; Opus 5.5 for open-ended work needing sustained judgment; Sonnet complements Opus at lower effort, matches Opus cost at higher effort).
- Anthropic, *Sonnet 5.5 migration guide*, Claude Platform Docs — https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide.
- Anthropic, *Escalate hard decisions with the advisor tool*, Claude Code Docs — https://code.claude.com/docs/en/advisor (pairings: Opus 5.5 accepts Fable or Opus 5+ as advisor; Claude decides when to consult; subagents inherit; billing; Fable consent).
- Anthropic, *Model configuration*, Claude Code Docs — https://code.claude.com/docs/en/model-config (the `model` setting is an initial selection that overrides the account default, and aliases resolve per provider, so the stub sets none; subagent `model` accepts an alias, a full model ID or `inherit`; `medium` default for Opus 5.5 and Sonnet 5.5; effort calibrated per model; safeguard fallback targets).
