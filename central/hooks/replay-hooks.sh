#!/usr/bin/env bash
# Replays synthetic hook inputs through every central hook and the loader in an isolated temporary project.
# Run from anywhere: bash central/hooks/replay-hooks.sh  (never touches a real repo)
set -u
H="$(cd "$(dirname "$0")" && pwd)"
PROJ=$(mktemp -d); T=$(mktemp -d); FAKEHOME=$(mktemp -d)
export CLAUDE_PROJECT_DIR="$PROJ" HOME="$FAKEHOME" PYTHONDONTWRITEBYTECODE=1
unset CLAUDE_PLUGIN_ROOT
cp "$H/config.json" "$T/config.bak"
trap 'cp "$T/config.bak" "$H/config.json"; rm -rf "$PROJ" "$T" "$FAKEHOME"' EXIT
cd "$PROJ"
git init -q . && git config user.email t@t && git config user.name t
pass=0; fail=0
check(){ # name expected_substring actual
  if grep -q -- "$2" <<<"$3"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1 -> ${3:0:200}"; fail=$((fail+1)); fi; }
printf '# FEATURES — test app — manifest v1\n- login\n' > FEATURES.md
printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n' > WORKING_RECORD.md

# --- transcripts
cat > "$T/ok.jsonl" <<J
{"type":"user","message":{"role":"user","content":"fix the bug"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/WORKING_RECORD.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nRegression table\n| Feature | Status |\n| login | kept |\n\nConfidence: Medium · Status: Validated — npm test 12/12"}]}}
J
cat > "$T/noline.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hello"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Here is the answer without a validation line."}]}}
J
cat > "$T/norecord.jsonl" <<J
{"type":"user","message":{"role":"user","content":"fix the bug"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Write","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Fixed.\n\nConfidence: High · Status: Checked"}]}}
J
cat > "$T/gov.jsonl" <<J
{"type":"user","message":{"role":"user","content":"update the rules"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/CLAUDE.md"}}]}}
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
# --- record-guard: only real repository changes count
cat > "$T/planfile.jsonl" <<J
{"type":"user","message":{"role":"user","content":"plan this"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Write","input":{"file_path":"/root/.claude/plans/plan-1.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Plan v1 — awaiting approval"}]}}
J
o=$(echo "{\"transcript_path\":\"$T/planfile.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard ignores files outside the repo" "^$" "$o"
cat > "$T/dispatch.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-worker"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"The worker could not run the command."}]}}
J
git add -A >/dev/null 2>&1; git commit -qm base >/dev/null 2>&1
o=$(echo "{\"transcript_path\":\"$T/dispatch.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard allows a worker turn that changed nothing" "^$" "$o"
mkdir -p js && echo "x" > js/app.js
o=$(echo "{\"transcript_path\":\"$T/dispatch.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard catches a worker turn that changed files" "record is incomplete" "$o"
rm -rf js
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
# --- Central content: manifest, session start, router
CENTRAL="$(cd "$H/.." && pwd)"
VER="$(head -1 "$CENTRAL/MANIFEST.txt" | sed 's/^version: *//')"
listed="$(tail -n +2 "$CENTRAL/MANIFEST.txt" | sort)"
actual="$(cd "$CENTRAL" && find . -type f ! -name MANIFEST.txt ! -path '*__pycache__*' | sed 's#^\./##' | sort)"
check "MANIFEST lists exactly the central files" "same" "$([ "$listed" = "$actual" ] && echo same || echo "differs: run tools/build_manifest.py")"
o=$(echo '{}' | python3 $H/session-start.py); check "session-start reports manifest version" "Rules v$VER loaded" "$o"
check "rules text injected" "My Environment" "$o"
check "worker instructions path given" "Worker instructions: .*opus-worker-instructions.md" "$o"
mv FEATURES.md F.bak
o=$(echo '{}' | python3 $H/session-start.py); check "missing per-repo file reported" "Missing per-repo files: FEATURES.md" "$o"
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record-guard points to seed templates" "seed" "$o"
mv F.bak FEATURES.md
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "router points to central skill file" "hz-guarantee-audit.*read .*skills/hz-guarantee-audit/SKILL.md" "$o"
check "router prefixes account skill" "anthropic-skills:hz-web-app-audit" "$o"
# --- Loader (only in the hz-claude-config checkout)
L="$CENTRAL/../stub/hz-loader.py"
if [ -f "$L" ]; then
  C="$T/cache"; U="file://$CENTRAL/"
  o=$(echo '{}' | HZ_CENTRAL_URL="$U" HZ_CACHE_DIR="$C" python3 "$L" session-start.py); check "loader fetches and injects rules" "Rules v$VER loaded" "$o"
  check "loader cached this version" "yes" "$([ -f "$C/$VER/.complete" ] && [ "$(cat "$C/current")" = "$VER" ] && echo yes)"
  o=$(echo '{"prompt":"- a\n- b\n- c"}' | HZ_CENTRAL_URL="$U" HZ_CACHE_DIR="$C" python3 "$L" plan-gate.py); check "loader runs later hooks from cache" "Full 'Plan vN" "$o"
  o=$(echo '{}' | HZ_CENTRAL_URL="file:///nonexistent/" HZ_CACHE_DIR="$C" python3 "$L" session-start.py); check "offline uses cached version" "offline: using cached v$VER" "$o"
  o=$(echo '{}' | HZ_CENTRAL_URL="file:///nonexistent/" HZ_CACHE_DIR="$T/empty" python3 "$L" session-start.py); check "offline with no cache says stop" "Central rules NOT loaded" "$o"
  o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\"}" | HZ_CACHE_DIR="$C" python3 "$L" validation-line.py); check "loader relays a Stop block" '"decision": "block"' "$o"
  o=$(echo '{}' | HZ_CACHE_DIR="$C" python3 "$L" ../../etc/passwd); check "loader refuses unsafe script names" "^$" "$o"
fi
# --- v3.1.3 regressions from the Weekly-Planner install
cat > "$T/arch.jsonl" <<J
{"type":"user","message":{"role":"user","content":"update the architecture doc"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/ARCHITECTURE.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Updated."}]}}
J
o=$(echo "{\"transcript_path\":\"$T/arch.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "ARCHITECTURE.md edits are exempt" "^$" "$o"
cat > "$T/shellrec.jsonl" <<J
{"type":"user","timestamp":"2000-01-01T00:00:00Z","message":{"role":"user","content":"fix it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"cat >> WORKING_RECORD.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\n| Feature | Status |\n| login | kept |"}]}}
J
touch -d '1999-01-01' WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/shellrec.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record not touched this turn still blocks" "update WORKING_RECORD.md" "$o"
touch WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/shellrec.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "record updated by a shell command counts" "^$" "$o"
rec "$NEWH" "$NEWS" '| Pocket money | 3 | 0 | 0 | 0 | x | **yes** 2026-09-20 |'
o=$(echo '{}' | python3 $H/session-start.py); check "bold **yes** counts as reviewed" "clean" "$(echo "$o" | grep -c 'has hit the redesign threshold' | sed 's/^0$/clean/')"
# --- v3.1.4: escaped pipes and malformed rows in the hotspot table
rec "$NEWH" "$NEWS" '| Sister Sync invites | 4 | 0 | 0 | 0 | `currentDayKey \|\| syncDayIdx` fallback | Yes 2026-09-24 (round 4 comparison) |'
o=$(echo '{}' | python3 $H/session-start.py); check "escaped pipe in a cell is not a column break" "clean" "$(echo "$o" | grep -c 'hotspot\]' | sed 's/^0$/clean/')"
rec "$NEWH" "$NEWS" '| Sister Sync invites | 4 | 0 | 0 | 0 | a || b broken cell | Yes 2026-09-24 |'
o=$(echo '{}' | python3 $H/session-start.py); check "malformed row is reported, not misread" "cells but the header has" "$o"
# --- v3.1.5: progress reports while workers run
cat > "$T/prog_nodispatch.jsonl" <<J
{"type":"user","message":{"role":"user","content":"status?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"In progress — not done.\nProgress: 1 of 3 done · Running: 1B, 1C"}]}}
J
cat > "$T/prog_earlier.jsonl" <<J
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-worker","run_in_background":true}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Dispatched."}]}}
{"type":"user","message":{"role":"user","content":"show me the status"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/css/app.css"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"In progress — not done. 1A committed.\nProgress: 1 of 3 done · Running: 1B, 1C"}]}}
J
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | python3 $H/validation-line.py); check "progress line accepted after a worker was dispatched" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/prog_nodispatch.jsonl\",\"stop_hook_active\":false}" | python3 $H/validation-line.py); check "progress line refused when no worker was dispatched" "only for reports while dispatched workers" "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | python3 $H/validation-line.py); check "missing line explains both report types" "progress report" "$o"
touch WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "progress turn needs no regression table" "^$" "$o"
touch -d '1999-01-01' WORKING_RECORD.md
python3 - "$T/prog_earlier.jsonl" <<'PY'
import sys; p=sys.argv[1]; l=open(p).read().replace('"content":"show me the status"}','"content":"show me the status"},"timestamp":"2000-01-01T00:00:00Z"',1); open(p,"w").write(l)
PY
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py); check "progress turn still needs the record update" "update WORKING_RECORD.md" "$o"
touch WORKING_RECORD.md
# --- UserPromptSubmit: skill router
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "skill-router matches guarantee-audit" "hz-guarantee-audit" "$o"
# --- PreToolUse: routing guard
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard observe mode allows" "^$" "$o"
sed -i 's/"observe"/"enforce"/' $H/config.json
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard enforce denies main-session source edit" '"deny"' "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/CLAUDE.md"}}' | python3 $H/routing-guard.py); check "routing-guard enforce allows governance edit" "^$" "$o"
sed -i 's/"enforce"/"observe"/' $H/config.json
echo; echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
