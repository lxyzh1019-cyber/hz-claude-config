# HZ skill trigger tuning — procedure

Skills fire on description match. A skill you "forget to trigger" has a description that does not match how you actually phrase requests. This procedure fixes that in three passes; run it once now, then whenever a skill silently fails to fire twice.

## Pass 1 — Evidence (30 min, once)
1. For each HZ skill, collect 8–10 real prompts from past chats where it *should* have fired. Use `conversation_search` on the skill's topic words; copy the user turns only.
2. Mark each prompt: fired / did not fire (from the chat history — did the skill's structure appear in the answer?).
3. Skills with < 50% fire rate go to Pass 2. Skills that never fired and have no real prompts go to Pass 3 (cull).

## Pass 2 — Description rewrite (per skill)
Use `skill-creator` → description optimizer with the Pass 1 prompts as the test set. Rules for the new description:
- First sentence: what it does. Second sentence onward: "Use this skill WHENEVER…" followed by the user's *actual* phrasings from Pass 1, verbatim, including Chinese phrasings if used.
- Include artifact names the user really types (index.html, CRQ, Marlins, STAR, v28b), not category words.
- Add the negative: "Do NOT trigger for …" so it stops competing with neighbours.
- Keep under ~120 words; the descriptions of all skills are in context every turn.
Re-run the prompts; target ≥ 80% fire rate before accepting.

## Pass 3 — Cull and merge
Near-duplicates suppress each other. Candidates from the current library:
- hz-ai-usage-reviewer + hz-token-saver-audit + hz-ai-health-check → keep hz-ai-health-check as the only entry point; the other two become its references, not separate skills.
- hz-idea-to-build + hz-project-skill-mcp-picker → one skill; the picker is a step inside idea-to-build.
- hz-guarantee-audit + hz-outcome-audit + hz-plan-regression-guard + hz-web-app-audit → keep all four; make hz-guarantee-audit the front door (its hand-off table already routes to the other three) and remove trigger overlap from the three specialists' descriptions.
Decide per pair; do not merge skills with different hard rules (outcome-audit's no-build rule must survive).

## Pass 4 — Deterministic layer (Claude Code only)
`.claude/hooks/skill-router.json` maps keywords/regex → "invoke skill X" injected on every prompt. Add the Pass 1 phrasings there for the skills that matter most. This is the only layer that guarantees invocation; keep it to the 5–7 skills you rely on daily.

For the executor, preload instead of trigger: `skills: [hz-plan-regression-guard]` in `opus-worker.md` injects the skill's full content at spawn. Requires the skill directory to exist under `.claude/skills/` in the repo.

## Pass 5 — Re-measure
After two weeks, repeat Pass 1 on new chats. A skill still under 50% either has the wrong description or is not a real workflow — cull it.
