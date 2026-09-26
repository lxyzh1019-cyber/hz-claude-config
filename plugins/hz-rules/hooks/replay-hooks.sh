#!/usr/bin/env bash
# Replays synthetic hook inputs through every hz-rules hook in an isolated temporary project.
# Run from anywhere: bash plugins/hz-rules/hooks/replay-hooks.sh  (never touches a real repo)
set -u
H="$(cd "$(dirname "$0")" && pwd)"
PROJ=$(mktemp -d); T=$(mktemp -d); FAKEHOME=$(mktemp -d)
export CLAUDE_PROJECT_DIR="$PROJ" HOME="$FAKEHOME" PYTHONDONTWRITEBYTECODE=1
unset CLAUDE_PLUGIN_ROOT
cp "$H/config.json" "$T/config.bak"
trap 'cp "$T/config.bak" "$H/config.json"; rm -rf "$PROJ" "$T" "$FAKEHOME"' EXIT
cd "$PROJ"
pass=0; fail=0
check(){ # name expected_substring actual
  if grep -q -- "$2" <<<"$3"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1 -> ${3:0:200}"; fail=$((fail+1)); fi; }
printf '# FEATURES — test app — manifest v1\n- login\n' > FEATURES.md
printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n' > WORKING_RECORD.md

# --- transcripts
cat > "$T/ok.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"fix the bug"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/repo/js/app.js"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/repo/WORKING_RECORD.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nRegression table\n| Feature | Status |\n| login | kept |\n\nConfidence: Medium · Status: Validated — npm test 12/12"}]}}
J
cat > "$T/noline.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"hello"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Here is the answer without a validation line."}]}}
J
cat > "$T/norecord.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"fix the bug"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Write","input":{"file_path":"/repo/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Fixed.\n\nConfidence: High · Status: Checked"}]}}
J
cat > "$T/gov.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"update the rules"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"/repo/CLAUDE.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Updated.\n\nConfidence: High · Status: Checked"}]}}
J

# --- Stop: validation line
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/validation-line.py); check "validation-line passes good line" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | python3 $H/validation-line.py); check "validation-line blocks missing line" '"decision": "block"' "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":true}" | python3 $H/validation-line.py); check "validation-line no loop" "^$" "$o"
# --- Stop: record guard
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard passes complete turn" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard blocks missing record+table" "regression table" "$o"
o=$(echo "{\"transcript_path\":\"$T/gov.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard exempts governance edits" "^$" "$o"
printf '# FEATURES — <app or plan name> — manifest v1\n' > FEATURES.md
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard blocks on template manifest" "unfilled template" "$o"
printf '# FEATURES — test app — manifest v1\n- login\n' > FEATURES.md
# --- SessionStart
o=$(echo '{}' | python3 $H/session-start.py); check "session-start injects version" "Rules v" "$o"
check "session-start reports routing mode" "routing guard mode" "$o"
# --- UserPromptSubmit: plan gate
o=$(echo '{"prompt":"please:\n- add a button\n- fix colour\n- change the schema"}' | python3 $H/plan-gate.py); check "plan-gate full tier on 3 bullets" "Full 'Plan vN" "$o"
o=$(echo '{"prompt":"- rename the label on the home tab"}' | python3 $H/plan-gate.py); check "plan-gate micro tier on 1 bullet" "Micro-plan" "$o"
o=$(echo '{"prompt":"what time is it"}' | python3 $H/plan-gate.py); check "plan-gate silent on chat" "^$" "$o"
# --- Hotspot counter
rec(){ printf '# WORKING RECORD\n\n## Hotspot counter\n%s\n%s\n%s\n\n## Deliverable ledger\n' "$1" "$2" "$3" > WORKING_RECORD.md; }
NEWH='| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |'
NEWS='|---|---|---|---|---|---|---|'
rec "$NEWH" "$NEWS" '| login sync | 3 | 0 | 0 | 0 | lost data | no |'
o=$(echo '{}' | python3 $H/session-start.py); check "session-start alerts on 3 fix rounds" "Area 'login sync' has hit" "$o"
o=$(echo '{"prompt":"what time is it"}' | python3 $H/plan-gate.py); check "plan-gate alerts on any prompt at threshold" "redesign threshold" "$o"
rec "$NEWH" "$NEWS" '| login sync | 3 | 0 | 0 | 0 | lost data | yes 2026-09-25 |'
o=$(echo '{}' | python3 $H/session-start.py); check "no alert once reviewed" "clean" "$(echo "$o" | grep -c 'has hit the redesign threshold' | sed 's/^0$/clean/')"
rec "$NEWH" "$NEWS" '| timer | 1 | 0 | 0 | 3 | extra guards | no |'
o=$(echo '{}' | python3 $H/session-start.py); check "alert on 3 workarounds" "workarounds 3" "$o"
rec "$NEWH" "$NEWS" '| chores | 1 | 0 | 1 | 0 | broke badge | no |'
o=$(echo '{}' | python3 $H/session-start.py); check "alert on 1 caused regression" "regressions 1" "$o"
rec '| Area / feature | Fix rounds | Recurrences | Last symptom | Rewrite-vs-repair reviewed? |' '|---|---|---|---|---|' '| allowance | 1 | 2 | same total bug | no |'
o=$(echo '{}' | python3 $H/session-start.py); check "old table format still parses" "recurrences 2" "$o"
rec "$NEWH" "$NEWS" '| | 0 | 0 | 0 | 0 | | no |'
o=$(echo '{}' | python3 $H/session-start.py); check "blank seed row is ignored" "clean" "$(echo "$o" | grep -c 'redesign threshold' | sed 's/^0$/clean/')"
o=$(echo '{"prompt":"the timer is broken again"}' | python3 $H/plan-gate.py); check "fix words trigger counter reminder" "+1 fix round" "$o"
check "fix words trigger read-history step" "Checked against:" "$o"
o=$(echo '{"prompt":"- rename the home tab label"}' | python3 $H/plan-gate.py); check "micro-plan asks for both new lines" "Removes/consolidates:" "$o"
# --- Central install behaviour
o=$(echo '{}' | python3 $H/session-start.py); check "session-start reports plugin version" "Rules v3.0.0" "$o"
check "rules injected when not loaded natively" "injected by the hz-rules" "$o"
check "injected text contains the rules" "My Environment" "$o"
mkdir -p "$FAKEHOME/.claude" && printf '# Global Working Rules — hz-rules v3\n' > "$FAKEHOME/.claude/CLAUDE.md"
o=$(echo '{}' | python3 $H/session-start.py); check "native rules detected" "loaded as ~/.claude/CLAUDE.md" "$o"
check "no double injection when native" "clean" "$(echo "$o" | grep -c 'My Environment' | sed 's/^0$/clean/')"
rm -f "$FAKEHOME/.claude/CLAUDE.md"
mv FEATURES.md F.bak
o=$(echo '{}' | python3 $H/session-start.py); check "missing per-repo file reported" "Missing per-repo files: FEATURES.md" "$o"
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard points to seed templates" "seed" "$o"
mv F.bak FEATURES.md
o=$(echo '{"prompt":"review my index.html, is this working?"}' | CLAUDE_PLUGIN_ROOT="$H/.." python3 $H/skill-router.py); check "plugin mode namespaces bundled skill" "hz-rules:hz-guarantee-audit" "$o"
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "cloud mode keeps bundled skill bare" "\`hz-guarantee-audit\`" "$o"
# --- UserPromptSubmit: skill router
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "skill-router matches guarantee-audit" "hz-guarantee-audit" "$o"
check "skill-router prefixes account skill" "anthropic-skills:hz-web-app-audit" "$o"
check "skill-router keeps repo skill bare" "\`hz-guarantee-audit\`" "$o"
# --- PreToolUse: routing guard
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"/repo/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard observe mode allows" "^$" "$o"
sed -i 's/"observe"/"enforce"/' $H/config.json
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"/repo/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard enforce denies main-session source edit" '"deny"' "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"/repo/CLAUDE.md"}}' | python3 $H/routing-guard.py); check "routing-guard enforce allows governance edit" "^$" "$o"
sed -i 's/"enforce"/"observe"/' $H/config.json
echo; echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
