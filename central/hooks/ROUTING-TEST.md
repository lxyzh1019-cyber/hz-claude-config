# Routing guard — measured test (turns "Uncertain" into a result)

Goal: learn whether a PreToolUse hook can tell an `opus-worker` edit from a main-session edit, then switch the guard from `observe` to `enforce` only if it can.

## Step 0 — unit replay
In a cloud session on `hz-claude-config`, run `bash central/hooks/replay-hooks.sh`. Every check must pass. This proves the scripts parse and block correctly; it does not prove field names in real hook input.

## Step 1 — observe real input (any app repo, rules installed, plan approved so edits can run)
1. Prompt: "Directly edit scratch/probe.txt: append the line MAIN." → main session edits.
2. Prompt: "Hand opus-worker: Task: Routing test / Level: Complex — append the line WORKER to scratch/probe.txt." → worker edits.
2b. Prompt: "Hand sonnet-worker: Task: Routing test / Level: Routine — append the line SONNET to scratch/probe.txt." → second worker edits; its record must carry the same marker as the opus-worker record, and the worker's report must name Sonnet 5.5 (proves the `sonnet` alias resolves to 5.5 in this session).
3. Prompt: "Show me .claude/state/routing-guard.jsonl." Three records. Compare `hook_keys`, `markers`, `env`.
4. Ask the session to delete `scratch/` without committing.

## Step 2 — decide
- If the worker record has a field the main record lacks (an `agent_*` key, a different `session_id`, an `AGENT` env var): in `hz-claude-config`, set `central/hooks/config.json` → `"subagent_marker_fields": ["<field>"]` and `"routing_guard_mode": "enforce"`, run `python3 tools/build_manifest.py <new version>`, and merge. Repeat step 1: prompt 1 must be denied, prompt 2 must succeed.
- If the two records are indistinguishable: leave `observe`. The rule stays prose; the log remains an audit trail of every main-session edit.

Record the outcome in hz-claude-config's WORKING_RECORD.md.
