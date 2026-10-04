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
pn(){ # set the prompt counter the UserPromptSubmit hook would have written
  mkdir -p "$PROJ/.claude/state"; printf '{"session":"","n":%s}' "$1" > "$PROJ/.claude/state/prompt-number.json"; }
printf '# FEATURES — test app — manifest v1\n- login\n' > FEATURES.md
printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n' > WORKING_RECORD.md

# --- transcripts
cat > "$T/ok.jsonl" <<J
{"type":"user","message":{"role":"user","content":"fix the bug"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/WORKING_RECORD.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n\nRegression table\n| Feature | Status |\n| login | kept |\n\nConfidence: Medium · Status: Validated — npm test 12/12\n---\n> 📌 **Result:** login works again.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** I open the pull request."}]}}
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
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "validation-line passes good line" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "validation-line blocks missing line" '"decision": "block"' "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":true}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "validation-line no loop" "^$" "$o"
# --- Stop: record guard
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard passes complete turn" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard blocks missing record+table" "regression table" "$o"
o=$(echo "{\"transcript_path\":\"$T/gov.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard exempts governance edits" "^$" "$o"
printf '# FEATURES — <app or plan name> — manifest v1\n' > FEATURES.md
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard blocks on template manifest" "unfilled template" "$o"
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
o=$(echo "{\"transcript_path\":\"$T/planfile.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard ignores files outside the repo" "^$" "$o"
cat > "$T/dispatch.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-worker"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"The worker could not run the command."}]}}
J
git add -A >/dev/null 2>&1; git commit -qm base >/dev/null 2>&1
o=$(echo "{\"transcript_path\":\"$T/dispatch.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard allows a worker turn that changed nothing" "^$" "$o"
mkdir -p js && echo "x" > js/app.js
o=$(echo "{\"transcript_path\":\"$T/dispatch.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard catches a worker turn that changed files" "record is incomplete" "$o"
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
check "micro-plan names sonnet-worker" "Executor: sonnet-worker" "$o"
o=$(echo '{"prompt":"the sync layer keeps breaking"}' | python3 $H/plan-gate.py); check "design trigger names opus-worker" "Executor: opus-worker" "$o"
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
o=$(echo "{\"transcript_path\":\"$T/ok.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record-guard points to seed templates" "seed" "$o"
mv F.bak FEATURES.md
o=$(echo '{"prompt":"update the plan to v3"}' | python3 $H/skill-router.py); check "router points to central skill file" "hz-plan-regression-guard.*read .*skills/hz-plan-regression-guard/SKILL.md" "$o"
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "router prefixes account skill" "anthropic-skills:hz-reviewer" "$o"
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
o=$(echo "{\"transcript_path\":\"$T/arch.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "ARCHITECTURE.md edits are exempt" "^$" "$o"
cat > "$T/shellrec.jsonl" <<J
{"type":"user","timestamp":"2000-01-01T00:00:00Z","message":{"role":"user","content":"fix it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"cat >> WORKING_RECORD.md"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\n| Feature | Status |\n| login | kept |"}]}}
J
touch -d '1999-01-01' WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/shellrec.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record not touched this turn still blocks" "update WORKING_RECORD.md" "$o"
touch WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/shellrec.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "record updated by a shell command counts" "^$" "$o"
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
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"⏳ Working on: 1B, 1C · 1 of 3 done"}]}}
J
cat > "$T/prog_earlier.jsonl" <<J
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-worker","run_in_background":true}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Dispatched."}]}}
{"type":"user","message":{"role":"user","content":"show me the status"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/css/app.css"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"⏳ Working on: 1B, 1C · 1 of 3 done"}]}}
J
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "one-line status accepted while a dispatched worker runs" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/prog_nodispatch.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "status line refused when no worker was dispatched" "Working on" "$o"
o=$(echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }); check "missing line explains the status line and the final answer" "Working on" "$o"
touch WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "progress turn needs no regression table" "^$" "$o"
touch -d '1999-01-01' WORKING_RECORD.md
python3 - "$T/prog_earlier.jsonl" <<'PY'
import sys; p=sys.argv[1]; l=open(p).read().replace('"content":"show me the status"}','"content":"show me the status"},"timestamp":"2000-01-01T00:00:00Z"',1); open(p,"w").write(l)
PY
o=$(echo "{\"transcript_path\":\"$T/prog_earlier.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }); check "progress turn still needs the record update" "update WORKING_RECORD.md" "$o"
touch WORKING_RECORD.md
# --- v3.1.6: git-guard (no prompts; main protected)
gg(){ printf '%s' "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")}}" | python3 $H/git-guard.py; }
git checkout -q -B claude/topic 2>/dev/null
check "commit on a working branch passes" "^$" "$(gg 'git add -A && git commit -m x')"
check "push of the working branch passes" "^$" "$(gg 'git push -u origin claude/topic')"
check "plain push from a working branch passes" "^$" "$(gg 'git push')"
check "push to main is blocked" '"deny"' "$(gg 'git push origin claude/topic:main')"
check "push HEAD:refs/heads/main is blocked" '"deny"' "$(gg 'git push origin HEAD:refs/heads/main')"
check "push --all is blocked" '"deny"' "$(gg 'git push --all origin')"
git checkout -q -B main 2>/dev/null
check "commit on main is blocked" '"deny"' "$(gg 'git commit -m x')"
check "plain push from main is blocked" '"deny"' "$(gg 'git push')"
check "non-git command passes" "^$" "$(gg 'npm test')"
check "draft pull request is blocked" '"deny"' "$(gg 'gh pr create --draft --title x --body y')"
check "draft pull request -d is blocked" '"deny"' "$(gg 'git push -u origin claude/topic && gh pr create -d -t x -b y')"
check "ready pull request passes" "^$" "$(gg 'gh pr create --title x --body y')"
check "gh pr ready passes" "^$" "$(gg 'gh pr ready 12')"
check "stub allows branch commit/push and pr create" "6" "$(python3 -c "import json;a=json.load(open('$H/../../stub/settings.json'))['permissions']['allow'];print(sum(1 for r in ['Bash(git status:*)','Bash(git add:*)','Bash(git commit:*)','Bash(git push:*)','Bash(gh pr create:*)','Bash(gh pr ready:*)'] if r in a))")"
# --- v3.1.14: draft pull requests through the GitHub tool
ggt(){ printf '%s' "{\"tool_name\":\"$1\",\"tool_input\":$2}" | python3 $H/git-guard.py; }
check "GitHub tool draft pull request is blocked" '"deny"' "$(ggt mcp__github__create_pull_request '{"title":"x","draft":true}')"
check "the block says to create it ready for review" "ready for review" "$(ggt mcp__github__create_pull_request '{"title":"x","draft":true}')"
check "GitHub tool ready pull request passes" "^$" "$(ggt mcp__github__create_pull_request '{"title":"x","draft":false}')"
check "GitHub tool without a draft field passes" "^$" "$(ggt mcp__github__create_pull_request '{"title":"x"}')"
check "marking an open pull request draft is blocked" '"deny"' "$(ggt mcp__github__update_pull_request '{"pullNumber":1,"draft":true}')"
check "other GitHub tools pass" "^$" "$(ggt mcp__github__list_pull_requests '{"state":"open"}')"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"mcp__github__create_pull_request","tool_input":{"draft":true}}' | python3 $H/dispatch.py); check "switchboard routes the GitHub pull-request tool to git-guard" '"deny"' "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"mcp__github__search_code","tool_input":{}}' | python3 $H/dispatch.py); check "switchboard skips other GitHub tools" "^$" "$o"
check "stub matcher covers the GitHub tools" "yes" "$(python3 -c "import json;h=json.load(open('$H/../../stub/settings.json'))['hooks']['PreToolUse'];print('yes' if any('mcp__' in g.get('matcher','') for g in h) else 'no')")"
git checkout -q -B claude/topic 2>/dev/null
# --- v3.1.6: explicit "skip the plan"
o=$(echo '{"prompt":"Skip the plan and run it directly. I explicitly allow running this specific script: curl -fsSL https://example/install-stub.sh | bash. Run it from the repository root and show me the full output."}' | python3 $H/plan-gate.py)
check "skip phrase: no plan requested" "asked to skip the plan" "$o"
check "skip phrase: no micro-plan tier" "clean" "$(echo "$o" | grep -c 'Micro-plan tier' | sed 's/^0$/clean/')"
o=$(echo '{"prompt":"- a\n- b\n- c without skipping anything"}' | python3 $H/plan-gate.py); check "no skip phrase: full plan still required" "Full 'Plan vN" "$o"
# --- v3.1.8: completion guard (auto-fix), planner suggestion, pause
# v3.1.14: only rows added or changed on this branch count. The base record (one earlier round's row) goes on
# origin/main; everything added afterwards is this branch's work.
ledger(){ printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n| earlier round | NOT STARTED | |\n%b' "$1" > WORKING_RECORD.md; }
ledger ''
git add -A >/dev/null 2>&1; git commit -qm ledger-base >/dev/null 2>&1
git update-ref refs/remotes/origin/main HEAD
ledger '| login | COMPLETE | npm test 12/12 |\n| export | NOT STARTED | |\n| sync | BLOCKED — API key missing | |\n'
rm -f .claude/state/completion-rounds.json .claude/state/completion-pause
cat > "$T/done_claim.jsonl" <<J
{"type":"user","uuid":"u1","message":{"role":"user","content":"finish the plan"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"All done.\n\nConfidence: High · Status: Validated — npm test"}]}}
J
cg(){ echo "{\"transcript_path\":\"$1\",\"stop_hook_active\":$2}" | python3 $H/completion-guard.py; }
o=$(cg "$T/done_claim.jsonl" false); check "completion: done claim with open item is blocked" "only send-back for this request" "$o"
check "completion: block names the open item" "export" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: no second send-back on the same request" "^$" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: never loops past the cap" "^$" "$o"
rm -f .claude/state/completion-rounds.json
# --- v3.1.14: rounds are counted per user prompt, so the hook's own feedback cannot reset them.
# v3.1.16: one send-back per request; the session's answers after it are never blocked again.
echo '{"prompt":"finish the plan"}' | python3 $H/plan-gate.py >/dev/null
cp "$T/done_claim.jsonl" "$T/loop.jsonl"
feedback(){ # a Stop-hook block reaches the transcript as another user record, then the session answers again
  cat >> "$T/loop.jsonl" <<J
{"type":"user","uuid":"fb$1","message":{"role":"user","content":"Not done: continue with 'export' now."}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"All done.\n\nConfidence: High · Status: Validated — npm test"}]}}
J
}
o=$(cg "$T/loop.jsonl" false); check "loop: one send-back" "only send-back" "$o"
feedback 1; o=$(cg "$T/loop.jsonl" true); check "loop: feedback does not reset the counter" "^$" "$o"
feedback 2; o=$(cg "$T/loop.jsonl" true); check "loop: still quiet" "^$" "$o"
rm -f .claude/state/completion-rounds.json
# scope: rows that are identical on origin/main belong to earlier rounds
o=$(cg "$T/done_claim.jsonl" false); check "completion: only this branch's rows are counted" "Completion: 1 of 3 done (33%)" "$o"
check "completion: an earlier round's row is not listed" "clean" "$(echo "$o" | grep -c 'earlier round' | sed 's/^0$/clean/')"
check "completion: open items are listed one per line, names only" '\\n- export' "$o"
rm -f .claude/state/completion-rounds.json
git update-ref -d refs/remotes/origin/main
o=$(cg "$T/done_claim.jsonl" false); check "completion: unreadable base shows the line but never blocks" "Completion: 1 of 4 done (25%)" "$o"
check "completion: unreadable base does not block on open items" "clean" "$(echo "$o" | grep -c 'Not done' | sed 's/^0$/clean/')"
git update-ref refs/remotes/origin/main "$(git rev-parse HEAD)"
rm -f .claude/state/completion-rounds.json
cat > "$T/qa.jsonl" <<J
{"type":"user","uuid":"u2","message":{"role":"user","content":"what is the ledger state?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Two items open.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(cg "$T/qa.jsonl" false); check "completion: question turn passes untouched" "^$" "$o"
cat > "$T/plan.jsonl" <<J
{"type":"user","uuid":"u3","message":{"role":"user","content":"plan it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Plan v1 — Awaiting approval\n\nConfidence: High · Status: Proposed"}]}}
J
o=$(cg "$T/plan.jsonl" false); check "completion: plan awaiting approval passes" "^$" "$o"
o=$(echo '{"prompt":"stop here for today"}' | python3 $H/plan-gate.py); check "pause phrase acknowledged" "Pause acknowledged" "$o"
o=$(cg "$T/done_claim.jsonl" false); check "completion: pause lets one final report stand" "^$" "$o"
o=$(cg "$T/done_claim.jsonl" false); check "completion: pause is single-use" "only send-back" "$o"
rm -f .claude/state/completion-rounds.json
printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n| login | COMPLETE | npm test 12/12 |\n| export | COMPLETE | |\n' > WORKING_RECORD.md
o=$(cg "$T/done_claim.jsonl" false); check "completion: all complete still needs the Completion line" "Completion: 2 of 2 done (100%)" "$o"
cat > "$T/done_line.jsonl" <<J
{"type":"user","uuid":"u4","message":{"role":"user","content":"finish the plan"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nCompletion: 1 of 2 done (50%)\n\nConfidence: High · Status: Validated — npm test"}]}}
J
rm -f .claude/state/completion-rounds.json
o=$(cg "$T/done_line.jsonl" false); check "completion: wrong count is corrected" "does not match" "$o"
cat > "$T/done_ok.jsonl" <<J
{"type":"user","uuid":"u5","message":{"role":"user","content":"finish the plan"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nCompletion: 2 of 2 done (100%)\n\nConfidence: High · Status: Validated — npm test"}]}}
J
rm -f .claude/state/completion-rounds.json
o=$(cg "$T/done_ok.jsonl" false); check "completion: COMPLETE without evidence is caught" "without evidence" "$o"
sed -i 's/| export | COMPLETE | |/| export | COMPLETE | manual check |/' WORKING_RECORD.md
o=$(cg "$T/done_ok.jsonl" false); check "completion: correct line with evidence passes" "^$" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "session-start: no completion line when nothing open" "clean" "$(echo "$o" | grep -c '\[completion\]' | sed 's/^0$/clean/')"
printf '| again | NOT STARTED | |\n' >> WORKING_RECORD.md
o=$(echo '{}' | python3 $H/session-start.py); check "session-start: completion line when items open" "Completion: 2 of 3 done (67%)" "$o"
# v3.1.14: at most five open items are listed, the rest are counted
for i in 1 2 3 4 5 6; do printf '| open-%s | NOT STARTED | |\n' "$i" >> WORKING_RECORD.md; done
o=$(echo '{}' | python3 $H/session-start.py); check "long open list is cut after five names" "+2 more open in the record" "$o"
check "the sixth open name is not listed" "clean" "$(echo "$o" | grep -c 'open-6' | sed 's/^0$/clean/')"
python3 - <<'PY'
import re
p = "WORKING_RECORD.md"
open(p, "w").write(re.sub(r"(?m)^\| open-\d.*\n", "", open(p).read()))
PY
o=$(echo '{"prompt":"why does the sync layer keep breaking across all apps? find the root cause and redesign it"}' | python3 $H/plan-gate.py); check "planner: fable suggested on strong signals" "Suggest /model fable" "$o"
o=$(echo '{"prompt":"- add a button\n- fix colour\n- change the label"}' | python3 $H/plan-gate.py); check "planner: session model plans by default" "The session's model plans (account default: Opus 5.5)" "$o"
o=$(echo '{"prompt":"- rename the label"}' | python3 $H/plan-gate.py); check "planner: silent on micro tier" "clean" "$(echo "$o" | grep -c '\[planner\]' | sed 's/^0$/clean/')"
rm -f .claude/state/completion-rounds.json
# --- v3.1.11: first-line version, plain top, stub check, pointer refresh
vl(){ echo "{\"transcript_path\":\"$1\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; }; }
cat > "$T/first_noversion.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install the stub"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I'll start by reading the current state."}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** installed.\n> 👉 **I need from you:** merge the pull request.\n> ➡️ **Next:** health check."}]}}
J
pn 1
o=$(vl "$T/first_noversion.jsonl"); check "the first reply no longer needs a version line" "clean" "$(echo "$o" | grep -c "Rules v" | sed 's/^0$/clean/')"
# v3.1.14: the first-reply check follows the prompt number, so Stop-hook feedback (another user record in the
# transcript) does not turn the same prompt into a later reply
cat > "$T/first_feedback.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install the stub"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n---\n> 📌 **Result:** installed.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** health check."}]}}
{"type":"user","message":{"role":"user","content":"This reply is missing its closing line."}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Confidence: High · Status: Checked\n---\n> 📌 **Result:** installed.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** health check."}]}}
J
o=$(vl "$T/first_feedback.jsonl"); check "feedback no longer triggers a version-line send-back" "clean" "$(echo "$o" | grep -c "very first line" | sed 's/^0$/clean/')"
pn 2
cat > "$T/second_notop.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** ready.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** waiting."}]}}
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"The hook now checks X in file y.py.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/second_notop.jsonl"); check "final answer without the quote top is sent back" "quote block of three lines" "$o"
check "later replies need no version line" "clean" "$(echo "$o" | grep -c 'first reply of the session' | sed 's/^0$/clean/')"
cat > "$T/second_top.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n\nConfidence: High · Status: Checked\n---\nResult: ready.\nI need from you: nothing.\nNext: waiting."}]}}
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Details: hook y.py.\n\nConfidence: High · Status: Checked\n---\n📌 Result: the check now runs at every start.\n👉 I need from you: nothing\n> ➡️ **Next:** nothing to do."}]}}
J
o=$(vl "$T/second_top.jsonl"); check "quote top accepted with or without the quote marker and bold" "^$" "$o"
# v3.1.14: the icons are part of the labels
cat > "$T/second_noicons.jsonl" <<J
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Confidence: High · Status: Checked\n---\n> **Result:** the check now runs.\n> **I need from you:** nothing\n> **Next:** nothing to do."}]}}
J
o=$(vl "$T/second_noicons.jsonl"); check "labels without icons are sent back" "quote block of three lines" "$o"
cat > "$T/second_plainarrow.jsonl" <<J
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Confidence: High · Status: Checked\n---\n> 📌 **Result:** the check now runs.\n> 👉 **I need from you:** nothing\n> ➡ **Next:** nothing to do."}]}}
J
o=$(vl "$T/second_plainarrow.jsonl"); check "arrow without the invisible character is accepted" "^$" "$o"
o=$(vl "$T/prog_earlier.jsonl"); check "progress report needs no plain top" "^$" "$o"
# stub check
o=$(echo '{}' | python3 $H/session-start.py); check "stub outdated is reported in plain words" "OUTDATED" "$o"
check "stub report names the missing pieces" "Sonnet worker" "$o"
S="$T/stubrepo"; rm -rf "$S"; mkdir -p "$S/.claude/agents"
cp "$H/../../stub/settings.json" "$S/.claude/settings.json"
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$S/.claude/agents/"
cp "$H/../../stub/CLAUDE-pointer.md" "$S/CLAUDE.md"; cp "$H/../../stub/hz-loader.py" "$S/.claude/"
o2=$(cd "$H" && python3 -c "
import sys; sys.path.insert(0,'.')
from _common import load_config; from stubcheck import stub_status
print(stub_status(load_config(), '$S'))")
check "current stub is reported current" "^current" "$o2"
# v3.1.14: a stub whose PreToolUse matcher does not cover the GitHub tools is outdated
python3 - "$S/.claude/settings.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p))
for g in s["hooks"]["PreToolUse"]:
    g["matcher"] = g.get("matcher", "").replace("|mcp__.*", "")
json.dump(s, open(p, "w"))
PY
o2=$(cd "$H" && python3 -c "
import sys; sys.path.insert(0,'.')
from _common import load_config; from stubcheck import stub_status
print(stub_status(load_config(), '$S'))")
check "old matcher makes the stub OUTDATED" "OUTDATED" "$o2"
check "the stub report names the GitHub tool check" "GitHub tool check before a pull request" "$o2"
# --- v3.1.14: the stub sets no session model; the workers are pinned
stub_says(){ (cd "$H" && python3 -c "
import sys; sys.path.insert(0,'.')
from _common import load_config; from stubcheck import stub_status
print(stub_status(load_config(), '$1'))"); }
check "the stub sets no model key" "yes" "$(python3 -c "import json;print('no' if 'model' in json.load(open('$H/../../stub/settings.json')) else 'yes')")"
check "opus-worker is pinned to Opus 5.5" "yes" "$(grep -qx 'model: claude-opus-5-5' "$H/../../stub/opus-worker.md" && echo yes)"
check "sonnet-worker is pinned to the exact Sonnet 5.5 ID" "yes" "$(grep -qx 'model: claude-sonnet-5-5' "$H/../../stub/sonnet-worker.md" && echo yes)"
M="$T/modelrepo"; rm -rf "$M"; mkdir -p "$M/.claude/agents"
cp "$H/../../stub/settings.json" "$M/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$M/.claude/agents/"
cp "$H/../../stub/CLAUDE-pointer.md" "$M/CLAUDE.md"; cp "$H/../../stub/hz-loader.py" "$M/.claude/"
check "a stub with the new model setup is current" "^current" "$(stub_says "$M")"
python3 -c "
import json; p='$M/.claude/settings.json'; s=json.load(open(p)); s['model']='opus'; json.dump(s, open(p,'w'))"
o2=$(stub_says "$M"); check "a stub that still sets a model is OUTDATED" "account default model" "$o2"
python3 -c "
import json; p='$M/.claude/settings.json'; s=json.load(open(p)); s.pop('model'); json.dump(s, open(p,'w'))"
sed -i 's/^model: claude-sonnet-5-5$/model: sonnet/' "$M/.claude/agents/sonnet-worker.md"
o2=$(stub_says "$M"); check "a sonnet-worker on the alias is OUTDATED" "pinned to Sonnet 5.5" "$o2"
# installer: a model the old stub set is removed, another value is kept
for v in opus fable claude-opus-5-5; do
  printf '{"model":"%s","permissions":{"allow":["Bash(ls:*)"]}}' "$v" > "$T/target.json"
  python3 "$H/../../stub/merge_settings.py" "$H/../../stub/settings.json" "$T/target.json" "hz-loader.py"
  got=$(python3 -c "import json;print(json.load(open('$T/target.json')).get('model','none'))")
  case "$v" in
    claude-opus-5-5) check "installer keeps a model I chose myself" "claude-opus-5-5" "$got";;
    *) check "installer removes the stub-set model '$v'" "none" "$got";;
  esac
  check "installer keeps the repo's own permissions ($v)" "Bash(ls:\*)" "$(cat "$T/target.json")"
done
# pointer refresh keeps other sections
P="$T/ptr"; rm -rf "$P"; mkdir -p "$P"
printf '# Repository rules\n\nold pointer text hz-loader.py\n\nRepository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.\n\n## Project Architecture\nkeep me\n' > "$P/CLAUDE.md"
sed -n '/^  res="\$(python3 - CLAUDE.md/,/^PYPTR$/p' "$H/../../stub/install-stub.sh" | sed '1d;$d' > "$T/ptr.py"
( cd "$P" && python3 "$T/ptr.py" CLAUDE.md "$H/../../stub/CLAUDE-pointer.md" ) > "$T/ptr.out"
check "installer refreshes an existing pointer" "updated" "$(cat "$T/ptr.out")"
check "pointer refresh keeps the repo's own section" "keep me" "$(cat "$P/CLAUDE.md")"
check "refreshed pointer has the multi-repo fallback" "hooks inactive" "$(cat "$P/CLAUDE.md")"
# --- v3.1.12: central switchboard
dp(){ rm -f "$PROJ/.claude/state/format-rounds.json" "$PROJ/.claude/state/record-rounds.json"; python3 $H/dispatch.py; }
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | dp); check "switchboard passes on a git-guard deny" '"deny"' "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"npm test"}}' | dp); check "switchboard quiet on a harmless command" "^$" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"x"}}' | dp); check "switchboard skips checks for other tools" "^$" "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | dp); check "switchboard passes on a Stop block" '"decision": "block"' "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"transcript_path\":\"$T/second_top.jsonl\",\"stop_hook_active\":false}" | dp); check "switchboard sends nothing back when every Stop check passes (only the version notice)" "clean" "$(echo "$o" | grep -c decision | sed 's/^0$/clean/')"
o=$(echo '{"hook_event_name":"UserPromptSubmit","prompt":"the sync layer keeps breaking"}' | dp); check "switchboard joins prompt contexts" "Executor: opus-worker" "$o"
check "switchboard answers once for the prompt event" "1" "$(echo "$o" | grep -c hookSpecificOutput)"
o=$(echo '{"hook_event_name":"SubagentStop"}' | dp); check "switchboard quiet on an event with no checks" "^$" "$o"
check "stub hands every forwarded event to the switchboard" "3" "$(python3 -c "import json;h=json.load(open('$H/../../stub/settings.json'))['hooks'];print(sum(1 for e in ('UserPromptSubmit','PreToolUse','Stop') if 'dispatch.py' in json.dumps(h.get(e,[]))))")"
# --- v3.1.15: UTF-8 whatever the PC language; Stop checks together; per-prompt cap; separated top block
G="$T/gbkrepo"; rm -rf "$G"; mkdir -p "$G"; SHIM="$T/gbkshim"; mkdir -p "$SHIM"
cat > "$SHIM/sitecustomize.py" <<'PYS'
import subprocess
_run = subprocess.run
def run(*a, **k):
    if (k.get("text") or k.get("universal_newlines")) and not k.get("encoding"):
        k["encoding"] = "gbk"            # what a Chinese-Windows default does to calls without an explicit encoding
    return _run(*a, **k)
subprocess.run = run
PYS
( cd "$G" && git init -q . && git config user.email t@t && git config user.name t \
  && printf '# WR\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n| old round — done · ok | COMPLETE | npm test — 12/12 · fine |\n| old open item — later | NOT STARTED | |\n' > WORKING_RECORD.md \
  && git add -A && git commit -qm base && git update-ref refs/remotes/origin/main HEAD \
  && printf '| new item — this branch | NOT STARTED | |\n' >> WORKING_RECORD.md )
gb(){ ( cd "$H" && CLAUDE_PROJECT_DIR="$G" PYTHONPATH="$SHIM" python3 -c "$1" 2>&1 ); }
o=$(gb "
import subprocess
try:
    r = subprocess.run(['git','show','origin/main:WORKING_RECORD.md'],cwd='$G',capture_output=True,text=True)
    print('decoded' if r.stdout else 'broken')
except UnicodeError:
    print('broken')")
check "gbk shim reproduces the Weekly-Planner failure for calls without an encoding" "broken" "$o"
o=$(gb "import sys;sys.path.insert(0,'.');from _common import load_config,completion_summary;c=completion_summary(load_config());print(c['scoped'],c['total'],c['open'])")
check "under gbk the completion count is still scoped to this branch" "True 1 \['new item — this branch'\]" "$o"
o=$(cd "$H" && printf '{"prompt":"über — straße · 你好"}' | CLAUDE_PROJECT_DIR="$G" PYTHONIOENCODING=gbk python3 -c "import sys;sys.path.insert(0,'.');from _common import read_hook_input;p=read_hook_input().get('prompt','');print('intact' if p.endswith('你好') and 'straße' in p else 'lost')" 2>&1)
check "hook input with Chinese text survives a gbk console" "intact" "$o"
check "installer smoke test reads UTF-8" "PYTHONIOENCODING=utf-8" "$(cat "$H/../../stub/install-stub.sh")"
# Stop checks together
o=$(echo "{\"hook_event_name\":\"Stop\",\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":false}" | dp)
check "switchboard sends all Stop reasons in one message" "Fix all of these in one reply" "$o"
check "joined message carries the record reason" "record is incomplete" "$o"
check "joined message carries the format reason" "quote block" "$o"
# per-prompt cap for the format check, not stop_hook_active
rm -f "$PROJ/.claude/state/format-rounds.json"
echo '{"prompt":"- one small thing","session_id":"cap1"}' | python3 $H/plan-gate.py >/dev/null
vc(){ echo "{\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":true,\"session_id\":\"cap1\"}" | python3 $H/validation-line.py; }
o=$(vc); check "format check sends back even after another check blocked (round 1)" '"decision": "block"' "$o"
o=$(vc); check "format check goes quiet after its one send-back on this prompt" "^$" "$o"
echo '{"prompt":"- another thing","session_id":"cap1"}' | python3 $H/plan-gate.py >/dev/null
o=$(vc); check "a new prompt gets its own rounds" '"decision": "block"' "$o"
check "send-back asks for only the missing lines" "do not repeat the rest" "$o"
rm -f "$PROJ/.claude/state/format-rounds.json" "$PROJ/.claude/state/prompt.json"
# separated top block
cat > "$T/longneed.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.15 · main\n\nConfidence: High · Status: Proposed\n---\n> 📌 **Result:** Plan ready.\n> 👉 **I need from you:** Say approved or tell me what to change, and note that two points need your OK: item 4 wording is already gone so I will put it where it sits now, and I add one encoding fix.\n> ➡️ **Next:** I build it."}]}}
J
o=$(vl "$T/longneed.jsonl"); check "request line longer than 30 words is sent back" "at most 30 words" "$o"
cat > "$T/shortneed.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.15 · main\n❓ Decisions\n1. Extra stdin fix — recommend yes.\n\nConfidence: High · Status: Proposed\n---\n> 📌 **Result:** Plan ready.\n> 👉 **I need from you:** Approve Plan v1, or name what to change.\n> ➡️ **Next:** I build it."}]}}
J
o=$(vl "$T/shortneed.jsonl"); check "one short request with a Decisions list passes" "^$" "$o"
cat > "$T/statusplus.jsonl" <<J
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Agent","input":{"subagent_type":"opus-worker"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Finished: record updated.\n⏳ Working on: opus-worker · 0 of 7 done"}]}}
J
o=$(vl "$T/statusplus.jsonl"); check "a multi-line progress report is no longer accepted" '"decision": "block"' "$o"
# --- v3.1.16: advisor off, idle hooks gone, installer cleans both out of an existing repository
M="$T/mergetest"; rm -rf "$M"; mkdir -p "$M"
printf '{"advisorModel":"fable","model":"opus","hooks":{"PostToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"x hz-loader.py dispatch.py"}]}],"SubagentStop":[{"hooks":[{"type":"command","command":"x hz-loader.py dispatch.py"}]}]}}' > "$M/old.json"
python3 "$H/../../stub/merge_settings.py" "$H/../../stub/settings.json" "$M/old.json" "hz-loader.py"
o=$(python3 -c "import json;s=json.load(open('$M/old.json'));print('advisor' if 'advisorModel' in s else 'no-advisor', 'model' if 'model' in s else 'no-model', sorted(s['hooks']))")
check "installer removes the old Fable advisor" "no-advisor" "$o"
check "installer removes the idle hook events" "\['PreToolUse', 'SessionStart', 'Stop', 'UserPromptSubmit'\]" "$o"
printf '{"advisorModel":"opus"}' > "$M/own.json"; python3 "$H/../../stub/merge_settings.py" "$H/../../stub/settings.json" "$M/own.json" "hz-loader.py"
check "installer keeps an advisor the repository chose itself" "opus" "$(cat "$M/own.json")"
S2="$T/stubadv"; rm -rf "$S2"; mkdir -p "$S2/.claude/agents"
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$S2/.claude/agents/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S2/CLAUDE.md"
python3 -c "import json;s=json.load(open('$H/../../stub/settings.json'));s['advisorModel']='fable';json.dump(s,open('$S2/.claude/settings.json','w'))"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S2'))")
check "a repository still on the Fable advisor shows OUTDATED" "OUTDATED.*advisor off" "$o"
# --- v3.1.17: the record check shows the exact table shape, so the first report is right and nothing is repeated
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; })
check "record check shows the four-row table shape" "Intentionally removed" "$o"
# --- v3.1.18: plan check at Approve, foreground workers, "waiting on you" stages, Opus helper pinned
pg(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','tool_input':{'plan':open(sys.argv[1],encoding='utf-8').read()}}))" "$1" | python3 $H/dispatch.py; }
cat > "$T/plan_good.md" <<'P'
# Plan v2 — Four new lessons — Awaiting approval
| Summary |
|---|
| This plan opens the four new lessons for the girls after the same check as before. |
| Changed from v1: the new lessons are included too, because you asked for it. |
| You need to approve this plan and later merge the changes. |
Changes in this version
```diff
+ 🟩 Rev 2: the four new lessons also open for the pilot
```
🟩 **Rev 2** The four new lessons also open for the pilot, after the same check.
Stages to finish
4 stages: 2 by Claude, 2 by you.
1. Build the lessons · Claude · Build
2. Run the checks · Claude · Build
3. Merge the changes · You · Check
4. Try it on the iPad · You · Check
Technical details: branch below-grade-lessons, commit d00f47f.
P
o=$(pg "$T/plan_good.md"); check "a plan with summary, squares and stages passes the Approve check" "^$" "$o"
sed 's/ · Build$//; s/ · Check$//' "$T/plan_good.md" > "$T/plan_nophase.md"
o=$(pg "$T/plan_nophase.md"); check "v3.1.24: stages without Build or Check are sent back" "3 stage(s) have neither" "$o"
mkdir -p "$PROJ/plans"; cp "$T/plan_nophase.md" "$PROJ/plans/zz-latest.md"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"ExitPlanMode","tool_input":{}}' | python3 $H/dispatch.py)
check "v3.1.24: with no plan text in the call, the plan file in the repository's plans/ is checked" "have neither" "$o"
rm -rf "$PROJ/plans"
o=$(echo "{\"transcript_path\":\"$T/shortneed.jsonl\",\"session_id\":\"sg2\",\"stop_hook_active\":false}" | python3 $H/setup-guard.py); check "no setup note pending: nothing to do" "^$" "$o"
sed 's/🟩 \*\*Rev 2\*\*/<span style="color:green">Rev 2:<\/span>/' "$T/plan_good.md" > "$T/plan_html.md"
o=$(pg "$T/plan_html.md"); check "colour code in a plan is sent back" "colour code" "$o"
check "a Rev label without its square is sent back too" "Missing on: Rev 2" "$o"
grep -v '^| Summary' "$T/plan_good.md" > "$T/plan_nosum.md"
o=$(pg "$T/plan_nosum.md"); check "a plan without the everyday Summary is sent back" "Summary" "$o"
grep -v 'Stages to finish' "$T/plan_good.md" > "$T/plan_nostages.md"
o=$(pg "$T/plan_nostages.md"); check "a plan without Stages to finish is sent back" "Stages to finish" "$o"
sed 's/🟩 \*\*Rev 2\*\*/🟦 **Rev 2**/' "$T/plan_good.md" > "$T/plan_wrongsq.md"
o=$(pg "$T/plan_wrongsq.md"); check "the wrong square for the round is sent back" "Missing on: Rev 2" "$o"
o=$(python3 -c "import json;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','tool_input':{'planFilePath':'$T/plan_html.md'}}))" | python3 $H/dispatch.py)
check "the plan check also reads a plan named by its file" "colour code" "$o"
# foreground workers
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"opus-worker","prompt":"Task: a\nLevel: Complex","run_in_background":true}}' | python3 $H/dispatch.py)
check "a worker started in the background is refused" "foreground" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"opus-worker","prompt":"Task: Fix sync\nLevel: Complex\nfind why"}}' | python3 $H/dispatch.py)
check "a foreground worker with task and level passes" "^$" "$o"
# --- v3.1.19: hard hand-over rules
wg(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'Agent','session_id':'wg1','tool_input':{'subagent_type':sys.argv[1],'prompt':sys.argv[2]}}))" "$1" "$2" | python3 $H/dispatch.py; }
rm -f "$PROJ/.claude/state/sonnet-tries.json"
o=$(wg general-purpose $'Task: Button\nLevel: Routine\nchange label'); check "a general helper may not do work" "Only opus-worker or sonnet-worker" "$o"
o=$(wg Explore 'look around the code'); check "a read-only look-around helper may run" "^$" "$o"
o=$(wg sonnet-worker 'change the button label'); check "a hand-over without Task and Level is refused" "Task: <the stage name" "$o"
o=$(wg opus-worker $'Task: Button label\nLevel: Routine\nchange the label'); check "Routine work may not go to Opus" "goes to sonnet-worker" "$o"
o=$(wg opus-worker $'Escalated from sonnet-worker: label logic is shared\nTask: Button label\nLevel: Routine'); check "an escalated Routine task may go to Opus" "^$" "$o"
o=$(wg sonnet-worker $'Task: Sync fix\nLevel: Complex\nfix it'); check "Complex work may not go to Sonnet" "goes to opus-worker, never" "$o"
o=$(wg sonnet-worker $'Task: Badge\nLevel: Routine\nalso update the firestore data model'); check "Sonnet may not get a hand-over that mentions complex work" "mentions complex work" "$o"
o=$(wg sonnet-worker $'Task: Badge text\nLevel: Routine\nchange the wording'); check "Sonnet try 1" "^$" "$o"
o=$(wg sonnet-worker $'Task: Badge text\nLevel: Routine\nchange the wording'); check "Sonnet try 2" "^$" "$o"
o=$(wg sonnet-worker $'Task: Badge text\nLevel: Routine\nchange the wording'); check "a third Sonnet try goes to Opus" "two tries did not finish it" "$o"
rm -f "$PROJ/.claude/state/sonnet-tries.json"
o=$(echo '{"tool_name":"Edit","session_id":"s1","agent_id":"a9","agent_type":"sonnet-worker","tool_input":{"file_path":"firestore.rules"}}' | python3 $H/routing-guard.py)
check "Sonnet may not change shared data rules" "Escalate to opus-worker" "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","agent_id":"a9","agent_type":"sonnet-worker","tool_input":{"file_path":"js/badges.js"}}' | python3 $H/routing-guard.py)
check "Sonnet may change ordinary app files" "^$" "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","agent_id":"a8","agent_type":"opus-worker","tool_input":{"file_path":"firestore.rules"}}' | python3 $H/routing-guard.py)
check "Opus may change shared data rules" "^$" "$o"
# waiting-on-you stages: counted, shown, never auto-fixed
W="$T/waitrepo"; rm -rf "$W"; mkdir -p "$W"
( cd "$W" && git init -q . && git config user.email t@t && git config user.name t \
  && printf '# WR\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n' > WORKING_RECORD.md && git add -A && git commit -qm base \
  && git update-ref refs/remotes/origin/main HEAD \
  && printf '| Build the lessons | COMPLETE | tests 12/12 |\n| Merge the changes | WAITING ON YOU — merge PR 32 |  |\n' >> WORKING_RECORD.md )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$W" python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config,completion_summary;c=completion_summary(load_config());print(c['display']);print('open=',c['open'])")
check "a stage of mine is counted in the total" "Completion: 1 of 2 done (50%) · Waiting on you: 1" "$o"
check "a stage of mine is listed by name" "Waiting on you: Merge the changes" "$o"
check "a stage of mine is not treated as the session's open work" "open= \[\]" "$o"
# the stub expects the pinned Opus helper and the plan check
S3="$T/stub18"; rm -rf "$S3"; mkdir -p "$S3/.claude/agents"
cp "$H/../../stub/settings.json" "$S3/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$S3/.claude/agents/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S3/CLAUDE.md"; cp "$H/../../stub/hz-loader.py" "$S3/.claude/"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "the new stub reads current" "^current" "$o"
sed -i 's/^model: claude-opus-5-5$/model: inherit/' "$S3/.claude/agents/opus-worker.md"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "an unpinned Opus helper shows OUTDATED" "OUTDATED.*Opus helper pinned" "$o"
# --- v3.1.20: app repositories update their own setup files
for n in settings.json opus-worker.md sonnet-worker.md hz-loader.py CLAUDE-pointer.md merge_settings.py v2-known-files.txt; do
  cmp -s "$H/../../stub/$n" "$H/../stub-files/$n" || echo "stub-files out of step: $n"
done > "$T/stubsync.txt"
check "the central copies of the setup files match stub/" "^$" "$(cat "$T/stubsync.txt")"
SV=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;print(load_config()['stub_expect']['version'])")
U="$T/selfupd"; rm -rf "$U" "$T/selfupd.git"; mkdir -p "$U/.claude/agents"; git init -q --bare "$T/selfupd.git"
( cd "$U" && git init -q -b main . && git config user.email t@t && git config user.name t \
  && printf '# Repository rules\n\nold pointer hz-loader.py\n\nRepository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.\n\n## Project Architecture\nkeep me\n' > CLAUDE.md \
  && python3 -c "import json;s=json.load(open('$H/../../stub/settings.json'));s['permissions']['allow'].append('Bash(npm test)');[g.__setitem__('matcher',g['matcher'].replace('ExitPlanMode|','')) for g in s['hooks']['PreToolUse']];json.dump(s,open('.claude/settings.json','w'),indent=2)" \
  && sed 's/^model: claude-opus-5-5$/model: inherit/; s/Always runs on Opus 5.5, whichever model the main session plans on. //' "$H/../../stub/opus-worker.md" > .claude/agents/opus-worker.md \
  && cp "$H/../../stub/sonnet-worker.md" .claude/agents/ && cp "$H/../../stub/hz-loader.py" .claude/ \
  && printf '# WR\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|\n| Quiz | 1 | 0 | swaps | no |\n' > WORKING_RECORD.md \
  && git add -A && git commit -qm base && git remote add origin "$T/selfupd.git" && git push -q origin main )
su(){ ( cd "$H" && CLAUDE_PROJECT_DIR="$U" python3 -c "
import sys;sys.path.insert(0,'.')
from _common import load_config;from stubcheck import stub_status;from stubupdate import update
cfg=load_config();s=stub_status(cfg,'$U');print('STATUS',s[:9])
if s.startswith('OUTDATED'):
    l,n=update(cfg,'$U');print('LINE',l);print('NOTE',n)" ); }
o=$(su); check "an outdated app updates its own setup files" "updated on disk just now" "$o"
check "the session is told to open a pull request from origin/main" "git switch -c hz-setup-update-" "$o"
check "the missing hotspot columns are added on the way" "hotspot table: two missing columns added" "$o"
check "the app's own settings entries are kept" "Bash(npm test)" "$(cat "$U/.claude/settings.json")"
check "the app's own CLAUDE.md section is kept" "keep me" "$(cat "$U/CLAUDE.md")"
check "the Opus helper is pinned after the update" "model: claude-opus-5-5" "$(cat "$U/.claude/agents/opus-worker.md")"
( cd "$U" && git stash -q && git switch -q -c hz-setup-update-$SV && git stash pop -q && git add -A && git commit -qm upd && git push -q origin hz-setup-update-$SV && git switch -q main )
o=$(su); check "while the pull request waits, no second one" "already waiting in a pull request" "$o"
check "while the pull request waits, nothing is rewritten" "^$" "$(cd "$U" && git status --short)"
( cd "$U" && git merge -q --ff-only hz-setup-update-$SV )
o=$(su); check "after the merge the stub is current" "STATUS current" "$o"
L="$T/localedit"; rm -rf "$L"; cp -r "$U" "$L"; ( cd "$L" && git switch -q -c other && git branch -q -D hz-setup-update-$SV && git update-ref -d refs/remotes/origin/hz-setup-update-$SV && git remote remove origin && printf '\n<!-- my own note -->\n' >> .claude/agents/opus-worker.md && sed -i 's/^model: claude-opus-5-5$/model: inherit/' .claude/agents/opus-worker.md )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$L" python3 -c "
import sys;sys.path.insert(0,'.')
from _common import load_config;from stubupdate import update
print(update(load_config(),'$L'))")
check "a helper file with local edits is left alone and reported" "has local edits" "$o"
o=$(cd "$H" && python3 -c "
import sys,os;sys.path.insert(0,'.')
from _common import load_config;from stubupdate import update
print(update(load_config(), os.path.abspath('$H/../..')))")
check "hz-claude-config itself never updates itself" "(None, None)" "$o"
# --- v3.1.21: QA/QC — destructive instructions, loader message for an incomplete rules repository
cat > "$T/destr.jsonl" <<J
{"type":"user","message":{"role":"user","content":"how do I update"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"1. Delete everything in the folder except .git.\n2. Extract the zip.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Ready.\n> 👉 **I need from you:** Follow the steps.\n> ➡️ **Next:** Merge."}]}}
J
rm -f "$PROJ/.claude/state/qc-rounds.json"
o=$(echo "{\"transcript_path\":\"$T/destr.jsonl\",\"stop_hook_active\":false}" | python3 $H/qc-guard.py)
check "a destructive instruction is sent back (QC2)" "QC2" "$o"
sed 's/2. Extract the zip./2. Extract the zip. This needs your separate yes./' "$T/destr.jsonl" > "$T/destr_ok.jsonl"
rm -f "$PROJ/.claude/state/qc-rounds.json"
o=$(echo "{\"transcript_path\":\"$T/destr_ok.jsonl\",\"stop_hook_active\":false}" | python3 $H/qc-guard.py)
check "the separate-confirmation form passes" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/shortneed.jsonl\",\"stop_hook_active\":false}" | python3 $H/qc-guard.py)
check "an ordinary reply passes the QC2 check" "^$" "$o"
check "the README has no step that empties the repository" "clean" "$(grep -ci 'delete everything\|empty the folder' "$H/../../README.md" | sed 's/^0$/clean/')"
check "the README keeps no old version numbers" "clean" "$(grep -c 'v3\.1\.1[0-9]' "$H/../../README.md" | sed 's/^0$/clean/')"
IN="$T/incomplete"; rm -rf "$IN"; mkdir -p "$IN/central/hooks" "$IN/proj/.claude" "$T/inc-cache"
cp "$H/../../stub/hz-loader.py" "$IN/proj/.claude/"; printf 'version: 9.9.9\nhooks/session-start.py\nhooks/missing.py\n' > "$IN/central/MANIFEST.txt"; cp "$H/session-start.py" "$IN/central/hooks/"
# v3.1.24: a free port and a wait until the server answers (a fixed port and "sleep 1" failed on back-to-back runs)
PORT=$(python3 -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()")
( cd "$IN" && python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$T/httpd.pid" )
for _ in $(seq 1 50); do python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$PORT/central/MANIFEST.txt',timeout=1)" 2>/dev/null && break; sleep 0.1; done
o=$(echo '{}' | CLAUDE_PROJECT_DIR="$IN/proj" HZ_CENTRAL_URL=http://127.0.0.1:$PORT/central/ HZ_CACHE_DIR="$T/inc-cache" python3 "$IN/proj/.claude/hz-loader.py" session-start.py)
kill $(cat "$T/httpd.pid") 2>/dev/null
check "the loader names a missing file instead of blaming the network" "incomplete on GitHub: hooks/missing.py" "$o"
# --- v3.1.22: session summary, version line from session start, plan counts, queued stages, setup first, tips
o=$(echo '{}' | python3 $H/session-start.py); check "v3.1.23: the session start sends no notice (the app does not show it)" "clean" "$(echo "$o" | grep -c systemMessage | sed 's/^0$/clean/')"
cat > "$T/stats.jsonl" <<J
{"type":"user","timestamp":"2026-10-01T10:00:00Z","message":{"role":"user","content":"build it"}}
{"type":"assistant","timestamp":"2026-10-01T10:01:00Z","message":{"id":"m1","model":"claude-fable-5-1","role":"assistant","usage":{"input_tokens":1000,"output_tokens":1000,"cache_read_input_tokens":8000},"content":[{"type":"text","text":"planning"}]}}
{"type":"assistant","timestamp":"2026-10-01T10:01:01Z","message":{"id":"m1","model":"claude-fable-5-1","role":"assistant","usage":{"input_tokens":1000,"output_tokens":1000,"cache_read_input_tokens":8000},"content":[{"type":"tool_use","id":"tu1","name":"Agent","input":{"subagent_type":"opus-worker","prompt":"Task: Build\nLevel: Complex"}}]}}
{"type":"assistant","isSidechain":true,"timestamp":"2026-10-01T10:02:00Z","message":{"id":"s1","model":"claude-opus-5-5","role":"assistant","usage":{"input_tokens":20000,"output_tokens":5000,"cache_read_input_tokens":45000},"content":[{"type":"text","text":"working"}]}}
{"type":"assistant","isSidechain":true,"timestamp":"2026-10-01T10:20:00Z","message":{"id":"s2","model":"claude-opus-5-5","role":"assistant","usage":{"input_tokens":10000,"output_tokens":0,"cache_read_input_tokens":10000},"content":[{"type":"text","text":"done"}]}}
{"type":"user","timestamp":"2026-10-01T10:20:05Z","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu1","content":"ok"}]}}
{"type":"assistant","timestamp":"2026-10-01T10:22:00Z","message":{"id":"m2","model":"claude-fable-5-1","role":"assistant","usage":{"input_tokens":0,"output_tokens":0,"cache_read_input_tokens":0},"content":[{"type":"text","text":"Confidence: High · Status: Checked\n---\n> 📌 **Result:** Built.\n> 👉 **I need from you:** Nothing.\n> ➡️ **Next:** Merge."}]}}
J
rm -f "$PROJ/.claude/state/session-stats.json"
sm(){ python3 -c "import json,sys;t=sys.stdin.read().strip();print(json.loads(t).get('systemMessage','') if t else '')"; }
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"st1\"}" | python3 $H/stats.py | sm)
check "the summary shows tokens by model" "Tokens: Opus 90% · Fable 10% (100 k)" "$o"
check "a message written in several parts is counted once" "(100 k)" "$o"
check "the summary shows time by model, helper waits not counted twice" "Time: Opus 18 min · Fable 3 min" "$o"
check "the summary shows hand-overs" "Hand-overs: Opus 1" "$o"
sed 's/Status: Checked/Status: Proposed/' "$T/stats.jsonl" > "$T/stats_prop.jsonl"
o=$(echo "{\"transcript_path\":\"$T/stats_prop.jsonl\",\"session_id\":\"st1\"}" | python3 $H/stats.py)
check "no summary on a plan that is not finished work" "^$" "$o"
grep -v isSidechain "$T/stats.jsonl" | sed 's/"content":\[{"type":"tool_result","tool_use_id":"tu1","content":"ok"}\]}}/"content":[{"type":"tool_result","tool_use_id":"tu1","content":"ok"}]},"toolUseResult":{"totalTokens":90000,"totalDurationMs":1080000}}/' > "$T/stats_fb.jsonl"
o=$(echo "{\"transcript_path\":\"$T/stats_fb.jsonl\",\"session_id\":\"st1\"}" | python3 $H/stats.py | sm)
check "helper totals are taken from the finished hand-over when no helper records exist" "Tokens: Opus 90% · Fable 10%" "$o"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","session_id":"st1","tool_input":{"command":"git push origin main"}}' | python3 $H/dispatch.py >/dev/null
echo "{\"hook_event_name\":\"Stop\",\"session_id\":\"st1\",\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | python3 $H/dispatch.py >/dev/null
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"st1\"}" | python3 $H/stats.py | sm)
check "the summary counts send-backs" "Send-backs: 1" "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"session_id\":\"st1\",\"transcript_path\":\"$T/stats.jsonl\",\"stop_hook_active\":false}" | python3 $H/dispatch.py)
check "the switchboard passes the summary to me" 'Session summary' "$o"
# counted by plan; queued and waiting stages
P2="$T/planrepo"; rm -rf "$P2"; mkdir -p "$P2"
( cd "$P2" && git init -q . && git config user.email t@t && git config user.name t \
  && printf '# WR\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n| R3 old round item | NOT STARTED | |\n| Splash redesign · Stage 1 of 3 — PR 1 | COMPLETE | tests 288 |\n| Splash redesign · Stage 2 of 3 — Merge PR 1 | NOT STARTED | |\n| Splash redesign · Stage 3 of 3 — PR 2 | NOT STARTED | |\n' > WORKING_RECORD.md \
  && git add -A && git commit -qm base && git update-ref refs/remotes/origin/main HEAD \
  && sed -i 's/| Splash redesign · Stage 2 of 3 — Merge PR 1 | NOT STARTED | |/| Splash redesign · Stage 2 of 3 — Merge PR 1 | WAITING ON YOU — merge PR 1 | |/; s/| Splash redesign · Stage 3 of 3 — PR 2 | NOT STARTED | |/| Splash redesign · Stage 3 of 3 — PR 2 | QUEUED — after Stage 2 | |/' WORKING_RECORD.md )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$P2" python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config,completion_summary;c=completion_summary(load_config());print(c['line']);print('open=',c['open'])")
check "the count covers the whole plan, not just this branch (v3.1.24: the merge waiting on you counts as Check)" "Completion: Build 1 of 2 done (50%) · Check 0 of 1 — Splash redesign" "$o"
check "old rounds and queued stages are not open work" "open= \[\]" "$o"
# setup update first
SG="$T/setuprepo"; rm -rf "$SG"; mkdir -p "$SG/.claude/state"; ( cd "$SG" && git init -q . && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m b )
echo '{"branch":"hz-setup-update-9.9"}' > "$SG/.claude/state/setup-pending.json"
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"sg1\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$SG" python3 $H/setup-guard.py)
check "no other answer before the setup pull request" "Do the setup update before anything else" "$o"
( cd "$SG" && git branch -q hz-setup-update-9.9 )
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"sg1\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$SG" python3 $H/setup-guard.py)
check "once the setup branch exists, answers go out" "^$" "$o"
check "the pending note is cleared" "gone" "$([ -f "$SG/.claude/state/setup-pending.json" ] && echo still || echo gone)"
# after a merge: where we are + fresh session
o=$(echo '{"prompt":"merged, move on"}' | python3 $H/plan-gate.py); check "after a merge the session is told to hand off" "hand-off" "$o"
# plan check: changes box, count line, Fable tip
grep -v '```\|^+ \|^Changes in this version' "$T/plan_good.md" > "$T/plan_nodiff.md"
o=$(pg "$T/plan_nodiff.md"); check "a revised plan without the changes box is sent back" "Changes in this version" "$o"
grep -v '^4 stages' "$T/plan_good.md" > "$T/plan_nocount.md"
o=$(pg "$T/plan_nocount.md"); check "a plan without the stage-count line is sent back" "explains the count" "$o"
o=$(python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','transcript_path':'$T/stats.jsonl','tool_input':{'plan':open('$T/plan_good.md',encoding='utf-8').read()}}))" | python3 $H/dispatch.py)
check "after a Fable plan passes, I get the switch-to-Opus tip" "type /model opus" "$o"
# --- UserPromptSubmit: skill router
o=$(echo '{"prompt":"review my index.html, is this working?"}' | python3 $H/skill-router.py); check "skill-router matches hz-reviewer" "anthropic-skills:hz-reviewer" "$o"
o=$(echo '{"prompt":"build the whole app, full version"}' | python3 $H/skill-router.py); check "skill-router matches hz-planner" "anthropic-skills:hz-planner" "$o"
o=$(echo '{"prompt":"start a new chat but keep where we are"}' | python3 $H/skill-router.py); check "skill-router matches hz-chat-handoff" "anthropic-skills:hz-chat-handoff" "$o"
o=$(echo '{"prompt":"is this rule file right?"}' | python3 $H/skill-router.py); check "a rules-file question goes to hz-reviewer" "anthropic-skills:hz-reviewer" "$o"
# --- PreToolUse: routing guard
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard (enforce by default) refuses the planner's own source edit" '"deny"' "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","agent_id":"a77","agent_type":"opus-worker","tool_input":{"file_path":"$PROJ/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard lets a worker's source edit through" "^$" "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/js/app.js"}}' | python3 $H/routing-guard.py); check "routing-guard enforce denies main-session source edit" '"deny"' "$o"
o=$(echo '{"tool_name":"Edit","session_id":"s1","tool_input":{"file_path":"$PROJ/CLAUDE.md"}}' | python3 $H/routing-guard.py); check "routing-guard enforce allows governance edit" "^$" "$o"
# --- v3.1.23: closing block at the bottom, version line in the Stop notice, notices kept on a send-back,
#     re-read tokens shown, record check per prompt, plan files in the repository
cat > "$T/top_old.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"> 📌 **Result:** ready.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** waiting.\n---\n\nDetail.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/top_old.jsonl"); check "the three lines at the top are now sent back" "ends with a quote block" "$o"
check "the send-back asks for the three lines last" "three closing lines last" "$o"
cat > "$T/bottom_tail.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Detail.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** ready.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** waiting.\n\nOne more thing after the block."}]}}
J
o=$(vl "$T/bottom_tail.jsonl"); check "text after the closing lines is sent back" "Nothing comes after these three lines" "$o"
o=$(echo "{\"transcript_path\":\"$T/shortneed.jsonl\",\"session_id\":\"v23\"}" | python3 $H/stats.py | sm)
check "the first reply shows the version line even before finished work" "^Rules v$VER · " "$o"
check "the first reply's notice is the version line only" "clean" "$(echo "$o" | grep -c 'Session summary' | sed 's/^0$/clean/')"
o=$(echo "{\"transcript_path\":\"$T/shortneed.jsonl\",\"session_id\":\"v23\"}" | python3 $H/stats.py)
check "the version line is shown once, not on every plan" "^$" "$o"
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"v23\"}" | python3 $H/stats.py | sm)
check "the summary opens with the version line" "^Rules v$VER · " "$o"
check "the summary shows how much was re-reading" "63 k of it re-reading what was already sent" "$o"
check "the stats log says what was shown" '"shown": "summary"' "$(cat "$PROJ/.claude/state/stats.jsonl")"
o=$(echo "{\"hook_event_name\":\"Stop\",\"session_id\":\"v23\",\"transcript_path\":\"$T/top_old.jsonl\",\"stop_hook_active\":false}" | dp)
check "a send-back keeps the notice beside it" '"systemMessage": "Rules v' "$o"
check "a send-back still sends back" '"decision": "block"' "$o"
check "the switchboard logs every Stop" '"sent_back": 1' "$(cat "$PROJ/.claude/state/dispatch.jsonl")"
SP="$T/setupwait"; rm -rf "$SP"; mkdir -p "$SP/.claude"; ( cd "$SP" && git init -q . && git config user.email t@t && git config user.name t && echo '{}' > .claude/settings.json && git add -A && git commit -qm b && git branch -q hz-setup-update-3.1.23 )
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"v23b\"}" | CLAUDE_PROJECT_DIR="$SP" python3 $H/stats.py | sm)
check "an outdated setup with its update branch waiting reads 'waiting for your merge'" "setup waiting for your merge" "$o"
pn 7; rm -f "$PROJ/.claude/state/record-rounds.json"; touch -d '1999-01-01' WORKING_RECORD.md
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":true}" | python3 $H/record-guard.py)
check "record check still sends back when another check blocked first (stop_hook_active)" "record is incomplete" "$o"
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":true}" | python3 $H/record-guard.py)
check "record check sends back once per request, then never loops" "^$" "$o"
pn 8
o=$(echo "{\"transcript_path\":\"$T/norecord.jsonl\",\"stop_hook_active\":false}" | python3 $H/record-guard.py)
check "a new request gets its own record send-back" "record is incomplete" "$o"
rm -f "$PROJ/.claude/state/prompt-number.json" "$PROJ/.claude/state/record-rounds.json"; touch WORKING_RECORD.md
check "the stub writes plan files into the repository" '"plansDirectory": "./plans"' "$(cat "$H/../../stub/settings.json")"
S3="$T/stubplans"; rm -rf "$S3"; mkdir -p "$S3/.claude/agents"
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$S3/.claude/agents/"; cp "$H/../../stub/hz-loader.py" "$S3/.claude/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S3/CLAUDE.md"
python3 -c "import json;s=json.load(open('$H/../../stub/settings.json'));s.pop('plansDirectory');json.dump(s,open('$S3/.claude/settings.json','w'))"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "a stub without the plan folder shows OUTDATED" "OUTDATED.*plan files saved in the repository" "$o"
python3 "$H/../../stub/merge_settings.py" "$H/../../stub/settings.json" "$S3/.claude/settings.json" "hz-loader.py"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "the self-update adds the plan folder and the stub is current again" "current (matches v3.1.23)" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "session start tells the session the plan file lands in plans/" "written into plans/ in this" "$o"
check "session start describes the closing lines at the end" "Every final answer ends with a" "$o"
# --- v3.1.24: plan file carries every revision, hand-off done by the session, blocked items listed
HB="$T/h24"; rm -rf "$HB"; mkdir -p "$HB"; git init -q --bare "$HB/origin.git"; HA="$HB/app"; git init -q "$HA"
( cd "$HA" && git config user.email t@t && git config user.name t && git remote add origin ../origin.git
cat > WORKING_RECORD.md <<'R'
# WORKING RECORD

## Where we are
- start

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| R14 / Plan v3 — Sunday v15 · Stage 1 of 5 — kids page | COMPLETE | tests |
| R14 / Plan v3 — Sunday v15 · Stage 2 of 5 — ritual | COMPLETE | tests |
| R14 / Plan v3 — Sunday v15 · Stage 3 of 5 — grown-ups | NOT STARTED | |
| R14 / Plan v3 — Sunday v15 · Stage 4 of 5 — looks | BLOCKED — needs icons | |
| R14 / Plan v3 — Sunday v15 · Stage 5 of 5 — old export | SUPERSEDED | |
| R14 / Plan v3 — Sunday v15 · Stage 6 of 6 — PR | QUEUED — after Stage 4 | |
R
mkdir plans && printf '# R14 · Plan v3 — Sunday v15\n' > plans/a.md && echo x > index.html && git add -A && git commit -qm base \
  && git push -q origin HEAD:main && git checkout -qb claude/sunday-v15 && git push -q -u origin claude/sunday-v15 ) >/dev/null 2>&1
hg(){ printf '%s' "$1" > "$HB/t.jsonl"; rm -f "$HA/.claude/state/handoff-rounds.json"; echo "{\"transcript_path\":\"$HB/t.jsonl\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HA" python3 $H/handoff-guard.py; }
msg(){ python3 -c "import json,sys;print(json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':sys.argv[1]}]}}))" "$1"; }
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])")
check "superseded rows are not counted" "Completion: 2 of 5 done" "$o"
check "blocked items are listed with their state" "Stage 4 of 5 — looks (blocked)" "$o"
check "queued items are listed with their state" "Stage 6 of 6 — PR (queued)" "$o"
check "done plus listed adds up (3 listed for 3 not done)" "^3$" "$(echo "$o" | grep -c '^- ')"
o=$(hg "$(msg 'Plan v5 is ready.
Confidence: High · Status: Proposed')"); check "a Plan vN only in the chat is sent back" "names Plan v5, but the newest plan file in plans/ is Plan v3" "$o"
o=$(hg "$(msg 'Plan v3 is ready.
Confidence: High · Status: Proposed')"); check "the plan number of the newest plan file passes" "^$" "$o"
printf '# R14 · Plan v5 — Sunday v15\n' > "$HA/plans/b.md"
o=$(hg "$(msg 'Plan v5 is ready.')"); check "a ledger plan name with an older version is renamed" "Rename the plan's rows" "$o"
rm -f "$HA/plans/b.md"
L1='Completion: 2 of 5 done (40%)
- R14 / Plan v3 — Sunday v15 · Stage 3 of 5 — grown-ups
- R14 / Plan v3 — Sunday v15 · Stage 4 of 5 — looks (blocked)
- R14 / Plan v3 — Sunday v15 · Stage 6 of 6 — PR (queued)
```
Continue R14 / Plan v3 — Sunday v15 on branch claude/sunday-v15; next: Stage 3 of 5 — grown-ups.
```
Confidence: High · Status: Checked'
echo "- next: Stage 3" >> "$HA/WORKING_RECORD.md"
o=$(hg "$(msg "$L1")"); check "a restart line with the record not committed is sent back" "Commit and push WORKING_RECORD.md" "$o"
( cd "$HA" && git commit -qam where ) >/dev/null
o=$(hg "$(msg "$L1")"); check "a restart line with the record committed but not pushed is sent back" "Commit and push" "$o"
( cd "$HA" && git push -q ) >/dev/null 2>&1
o=$(hg "$(msg "$L1")"); check "a pushed record, the ledger name, this branch and every row listed: passes" "^$" "$o"
o=$(hg "$(msg 'Continue R14 / Plan v5 — Sunday on branch claude/sunday-v15; next: Stage 3.')")
check "a restart line with another plan name is sent back with the exact line" "Plan v3 .u2014 Sunday v15 on branch claude/sunday-v15; next: Stage 3 of 5" "$o"
check "a restart line without the not-complete rows is sent back" "List every row of the plan that is not complete" "$o"
o=$(hg "$(msg 'Continue R14 / Plan v3 — Sunday v15 on branch main; next: Stage 3.')"); check "a restart line with the wrong branch is sent back" "names branch main, but this session is on claude/sunday-v15" "$o"
printf '{"session":"hs","n":3}' > "$HA/.claude/state/prompt-number.json"; rm -f "$HA/.claude/state/handoff-rounds.json"
printf '%s' "$(msg 'Plan v9.')" > "$HB/t.jsonl"
o=$(echo "{\"transcript_path\":\"$HB/t.jsonl\",\"session_id\":\"hs\"}" | CLAUDE_PROJECT_DIR="$HA" python3 $H/handoff-guard.py); check "hand-off check: first send-back" "Plan v9" "$o"
o=$(echo "{\"transcript_path\":\"$HB/t.jsonl\",\"session_id\":\"hs\"}" | CLAUDE_PROJECT_DIR="$HA" python3 $H/handoff-guard.py); check "hand-off check: once per request, never loops" "^$" "$o"
rm -f "$HA/.claude/state/prompt-number.json"
o=$(echo '{"prompt":"merged, go on","session_id":"m1"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "after a merge the session gets the hand-off with the exact restart line" "Plan v3 .u2014 Sunday v15 on branch claude/sunday-v15; next: Stage 3 of 5" "$o"
check "the hand-off asks to commit and push the record" "commit and push WORKING_RECORD.md to claude/sunday-v15" "$o"
check "the hand-off asks for every row that is not complete" "open, blocked, queued" "$o"
check "the hand-off points to the plan file instead of copying it" "its plan file path" "$o"
mkdir -p "$HA/.claude/state"; printf '{"long1": 2000000}' > "$HA/.claude/state/session-tokens.json"
o=$(echo '{"prompt":"next step please","session_id":"long1"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "a long session is asked to hand off at the next stage break" "This session is long (2.0 M tokens)" "$o"
o=$(echo '{"prompt":"next step please","session_id":"long1"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "the long-session hand-off is asked once per session" "clean" "$(echo "$o" | grep -c 'This session is long' | sed 's/^0$/clean/')"
o=$(echo '{"prompt":"next step please","session_id":"short1"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "a short session is not asked to hand off" "clean" "$(echo "$o" | grep -c 'hand-off' | sed 's/^0$/clean/')"
o=$(echo '{"prompt":"Continue R14 / Plan v3 — Sunday v15 on branch claude/sunday-v15; next: Stage 3 of 5.","session_id":"r1"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "a restart line makes the new session switch to its branch first" "First switch to branch claude/sunday-v15" "$o"
check "the new session reads Where we are and waits" "Wait for my OK" "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"session_id\":\"v24\",\"transcript_path\":\"$T/top_old.jsonl\",\"stop_hook_active\":false}" | dp)
check "a send-back carries only the version line, not the summary" "clean" "$(echo "$o" | grep -c 'Session summary' | sed 's/^0$/clean/')"
check "the switchboard runs the hand-off check on Stop" "handoff-guard.py" "$(cat $H/config.json)"
# --- v3.1.24b: Build and Check counted apart; hand-off when Build reaches 100%
HC="$T/hc"; rm -rf "$HC"; mkdir -p "$HC"; git init -q --bare "$HC/origin.git"; HCA="$HC/app"; git init -q "$HCA"
( cd "$HCA" && git config user.email t@t && git config user.name t && git remote add origin ../origin.git
cat > WORKING_RECORD.md <<'R'
# WORKING RECORD

## Where we are
- start

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| Sunday recovery · Stage 1 of 7 — failing tests | COMPLETE | 6 tests red |
| Sunday recovery · Stage 2 of 7 — change in both apps | COMPLETE | tests green |
| Sunday recovery · Stage 3 of 7 — run every test | COMPLETE | 120/120 |
| Sunday recovery · Stage 4 of 7 — draft pull requests | COMPLETE | PR 12, PR 13 |
| Sunday recovery · Stage 5 of 7 — merge both (Check) | WAITING ON YOU — merge PR 12 and 13 | |
| Sunday recovery · Stage 6 of 7 — live site updated (Check) | QUEUED — after Stage 5 | |
| Sunday recovery · Stage 7 of 7 — Sunday recovery on the device (Check) | QUEUED — after Stage 6 | |
R
echo x > index.html && git add -A && git commit -qm base && git push -q origin HEAD:main && git checkout -qb claude/recovery && git push -q -u origin claude/recovery ) >/dev/null 2>&1
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HCA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])")
check "Build and Check are counted apart: Build 100% when Claude's work is done" "Completion: Build 4 of 4 done (100%) · Check 0 of 3" "$o"
check "the checks are listed under their own heading" "^Check:" "$o"
check "Build done says the rest is checking and how to come back" "Build is done; the rest is checking" "$o"
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HCA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;c=completion_summary(load_config());print(restart_line(c))")
check "after Build, the restart line points to the first check" "next: Stage 5 of 7 — merge both" "$o"
printf '%s' "$(msg 'Done.
Completion: Build 4 of 4 done (100%) · Check 0 of 3
Confidence: High · Status: Checked')" > "$HC/t.jsonl"
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "v3.1.24: a report at Build 100% without the restart line is sent back for the hand-off" "Build is at 100% and only checks are left" "$o"
check "that send-back carries the exact restart line with the first check" "next: Stage 5 of 7" "$o"
( cd "$HCA" && sed -i 's/^- start$/- start\n- Restart: Continue Sunday recovery on branch claude\/recovery; next: Stage 5 of 7 — merge both (Check)./' WORKING_RECORD.md )
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "once the restart line stands in Where we are, later reports pass" "^$" "$o"
( cd "$HCA" && sed -i 's/| Sunday recovery · Stage 4 of 7 — draft pull requests | COMPLETE | PR 12, PR 13 |/| Sunday recovery · Stage 4 of 7 — draft pull requests | NOT STARTED | |/' WORKING_RECORD.md )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HCA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['line'])")
check "an open Build stage keeps Build below 100%" "Completion: Build 3 of 4 done (75%) · Check 0 of 3" "$o"
o=$(echo '{"prompt":"go on","session_id":"b1"}' | CLAUDE_PROJECT_DIR="$HCA" python3 $H/plan-gate.py)
check "while Build is open, the session is told to hand off when Build reaches 100%" "When the last Build stage is finished" "$o"
check "that hand-off names the first check as next" "next: Stage 5 of 7" "$o"
printf '%s' "$(msg 'Not yet.
Completion: Build 3 of 4 done (75%) · Check 0 of 3
Confidence: High · Status: Checked')" > "$HC/t.jsonl"
printf '{"session":"cg9","n":1}' > "$HCA/.claude/state/prompt-number.json" 2>/dev/null || { mkdir -p "$HCA/.claude/state"; printf '{"session":"cg9","n":1}' > "$HCA/.claude/state/prompt-number.json"; }
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"session_id\":\"cg9\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "an open Build stage is still sent back" "draft pull requests" "$o"
check "checks are never named as work to do now" "clean" "$(echo "$o" | grep -c 'Continue with .Sunday recovery · Stage 5' | sed 's/^0$/clean/')"
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HCA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['line'])" )
( cd "$HCA" && sed -i 's/| Sunday recovery · Stage 5 of 7 — merge both (Check) | WAITING ON YOU — merge PR 12 and 13 | |/| Sunday recovery · Stage 5 of 7 — merge both | WAITING ON YOU — merge PR 12 and 13 | |/' WORKING_RECORD.md )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$HCA" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['line'])")
check "a stage waiting on you counts as Check even without the label" "Check 0 of 3" "$o"
printf '%s' "$(msg 'Build still open.
Completion: Build 3 of 4 done (75%) · Check 0 of 3
Confidence: High · Status: Checked')" > "$HC/t.jsonl"; printf '{"session":"cg9","n":2}' > "$HCA/.claude/state/prompt-number.json"
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"session_id\":\"cg9\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "an unlabelled check row is sent back to get its (Check) label, so ticking it never moves it to Build" "Add ' (Check)' to the end of these row names" "$o"
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$PROJ" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['line'])")
check "a plan without checks keeps the plain line" "^Completion: [0-9][0-9]* of [0-9][0-9]* done" "$o"
check "the rules name rows by the plan name only (no R-number)" "plan name only" "$(cat $H/../rules/CLAUDE-rules.md)"
# --- v3.1.24c: closing lines without colour codes or sizes
cat > "$T/jargon.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Detail.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Every button is at least 44px tall, and the orange-red #c14a24 is drawn as #b8441f.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** waiting."}]}}
J
o=$(vl "$T/jargon.jsonl"); check "colour codes in the closing lines are sent back" "no colour codes or sizes (#b8441f, #c14a24, 44px)" "$o"
check "the send-back says a change from what I approved is a question" "is a question in the " "$o"
cat > "$T/plainclose.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Buttons are 44px; colour #b8441f (details may keep codes).\n\nConfidence: High · Status: Checked\n❓ Decisions\n1. Use a slightly darker orange-red? Recommended: no.\n---\n> 📌 **Result:** Buttons are finger-sized now.\n> 👉 **I need from you:** Answer the colour question.\n> ➡️ **Next:** I keep your colour unless you say otherwise."}]}}
J
o=$(vl "$T/plainclose.jsonl"); check "codes in the details are fine when the closing lines are plain" "^$" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "session start says a change from what I approved is a question" "is a question in that list" "$o"
# --- v3.1.25: tokens by activity (planning, coding, testing, other) in the session summary
python3 - "$T/act.jsonl" <<'PY'
import json, sys
def a(i, tools, tok):
    c = [{"type": "tool_use", "id": f"t{i}{k}", "name": n, "input": inp} for k, (n, inp) in enumerate(tools)]
    return {"type": "assistant", "timestamp": f"2026-10-04T10:{i:02d}:00Z", "message": {"id": f"m{i}", "model": "claude-opus-5-5",
            "role": "assistant", "usage": {"input_tokens": tok, "output_tokens": 0}, "content": c or [{"type": "text", "text": "x"}]}}
recs = [{"type": "user", "message": {"role": "user", "content": "go"}},
        a(1, [("Read", {"file_path": "js/app.js"}), ("Grep", {"pattern": "x"})], 300),
        a(2, [("Agent", {"subagent_type": "Explore", "prompt": "look"})], 100),
        a(3, [("Edit", {"file_path": "js/app.js"})], 400),
        a(4, [("Bash", {"command": "npm test"})], 150),
        a(5, [("Bash", {"command": "npx playwright test tests/smoke.spec.js"}), ("Read", {"file_path": "x"})], 50),
        a(6, [("Bash", {"command": "git push -u origin claude/x"})], 80),
        a(7, [("Edit", {"file_path": "a"}), ("Bash", {"command": "npm test"})], 20),
        a(8, [], 100)]
recs[-1]["message"]["content"] = [{"type": "text", "text": "Done.\n\nConfidence: High · Status: Checked"}]
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in recs) + "\n")
PY
o=$(echo "{\"transcript_path\":\"$T/act.jsonl\",\"session_id\":\"act1\"}" | python3 $H/stats.py | sm)
check "the summary shows tokens by activity" "^Activity: planning 33% · coding 33% · testing 18% · other 15%" "$o"
check "the activity line says it is an estimate" "estimate" "$o"
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"act2\"}" | python3 $H/stats.py | sm)
check "helper totals count by helper type (workers code, Explore and Plan plan)" "^Activity: " "$o"
# --- v3.1.25b: plan body in everyday words, Edmonton time, in-between messages counted
sed 's/^1\. Build the lessons · Claude · Build$/1. Build the lessons in js\/lessons.js line 120 with saveWeek() · Claude · Build/' "$T/plan_good.md" > "$T/plan_jargon.md"
o=$(pg "$T/plan_jargon.md"); check "a plan body with file names, line numbers or code is sent back" "js/lessons.js" "$o"
check "the send-back points to Technical details" "Technical details" "$o"
printf '\nTechnical details: js/lessons.js line 120, saveWeek(), commit 8b56fdb.\n' >> "$T/plan_good2.md"; cat "$T/plan_good.md" > "$T/plan_good2.md"; printf 'More technical notes: js/lessons.js line 120, saveWeek().\n' >> "$T/plan_good2.md"
o=$(pg "$T/plan_good2.md"); check "file names and code inside Technical details are fine" "^$" "$o"
cat > "$T/utc.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Merged at 00:02 UTC.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** merged.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** nothing."}]}}
J
o=$(vl "$T/utc.jsonl"); check "a UTC time in a finished answer is sent back" "Edmonton time" "$o"
cat > "$T/utc_iso.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Deployed 2026-10-04T06:02:11Z.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** deployed.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** nothing."}]}}
J
o=$(vl "$T/utc_iso.jsonl"); check "a raw UTC timestamp is sent back too" "Edmonton time" "$o"
cat > "$T/utc_code.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Merged at 6:02 PM MDT.\n```\nlog 2026-10-04T00:02:11Z ok\n```\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** merged.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** nothing."}]}}
J
o=$(vl "$T/utc_code.jsonl"); check "local time passes, and a log inside a code block is left alone" "^$" "$o"
o=$(cd "$H" && python3 -c "
import sys;sys.path.insert(0,'.');from _common import edmonton_time;from datetime import datetime,timezone as z
for d in ((2026,10,4,6,0),(2026,12,1,7,0),(2026,3,8,8,59),(2026,3,8,9,0),(2026,11,1,7,59),(2026,11,1,8,0)): print(edmonton_time(datetime(*d,tzinfo=z.utc)))")
check "Edmonton time in summer is MDT (UTC-6)" "Oct 4, 12:00 AM MDT" "$o"
check "Edmonton time in winter is MST (UTC-7)" "Dec 1, 12:00 AM MST" "$o"
check "daylight time starts on the second Sunday of March" "Mar 8, 1:59 AM MST" "$o"
check "  ...at 2 AM local" "Mar 8, 3:00 AM MDT" "$o"
check "daylight time ends on the first Sunday of November" "Nov 1, 1:59 AM MDT" "$o"
check "  ...back to 1 AM MST" "Nov 1, 1:00 AM MST" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "session start gives the current Edmonton time" "Times for me are in Edmonton time" "$o"
python3 - "$T/chat.jsonl" <<'PY'
import json, sys
def a(i, blocks): return {"type": "assistant", "message": {"id": f"c{i}", "model": "claude-opus-5-5", "role": "assistant", "usage": {"input_tokens": 10}, "content": blocks}}
def tu(i): return {"type": "tool_use", "id": f"u{i}", "name": "Read", "input": {}}
def tx(s): return {"type": "text", "text": s}
recs = [{"type": "user", "message": {"role": "user", "content": "go"}},
        a(1, [tx("Now I'll read the file."), tu(1)]),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u1", "content": "x"}]}},
        a(2, [tu(2)]),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u2", "content": "x"}]}},
        a(3, [tx("Retrying.")]), a(4, [tu(4)]),
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u4", "content": "x"}]}},
        a(5, [tx("Done.\n\nConfidence: High · Status: Checked")])]
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in recs) + "\n")
PY
o=$(echo "{\"transcript_path\":\"$T/chat.jsonl\",\"session_id\":\"ch1\"}" | python3 $H/stats.py | sm)
check "the summary counts in-between messages (2 here, the final answer not counted)" "In-between messages: 2" "$o"
# --- v3.1.25c: the completion send-back keeps the closing lines last; preferences carry Edmonton time
check "the completion send-back puts its lines before the validation line, closing lines last" "the three closing lines stay last" "$(cat $H/completion-guard.py)"
check "claude.ai preferences ask for Edmonton time" "Edmonton time" "$(cat $H/../../docs/claude-ai-preferences.txt)"
check "claude.ai preferences make changes from the approval a question" "is a question in the Decisions list" "$(cat $H/../../docs/claude-ai-preferences.txt)"
echo; echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
