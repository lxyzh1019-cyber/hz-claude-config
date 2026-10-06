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
export HZ_CHAT_REPLY_MAX_CHARS=0   # v3.1.26: judge short fixtures as work reports
export HZ_PLANNER_CHECK_OFF=1      # v3.1.30: older plan-shape tests run as if the planner wrote the plan; the v3.1.30 tests switch it on
export HZ_RULES_FIRST_OFF=1        # v3.1.29: older tests run as if the rules were read; the v3.1.29 tests switch it on
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
check "rules file named at session start (v3.1.29: read, not injected)" "read the full working rules with the Read tool" "$o"
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
check "marking an open pull request draft is allowed again (v3.1.30: back to draft while it is fixed)" '^$' "$(ggt mcp__github__update_pull_request '{"pullNumber":1,"draft":true}')"
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
o=$(echo '{"prompt":"why does the sync layer keep breaking across all apps? find the root cause and redesign it"}' | python3 $H/plan-gate.py); check "planner: a big plan goes to the planner helper (v3.1.30; was: Fable suggested)" "the planner helper writes it" "$o"
o=$(echo '{"prompt":"- add a button\n- fix colour\n- change the label"}' | python3 $H/plan-gate.py); check "planner: a full plan is written by the planner helper (v3.1.30)" "A full plan is written by the 'planner' helper" "$o"
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
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" "$S/.claude/agents/"
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
cp "$H/../../stub/settings.json" "$M/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" "$M/.claude/agents/"
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
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" "$S2/.claude/agents/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S2/CLAUDE.md"
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
o=$(pg "$T/plan_good.md"); check "a plan with summary, squares and stages passes the Approve check" "Plan size: about" "$o"
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
check "a worker started in the background is no longer refused for that (v3.1.30: Claude Code runs workers in the background)" "clean" "$(echo "$o" | grep -c "Workers run in the foreground" | sed 's/^0$/clean/')"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":"opus-worker","prompt":"Task: Fix sync\nLevel: Complex\nMap: js/sync.js lines 10-80\nfind why"}}' | python3 $H/dispatch.py)
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
cp "$H/../../stub/settings.json" "$S3/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" "$S3/.claude/agents/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S3/CLAUDE.md"; cp "$H/../../stub/hz-loader.py" "$S3/.claude/"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "the new stub reads current" "^current" "$o"
sed -i 's/^model: claude-opus-5-5$/model: inherit/' "$S3/.claude/agents/opus-worker.md"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "an unpinned Opus helper shows OUTDATED" "OUTDATED.*Opus helper pinned" "$o"
# --- v3.1.20: app repositories update their own setup files
for n in settings.json opus-worker.md sonnet-worker.md reviewer.md explore.md planner.md planner-opus.md hz-loader.py CLAUDE-pointer.md merge_settings.py v2-known-files.txt; do
  cmp -s "$H/../../stub/$n" "$H/../stub-files/$n" || echo "stub-files out of step: $n"
done > "$T/stubsync.txt"
check "the central copies of the setup files match stub/" "^$" "$(cat "$T/stubsync.txt")"
SV=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;print(load_config()['stub_expect']['version'])")
U="$T/selfupd"; rm -rf "$U" "$T/selfupd.git"; mkdir -p "$U/.claude/agents"; git init -q --bare "$T/selfupd.git"
( cd "$U" && git init -q -b main . && git config user.email t@t && git config user.name t \
  && printf '# Repository rules\n\nold pointer hz-loader.py\n\nRepository-specific files: `FEATURES.md` and `WORKING_RECORD.md`.\n\n## Project Architecture\nkeep me\n' > CLAUDE.md \
  && python3 -c "import json;s=json.load(open('$H/../../stub/settings.json'));s['permissions']['allow'].append('Bash(npm test)');[g.__setitem__('matcher',g['matcher'].replace('ExitPlanMode|','')) for g in s['hooks']['PreToolUse']];json.dump(s,open('.claude/settings.json','w'),indent=2)" \
  && sed 's/^model: claude-opus-5-5$/model: inherit/; s/Always runs on Opus 5.5, whichever model the main session plans on. //' "$H/../../stub/opus-worker.md" > .claude/agents/opus-worker.md \
  && cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" .claude/agents/ && cp "$H/../../stub/hz-loader.py" .claude/ \
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
check "the send-back asks for the three lines last (v3.1.29: only --- and the three lines)" "Send only a line with just --- and the three closing lines" "$o"
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
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$H/../../stub/reviewer.md" "$H/../../stub/explore.md" "$H/../../stub/planner.md" "$H/../../stub/planner-opus.md" "$S3/.claude/agents/"; cp "$H/../../stub/hz-loader.py" "$S3/.claude/"; cp "$H/../../stub/CLAUDE-pointer.md" "$S3/CLAUDE.md"
python3 -c "import json;s=json.load(open('$H/../../stub/settings.json'));s.pop('plansDirectory');json.dump(s,open('$S3/.claude/settings.json','w'))"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "a stub without the plan folder shows OUTDATED" "OUTDATED.*plan files saved in the repository" "$o"
python3 "$H/../../stub/merge_settings.py" "$H/../../stub/settings.json" "$S3/.claude/settings.json" "hz-loader.py"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$S3'))")
check "the self-update adds the plan folder and the stub is current again" "current (matches v3.1.30)" "$o"
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
check "the summary shows tokens by activity (v3.1.26 groups)" "^Activity: planning 33% · coding 33% · testing 18% · git & pull requests 7% · talking 8%" "$o"
check "the activity line says it is an estimate" "estimate" "$o"
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"act2\"}" | python3 $H/stats.py | sm)
check "helper totals count by helper type (workers code, Explore and Plan plan)" "^Activity: " "$o"
# --- v3.1.25b: plan body in everyday words, Edmonton time, in-between messages counted
sed 's/^1\. Build the lessons · Claude · Build$/1. Build the lessons in js\/lessons.js line 120 with saveWeek() · Claude · Build/' "$T/plan_good.md" > "$T/plan_jargon.md"
o=$(pg "$T/plan_jargon.md"); check "a plan body with file names, line numbers or code is sent back" "js/lessons.js" "$o"
check "the send-back points to Technical details" "Technical details" "$o"
printf '\nTechnical details: js/lessons.js line 120, saveWeek(), commit 8b56fdb.\n' >> "$T/plan_good2.md"; cat "$T/plan_good.md" > "$T/plan_good2.md"; printf 'More technical notes: js/lessons.js line 120, saveWeek().\n' >> "$T/plan_good2.md"
o=$(pg "$T/plan_good2.md"); check "file names and code inside Technical details are fine" "Plan size: about" "$o"
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
check "claude.ai preferences keep the step-writing line" "ASD-STE100-lite" "$(cat $H/../../docs/claude-ai-preferences.txt)"
check "claude.ai preferences keep the hz-designer line" "use hz-designer, not design-critique" "$(cat $H/../../docs/claude-ai-preferences.txt)"
check "claude.ai preferences: Projects end with the closing block too" "still end with my closing block" "$(cat $H/../../docs/claude-ai-preferences.txt)"
# --- v3.1.26: main vs helpers, clearer activity groups, helper time counted once
SD="$T/s26"; rm -rf "$SD"; mkdir -p "$SD/sess26/subagents"
python3 - "$SD" <<'PY'
import json, sys, os
d = sys.argv[1]
def a(i, tools, tok, ts, side=False, text=None):
    c = [{"type": "tool_use", "id": f"t{i}{k}", "name": n, "input": inp} for k, (n, inp) in enumerate(tools)]
    if text: c = [{"type": "text", "text": text}]
    r = {"type": "assistant", "timestamp": ts, "message": {"id": f"m{i}", "model": "claude-opus-5-5", "role": "assistant",
         "usage": {"input_tokens": tok, "output_tokens": 0}, "content": c}}
    if side: r["isSidechain"] = True
    return r
u = {"type": "user", "timestamp": "2026-10-04T10:00:00Z", "message": {"role": "user", "content": "go"}}
main = [u,
  a(1, [("Bash", {"command": "cat js/app.js | head -50"})], 100, "2026-10-04T10:01:00Z"),
  a(2, [("Bash", {"command": "git commit -m x && git push"})], 100, "2026-10-04T10:02:00Z"),
  a(3, [("Bash", {"command": "gh pr create --draft"})], 100, "2026-10-04T10:03:00Z"),
  a(4, [], 100, "2026-10-04T10:04:00Z", text="Checking the next part."),
  a(5, [("Bash", {"command": "node tools/capture-screenshots.js"})], 100, "2026-10-04T10:05:00Z"),
  a(6, [("Bash", {"command": "npm run build"})], 100, "2026-10-04T10:06:00Z"),
  a(7, [("Agent", {"subagent_type": "opus-worker", "prompt": "Task: x / Level: Complex"})], 100, "2026-10-04T10:07:00Z"),
  {"type": "user", "timestamp": "2026-10-04T10:29:00Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t70", "content": "done"}]}},
  a(8, [], 100, "2026-10-04T10:30:00Z", text="Done.\n\nConfidence: High · Status: Checked")]
open(os.path.join(d, "sess26.jsonl"), "w").write("\n".join(json.dumps(r) for r in main) + "\n")
helper = [a(20, [("Edit", {"file_path": "a"})], 2000, "2026-10-04T10:08:00Z"),
          a(21, [("Bash", {"command": "grep -rn foo js/"})], 2000, "2026-10-04T10:18:00Z"),
          a(22, [("Edit", {"file_path": "b"})], 2000, "2026-10-04T10:28:00Z")]
open(os.path.join(d, "sess26", "subagents", "agent-1.jsonl"), "w").write("\n".join(json.dumps(r) for r in helper) + "\n")
PY
o=$(echo "{\"transcript_path\":\"$SD/sess26.jsonl\",\"session_id\":\"sess26\"}" | python3 $H/stats.py | sm)
check "the token line shows main versus helpers" "main 12% · helpers 88%" "$o"
check "shell reads count as planning, git and pull requests get their own group, text-only steps are talking" "^Activity: planning 31% · coding 60% · testing 1% · git & pull requests 3% · talking 3% · other 1%" "$o"
check "the activity line lists every group that has tokens" "git & pull requests 3% · talking 3%" "$o"
check "screenshot scripts count as testing (visual checks)" "testing 1%" "$o"
check "helper time is counted once, not twice (main 8 + helper 20 = 28 min; twice would be 48)" "Time: Opus 28 min" "$o"
cat > "$T/split.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"go"}}
{"type":"assistant","message":{"id":"sp1","model":"claude-opus-5-5","role":"assistant","usage":{"input_tokens":500},"content":[{"type":"thinking","thinking":"hmm"}]}}
{"type":"assistant","message":{"id":"sp1","model":"claude-opus-5-5","role":"assistant","usage":{"input_tokens":500},"content":[{"type":"tool_use","id":"x1","name":"Edit","input":{"file_path":"a"}}]}}
{"type":"assistant","message":{"id":"sp2","model":"claude-opus-5-5","role":"assistant","usage":{"input_tokens":500},"content":[{"type":"text","text":"Done.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(echo "{\"transcript_path\":\"$T/split.jsonl\",\"session_id\":\"sp\"}" | python3 $H/stats.py | sm)
check "a step written as several records counts by its tool call, not as talking" "^Activity: coding 50% · talking 50%" "$o"
# --- v3.1.26b: plans right the first time; one session carries the whole plan
o=$(echo '{}' | python3 $H/session-start.py); check "session start gives the plan shape that passes" "Plans: write the first version in this shape" "$o"
cat > "$T/p_first.md" <<'P'
# Plan v1 — Sunday money

| Summary |
|---|
| Moves pocket money into the planner |
| First version |
| Approve it |

The kids page shows the week's money and the Sunday steps.

Stages to finish
3 stages: 2 build steps by Claude, then 1 check
1. Build the money page · Claude · Build
2. Run every test · Claude · Build
3. Try it on the iPad · You · Check

Technical details: js/money.js, saveWeek(), commit 8b56fdb.
P
o=$(pg "$T/p_first.md"); check "a first version in the given shape passes the first time" "Plan size: about" "$o"
cat > "$T/p_mention.md" <<'P'
# Plan v2 — Sunday money

| Summary |
|---|
| Moves pocket money into the planner |
| Adds the cash account, as you asked in Rev 2 |
| Approve it |

Changes in this version:
```diff
+ 🟩 Rev 2 — cash shows as its own account
```

🟩 Rev 2 — The kids page shows cash as its own account (see the Rev 2 note above).

Stages to finish
3 stages: 2 build steps by Claude, then 1 check
1. Build the money page · Claude · Build
2. Run every test · Claude · Build
3. Try it on the iPad · You · Check
P
o=$(pg "$T/p_mention.md"); check "a Rev mentioned inside a sentence needs no square" "Plan size: about" "$o"
sed 's/^🟩 Rev 2 — The kids page/Rev 2 — The kids page/' "$T/p_mention.md" > "$T/p_nosq.md"
o=$(pg "$T/p_nosq.md"); check "a Rev label at the start of a line still needs its square" "Missing on: Rev 2" "$o"
printf '# Plan v2 — X\n\nRev 2 — something changed in how the weekly money page shows the cash, the savings and the fines, with more words so the check reads it as a real plan and not a stray line of text, which is what this test needs to see.\n' > "$T/p_many.md"
o=$(pg "$T/p_many.md"); check "a sent-back plan gets every problem at once (summary, squares, changes block, stages)" "Rev N.*Summary.*Changes in this version.*Stages to finish" "$o"
check "the send-back shows the shape that passes" "The shape that passes" "$o"
o=$(echo '{"prompt":"merged, go on","session_id":"m26"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "the hand-off never asks me to open a new session" "Do not ask the user to open a new session" "$o"
printf '{"long26": 2000000}' > "$HA/.claude/state/session-tokens.json"
o=$(echo '{"prompt":"next","session_id":"long26"}' | CLAUDE_PROJECT_DIR="$HA" python3 $H/plan-gate.py)
check "a long session keeps going and stays lean instead of stopping" "Keep going without stopping, but keep this main session lean" "$o"
# --- v3.1.26c: find all, fix all, check once
o=$(echo '{}' | python3 $H/session-start.py); check "session start asks to find all problems, fix all, check once" "Find all, fix all, check once" "$o"
check "workers are told the same and report their test runs" "how many full test runs you used" "$(cat $H/../agents/opus-worker-instructions.md)"
o=$(echo "{\"transcript_path\":\"$T/act.jsonl\",\"session_id\":\"tr1\"}" | python3 $H/stats.py | sm)
check "the summary counts the test runs" "Test runs: 3" "$o"
# --- v3.1.26d: the everyday part of a plan is at most about 2 pages
python3 - "$T/p_long.md" "$T/p_long_ok.md" <<'PY'
import sys
head = "# Plan v1 — Sunday money\n\n| Summary |\n|---|\n| Moves pocket money into the planner |\n| First version |\n| Approve it |\n\n"
stages = "\nStages to finish\n2 stages: 1 build step by Claude, then 1 check\n1. Build the money page · Claude · Build\n2. Try it on the iPad · You · Check\n"
body = "The kids page shows the week's money and the Sunday steps in everyday words. " * 90
open(sys.argv[1], "w", encoding="utf-8").write(head + body + stages)
open(sys.argv[2], "w", encoding="utf-8").write(head + "The kids page shows the week's money.\n" + stages + "\nTechnical details:\n" + body)
PY
o=$(pg "$T/p_long.md"); check "an everyday part over about 2 pages is sent back" "keep it under about 6,000" "$o"
check "the send-back says to move detail, not delete it" "do not delete it" "$o"
o=$(pg "$T/p_long_ok.md"); check "long detail under Technical details is fine" "Plan size: about" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "the plan shape at session start mentions the 2-page limit" "at most about 2 pages" "$o"
# --- v3.1.26d: fewer re-reads and send-backs
# 1 rules read by shell -> refused with the Read path; setup allows Read on the rules copy
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"v=$(cat ~/.cache/hz-rules/current); cat ~/.cache/hz-rules/$v/skills/hz-plan-regression-guard/SKILL.md"}}' | python3 $H/dispatch.py)
check "a shell command reading the rules is refused before the Allow prompt" "Read the central rules with the Read tool" "$o"
check "  ...with the exact skill file to read" "hz-plan-regression-guard/SKILL.md" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"npm test"}}' | python3 $H/rules-read-guard.py)
check "other shell commands are untouched" "^$" "$o"
check "the setup allows the Read tool on the rules copy" "Read(~/.cache/hz-rules/\*\*)" "$(cat $H/../../stub/settings.json)"
check "the setup counts reads for the worker step limit" "Read|Glob|Grep|Edit" "$(cat $H/../../stub/settings.json)"
# 3 which check sent a reply back
o=$(echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"sb26\"}" | python3 $H/stats.py >/dev/null; python3 -c "
import sys;sys.path.insert(0,'$H');import os;os.environ['CLAUDE_PROJECT_DIR']='$PROJ'
from _common import bump_stat
bump_stat('sb26','sendbacks');bump_stat('sb26','sendback:validation-line');bump_stat('sb26','sendbacks');bump_stat('sb26','sendback:completion-guard')"; rm -f "$PROJ/.claude/state/version-shown.json"; echo "{\"transcript_path\":\"$T/stats.jsonl\",\"session_id\":\"sb26\"}" | python3 $H/stats.py | sm)
check "the summary says which check sent a reply back" "Send-backs: 2 (completion 1 · format 1)" "$o"
# 4 worker step limit (v3.1.28: 80 / 100; without the worker's record file the hook-call count is used)
rm -f "$PROJ/.claude/state/worker-steps.json"
wb(){ echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"Read\",\"session_id\":\"main1\",\"agent_id\":\"$1\",\"tool_input\":{}}" | python3 $H/worker-budget.py; }
for i in $(seq 1 79); do wb w1 >/dev/null; done
o=$(wb w1); check "at step 80 a worker is told to wrap up" "finish the fix you are on" "$o"
o=$(wb w1); check "step 81 runs normally" "^$" "$o"
for i in $(seq 82 100); do wb w1 >/dev/null; done
o=$(wb w1); check "after step 100 the worker must report" "Step limit reached (100)" "$o"
o=$(wb w2); check "another worker has its own count" "^$" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Read","session_id":"main1","tool_input":{}}' | python3 $H/worker-budget.py)
check "the main session is never step-limited" "^$" "$o"
# 5 workers keep memory small
check "workers read big files in parts and full screenshots only for visual comparisons" "Read large files in parts" "$(cat $H/../agents/opus-worker-instructions.md)"
# 6 evidence when a row is ticked
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"D:/x/WORKING_RECORD.md","old_string":"a","new_string":"| Plan · Stage 2 of 3 — page | COMPLETE |  |"}}' | python3 $H/record-edit-guard.py)
check "a row ticked COMPLETE without evidence is refused at the edit" "needs its Evidence in the same edit" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"D:/x/WORKING_RECORD.md","old_string":"a","new_string":"| Plan · Stage 2 of 3 — page | COMPLETE | 42/42 tests |"}}' | python3 $H/record-edit-guard.py)
check "with evidence the edit goes through" "^$" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"D:/x/js/app.js","old_string":"a","new_string":"| x | COMPLETE |  |"}}' | python3 $H/record-edit-guard.py)
check "other files are not checked" "^$" "$o"
# 7 wrong count -> notice, not send-back
printf '%s' "$(msg 'Done.
Completion: Build 2 of 4 done (50%) · Check 0 of 3
Confidence: High · Status: Checked')" > "$HC/t.jsonl"
( cd "$HCA" && git checkout -q WORKING_RECORD.md 2>/dev/null; true )
printf '{"session":"wc1","n":1}' > "$HCA/.claude/state/prompt-number.json"; rm -f "$HCA/.claude/state/completion-rounds.json"
( cd "$HCA" && sed -i 's/^- start$/- start\n- Restart: Continue Sunday recovery on branch claude\/recovery; next: Stage 5 of 7 — merge both (Check).\n- Reviewer before done (Sunday recovery): no blocking problems/' WORKING_RECORD.md && sed -i 's/| Sunday recovery · Stage 4 of 7 — draft pull requests | NOT STARTED | |/| Sunday recovery · Stage 4 of 7 — draft pull requests | COMPLETE | PR 12, PR 13 |/; s/| Sunday recovery · Stage 5 of 7 — merge both | WAITING ON YOU/| Sunday recovery · Stage 5 of 7 — merge both (Check) | WAITING ON YOU/' WORKING_RECORD.md )
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"session_id\":\"wc1\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "a wrong Completion count alone is shown in the notice, not sent back" "Completion (from the record): Completion: Build 4 of 4" "$o"
check "  ...and it is not a send-back" "clean" "$(echo "$o" | grep -c decision | sed 's/^0$/clean/')"
# 8 short chat reply without tools is not sent back
cat > "$T/hi.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hi! What would you like to work on?"}]}}
J
o=$(HZ_CHAT_REPLY_MAX_CHARS= vl "$T/hi.jsonl"); check "a short chat reply that used no tools is not sent back" "^$" "$o"
cat > "$T/hi_tools.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"check it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"z1","name":"Read","input":{}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"z1","content":"x"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Checked it, all fine."}]}}
J
o=$(HZ_CHAT_REPLY_MAX_CHARS= vl "$T/hi_tools.jsonl"); check "a reply after work (tools used) is still checked" "has no closing line" "$o"
# 2 plan size shown
o=$(pg "$T/p_first.md"); check "the plan size is shown in the notice, no send-back" "Plan size: about 1 page above Technical details" "$o"
cat > "$T/bgnote.jsonl" <<'J'
{"type":"user","message":{"role":"user","content":"build it"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"b1","name":"Agent","input":{"subagent_type":"opus-worker","run_in_background":true,"prompt":"x"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"b1","content":"started"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"The worker is building Stage 4 in the background; I'll report when it's done."}]}}
J
o=$(HZ_CHAT_REPLY_MAX_CHARS= vl "$T/bgnote.jsonl"); check "a short note while background work runs is a status, not sent back" "^$" "$o"
# --- v3.1.26e: build state first; no building while deciding; ask before building
o=$(echo '{}' | python3 $H/session-start.py); check "session start: the Result line starts with the build state" "starts with where the work stands" "$o"
check "session start: no building while I'm still deciding; ask first" "ask me first and build only after my yes" "$o"
check "the rules carry the same three rules" "Build state first; no building while I'm still deciding" "$(cat $H/../rules/CLAUDE-rules.md)"
P2="$H/../../docs/claude-ai-preferences.txt"
check "claude.ai preferences: build state in the Result line" "Start the 📌 Result line with where the build stands" "$(cat $P2)"
check "claude.ai preferences: no files while I'm deciding" "don't make files" "$(cat $P2)"
check "claude.ai preferences: ask before making the file" "make the file only after my yes" "$(cat $P2)"
check "claude.ai preferences still keep the step-writing and hz-designer lines" "ASD-STE100-lite" "$(cat $P2)"
# --- v3.1.27: queued for approval, Rev = plan version, design decisions covered, push always fine
QP="$T/q27"; rm -rf "$QP"; mkdir -p "$QP"; ( cd "$QP" && git init -q . && git config user.email t@t && git config user.name t
cat > WORKING_RECORD.md <<'R'
# WORKING RECORD

## Design decisions
- [agreed] No cash account — search: no cash account
- [agreed] Money between Sundays waits — search: Waiting for Sunday
- [open] Colour of the jar

## Deliverable ledger
| Deliverable | State | Evidence |
|---|---|---|
| Sunday v15 · Stage 1 of 4 — kids page | COMPLETE | tests |
| Sunday v15 · Stage 2 of 4 — redesigns | BLOCKED — awaiting plan approval | |
| Sunday v15 · Stage 3 of 4 — looks | WAITING ON YOU — approve Plan v9 first | |
| Sunday v15 · Stage 4 of 4 — merge (Check) | WAITING ON YOU — merge | |
R
git add -A && git commit -qm b ) >/dev/null 2>&1
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$QP" python3 -c "import sys;sys.path.insert(0,'.');from _common import *;print(completion_summary(load_config())['display'])")
check "a stage waiting for plan approval is queued, not blocked" "Stage 2 of 4 — redesigns (queued)" "$o"
check "a stage 'waiting on you' only for approval is queued, not a check" "Stage 3 of 4 — looks (queued)" "$o"
check "  ...so Build counts them as work still to come" "Completion: Build 1 of 3 done (33%) · Check 0 of 1" "$o"
cat > "$T/p27.md" <<'P'
# Plan v9 — Sunday v15

| Summary |
|---|
| Pocket money without a cash account |
| Drops cash as an account, as you asked |
| Approve it |

Changes in this version:
```diff
+ 🟦 Rev 9 — no cash account; money between Sundays shows as Waiting for Sunday
```

🟦 Rev 9 — Everything I have shows savings, locked, companies and the loan; no cash account. Waiting for Sunday holds money that arrives between meetings.

Stages to finish
3 stages: 2 build steps by Claude, then 1 check
1. Build the redesigns · Claude · Build
2. Run every test · Claude · Build
3. Try it on the iPad · You · Check
P
pg27(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','tool_input':{'plan':open(sys.argv[1],encoding='utf-8').read()}}))" "$1" | CLAUDE_PROJECT_DIR="$QP" python3 $H/dispatch.py; }
o=$(pg27 "$T/p27.md"); check "a plan with Rev = version and every agreed decision passes" "Plan size: about" "$o"
sed 's/🟦 Rev 9/🟪 Rev 8/g' "$T/p27.md" > "$T/p27_rev.md"
o=$(pg27 "$T/p27_rev.md"); check "a Rev number different from the plan version is sent back" "this is Plan v9, so its changes are marked Rev 9" "$o"
sed 's/Waiting for Sunday/Holding line/g' "$T/p27.md" > "$T/p27_miss.md"
o=$(pg27 "$T/p27_miss.md"); check "an agreed design decision missing from the plan is sent back by name" "Money between Sundays waits (search: Waiting for Sunday)" "$o"
check "  ...open points are not required" "clean" "$(echo "$o" | grep -c 'Colour of the jar' | sed 's/^0$/clean/')"
o=$(echo '{}' | python3 $H/session-start.py)
check "session start: pushing the work branch is always fine, merging stays mine" "Pushing the work branch (never main) to GitHub is always fine without asking" "$o"
check "session start: shape first, then one plan version" "the plan version does not move" "$o"
check "the rules: queued for approval, never blocked" "QUEUED — after approval" "$(cat $H/../rules/CLAUDE-rules.md)"
check "the plan shape says Rev = version" "the Rev number is the plan version" "$o"

# ---- v3.1.28
# 1 the step limit counts the worker's own record (the Sunday v15 counter saw 21 of a worker's 320 steps)
WB="$T/wb"; mkdir -p "$WB/S9/subagents"; : > "$WB/S9.jsonl"; rm -f "$PROJ/.claude/state/worker-steps.json"
wrec(){ for i in $(seq "$1" "$2"); do echo "{\"type\":\"assistant\",\"message\":{\"id\":\"m$i\",\"content\":[{\"type\":\"tool_use\",\"name\":\"Bash\",\"input\":{}}]}}"; done >> "$WB/S9/subagents/agent-w9.jsonl"; }
wb9(){ echo "{\"hook_event_name\":\"PreToolUse\",\"tool_name\":\"${2:-Read}\",\"session_id\":\"S9\",\"agent_id\":\"w9\",\"transcript_path\":\"$WB/S9.jsonl\",\"tool_input\":{}}" | python3 $H/worker-budget.py; }
wrec 1 50; o=$(wb9 x); check "a worker at step 50 of its record works on" "^$" "$o"
wrec 51 83; o=$(wb9 x); check "the first checked call after step 80 of the record says wrap up (shell steps counted too)" "Step 83 of this worker run" "$o"
wrec 84 90; o=$(wb9 x); check "the wrap-up notice comes once" "^$" "$o"
echo "{\"type\":\"assistant\",\"message\":{\"id\":\"m90\",\"content\":[{\"type\":\"tool_use\",\"name\":\"Read\",\"input\":{}}]}}" >> "$WB/S9/subagents/agent-w9.jsonl"
check "several records of one step count once" "\"steps\": 90" "$(cat "$PROJ/.claude/state/worker-steps.json"; wb9 x >/dev/null; cat "$PROJ/.claude/state/worker-steps.json")"
wrec 91 101; o=$(wb9 x); check "past step 100 of the record the worker must report" "Step limit reached (100)" "$o"
o=$(wb9 x SubagentHandback); check "the worker's own hand-back is never refused" "^$" "$o"
check "the counter records which tools reach it and where the count came from" "\"source\": \"record\"" "$(cat "$PROJ/.claude/state/worker-steps.json")"
# 2 test runs: only commands that run something; reading test files and logs is not a test run
cat > "$T/tr28.jsonl" <<J
{"type":"user","message":{"role":"user","content":"check it"}}
{"type":"assistant","message":{"id":"t1","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"cd \"D:/x\" && grep -n \"want('a')\" tests/smoke.js | head"}}]}}
{"type":"assistant","message":{"id":"t2","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"tail -5 smoke-run.log"}}]}}
{"type":"assistant","message":{"id":"t3","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"cd \"D:/x\"; npm test 2>&1 | tail -3"}}]}}
{"type":"assistant","message":{"id":"t4","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"SMOKE_ONLY=a node tests/smoke.js"}}]}}
{"type":"assistant","message":{"id":"t5","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"git commit -m \"smoke rewrite\""}}]}}
{"type":"assistant","message":{"id":"t6","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Bash","input":{"command":"sleep 60 && tail -5 run.log"}}]}}
{"type":"assistant","isSidechain":true,"message":{"id":"h1","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Read","input":{}},{"type":"tool_use","name":"Read","input":{}}]}}
{"type":"assistant","isSidechain":true,"message":{"id":"h2","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"tool_use","name":"Read","input":{}}]}}
{"type":"assistant","message":{"id":"t7","model":"claude-opus-5-5","usage":{"input_tokens":10,"output_tokens":1},"content":[{"type":"text","text":"done\\n\\nConfidence: High · Status: Checked"}]}}
J
o=$(rm -f "$PROJ/.claude/state/version-shown.json"; echo "{\"transcript_path\":\"$T/tr28.jsonl\",\"session_id\":\"tr28\"}" | python3 $H/stats.py | sm)
check "reading test files or logs is not a test run; npm test and node tests/… are" "Test runs: 2 " "$o"
check "the summary shows the share of worker steps with one tool call" "Worker steps: 2 · one tool call per step: 50%" "$o"
check "a step that only waits is counted as waiting" "waiting" "$o"
# 3 a difference from the prototype is asked with pictures
mkdev(){ printf '%s\n' "{\"type\":\"user\",\"message\":{\"role\":\"user\",\"content\":\"compare\"}}" "{\"type\":\"assistant\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"tool_use\",\"name\":\"Read\",\"input\":{}}]}}" > "$T/dev.jsonl"
  python3 -c "import json,sys;print(json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':sys.argv[1]}]}}))" "$1" >> "$T/dev.jsonl"; }
DEVTXT='Two things differ from the build.

Confidence: High · Status: Checked

❓ Decisions
- 1. The goal card has a ⋯ button the reference doesn'"'"'t have — keep it (only way to pick the goal).

---
> 📌 **Result:** Waiting on your decision.
> 👉 **I need from you:** answer decision 1.
> ➡️ **Next:** I finish the screens.'
mkdev "$DEVTXT"
o=$(echo "{\"transcript_path\":\"$T/dev.jsonl\",\"session_id\":\"dv\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; })
check "a difference question without pictures is sent back" "show the prototype and the build side by side" "$o"
mkdev "Comparison page: https://claude.ai/artifact/abc
$DEVTXT"
o=$(echo "{\"transcript_path\":\"$T/dev.jsonl\",\"session_id\":\"dv\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/format-rounds.json"; python3 $H/validation-line.py; })
check "with a link to the comparison page it passes" "^$" "$o"
# 4 the condensed rules lose no rule, and stay within 24,000 characters
RC="$H/../../tools/rules-coverage.txt"; R="$H/../rules/CLAUDE-rules.md"
miss=$(python3 - "$RC" "$H/../.." <<'PY'
import sys, os
root = sys.argv[2]
F = {"R": "central/rules/CLAUDE-rules.md", "C": "CLAUDE.md", "D": "docs/model-guidance-sources.md", "T": "central/hooks/_common.py"}
txt = {k: open(os.path.join(root, v), encoding="utf-8").read() for k, v in F.items()}
n = bad = 0
for l in open(sys.argv[1], encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    rule, f, ph = [x.strip() for x in l.rstrip("\n").split(" | ", 2)]
    n += 1
    if ph not in txt[f]:
        bad += 1
        print("missing:", rule)
print(f"{n} rules, {bad} missing")
PY
)
check "every rule of the old rules text is still there (coverage list)" " 0 missing" "$miss"
check "  ...and the list covers at least 160 rules" "^1[6-9][0-9] rules\|^[2-9][0-9][0-9] rules" "$(echo "$miss" | tail -1)"
check "the rules are at most 25,000 characters" "ok" "$(python3 -c "import sys;print('ok' if len(open(sys.argv[1],encoding='utf-8').read())<=25000 else 'too long')" "$R")"
# 5 the new rules are in the rules, the worker instructions and the session start
check "the rules: one-line answer to a new-session suggestion" "Restart: yes — use the restart line" "$(cat $R)"
check "the rules: prototype and build side by side" "prototype and build side by side" "$(cat $R)"
check "worker instructions: several files in one step" "Read all the files or parts you need in one step" "$(cat $H/../agents/opus-worker-instructions.md)"
check "worker instructions: no waiting loops" "No waiting loops" "$(cat $H/../agents/opus-worker-instructions.md)"
check "worker instructions: step 80 / 100" "Around step 80" "$(cat $H/../agents/opus-worker-instructions.md)"
o=$(echo '{}' | python3 $H/session-start.py); check "session start: differences come with a side-by-side page" "prototype and build side by side" "$o"
o=$(echo '{"prompt":"merged, move on"}' | python3 $H/plan-gate.py)
check "after a merge the session is never told to suggest a new session" "clean" "$(echo "$o" | grep -c 'suggest a fresh session' | sed 's/^0$/clean/')"
# 6 writing for me in ASD-STE100-lite (user test 2026-10-05: the STE answers read better)
check "the rules carry the STE-lite writing block" "Writing for me (ASD-STE100-lite)" "$(cat $R)"
check "the plan summary starts with what changes for me" "What changes for you" "$(echo '{}' | python3 $H/session-start.py)"
check "the claude.ai preferences carry the same STE-lite block" "Accuracy is more important than style." "$(cat $H/../../docs/claude-ai-preferences.txt)"
check "the claude.ai preferences ask for prototype and build side by side" "show the prototype and the build side by side" "$(cat $H/../../docs/claude-ai-preferences.txt)"
# 7 explorer and reviewer on call (v3.1.28)
o=$(wg opus-worker "Task: Fix sync
Level: Complex
find why"); check "a Complex hand-over without a map is refused" "carries a map" "$o"
o=$(wg opus-worker "Task: Fix sync
Level: Complex
Map: not needed — one line in a file named by the user"); check "  ...with 'Map: not needed — reason' it passes" "^$" "$o"
o=$(wg Explore "Where is the sync code?"); check "the explorer may run" "^$" "$o"
o=$(wg reviewer "Moment: Before done"); check "the reviewer may run" "^$" "$o"
check "the reviewer only reads" "tools: Read, Grep, Glob" "$(cat $H/../../stub/reviewer.md)"
check "the explorer runs on Sonnet 5.5" "model: claude-sonnet-5-5" "$(cat $H/../../stub/explore.md)"
check "the explorer overrides the built-in Explore" "name: Explore" "$(cat $H/../../stub/explore.md)"
cat > "$T/stuck.jsonl" <<J
{"type":"user","message":{"role":"user","content":"go on"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"w1","name":"Agent","input":{"subagent_type":"opus-worker","prompt":"Task: a"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"w1","content":"Stuck: smoke test money — still fails — tried two fixes"}]}}
J
wgs(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'Agent','session_id':'st9','transcript_path':sys.argv[1],'tool_input':{'subagent_type':'opus-worker','prompt':'Task: a\nLevel: Complex\nMap: js/a.js'}}))" "$1" | python3 $H/dispatch.py; }
o=$(wgs "$T/stuck.jsonl"); check "after 'Stuck:' the next worker is refused until the reviewer ran" "Send the reviewer first" "$o"
cp "$T/stuck.jsonl" "$T/stuck2.jsonl"
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"r1","name":"Agent","input":{"subagent_type":"reviewer","prompt":"Moment: Stuck"}}]}}' >> "$T/stuck2.jsonl"
o=$(wgs "$T/stuck2.jsonl"); check "  ...after the reviewer the next worker goes out" "^$" "$o"
o=$(echo '{"prompt":"find the root cause of the sync bug and redesign the data model","session_id":"rv1"}' | python3 $H/plan-gate.py)
check "a big or risky plan asks for the reviewer first" "Big or risky plan: before presenting it" "$o"
cat > "$T/planrv.jsonl" <<J
{"type":"user","message":{"role":"user","content":"find the root cause of the sync bug and redesign the data model"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"drafting"}]}}
J
pgr(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','session_id':'rv1','transcript_path':sys.argv[1],'tool_input':{'plan':open(sys.argv[2],encoding='utf-8').read()}}))" "$1" "$T/plan_good.md" | python3 $H/dispatch.py; }
o=$(pgr "$T/planrv.jsonl"); check "  ...and the plan check refuses it without the reviewer" "send the reviewer" "$o"
echo '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"r2","name":"Agent","input":{"subagent_type":"reviewer","prompt":"Moment: Before a plan"}}]}}' >> "$T/planrv.jsonl"
o=$(pgr "$T/planrv.jsonl"); check "  ...after the reviewer the plan goes out" "clean" "$(echo "$o" | grep -c 'send the reviewer' | sed 's/^0$/clean/')"
o=$(echo '{"prompt":"rename the save button","session_id":"rv2"}' | python3 $H/plan-gate.py)
check "a small request does not ask for the reviewer" "clean" "$(echo "$o" | grep -c '\[reviewer\]' | sed 's/^0$/clean/')"
( cd "$HCA" && sed -i '/^- Reviewer before done (Sunday recovery)/d' WORKING_RECORD.md )
rm -f "$HCA/.claude/state/completion-rounds.json"
o=$(echo "{\"transcript_path\":\"$HC/t.jsonl\",\"session_id\":\"wc1\",\"stop_hook_active\":false}" | CLAUDE_PROJECT_DIR="$HCA" python3 $H/completion-guard.py)
check "at Build 100% without the reviewer's check, the session is sent to the reviewer" "Before done: send the reviewer" "$o"
SU="$T/stub27"; rm -rf "$SU"; mkdir -p "$SU/.claude/agents"
cp "$H/../../stub/settings.json" "$SU/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$SU/.claude/agents/"; cp "$H/../../stub/hz-loader.py" "$SU/.claude/"; cp "$H/../../stub/CLAUDE-pointer.md" "$SU/CLAUDE.md"
o=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubcheck import stub_status;print(stub_status(load_config(),'$SU'))")
check "an app without the two new helpers shows its setup as outdated" "OUTDATED.*reviewer on call" "$o"
( cd "$SU" && git init -q -b main . && git config user.email t@t && git config user.name t && git add -A && git commit -qm base && git init -q --bare "$T/stub27.git" && git remote add origin "$T/stub27.git" && git push -q origin main )
o=$(cd "$H" && CLAUDE_PROJECT_DIR="$SU" python3 -c "import sys;sys.path.insert(0,'.');from _common import load_config;from stubupdate import update;print(update(load_config(),'$SU'))")
check "the self-update adds the reviewer" "reviewer" "$(ls "$SU/.claude/agents/")"
check "the self-update adds the explorer" "explore.md" "$(ls "$SU/.claude/agents/")"
check "worker instructions: report Stuck after two tries" "Stuck: <check>" "$(cat $H/../agents/opus-worker-instructions.md)"
check "worker instructions: start from the map" "Start from the map" "$(cat $H/../agents/opus-worker-instructions.md)"
o=$(echo '{}' | python3 $H/session-start.py); check "session start names the explorer and reviewer instructions" "Reviewer instructions:" "$o"
# --- v3.1.29: real Weekly-Planner replies (PR 114 session): a note after Status passes; a send-back asks only for what failed
mkt(){ python3 -c "
import json,sys
print(json.dumps({'type':'user','message':{'role':'user','content':'is there another request'}}))
print(json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'tool_use','name':'Bash','input':{'command':'gh pr list'}}]}}))
print(json.dumps({'type':'user','message':{'role':'user','content':[{'type':'tool_result','content':'ok'}]}}))
print(json.dumps({'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':sys.argv[1]}]}}))" "$1" > "$2"; }
mkt $'No, don\'t create a new pull request.\n\nConfidence: Medium · Status: Checked. I\'m not sure which prompt you\'re seeing.\n---\n> 📌 **Result:** The setup update is merged.\n> 👉 **I need from you:** Use Pull origin in GitHub Desktop.\n> ➡️ **Next:** I am ready for your request.' "$T/v129_note.jsonl"
o=$(vl "$T/v129_note.jsonl"); check "v3.1.29: a short note after Status passes (real reply)" "^$" "$o"
mkt $'Ready to merge.\n\nConfidence: High · Status: Checked — PR checked on GitHub\n---\n> 📌 **Result:** Ready to merge.\n> 👉 **I need from you:** Merge it.\n> ➡️ **Next:** New setup next session.' "$T/v129_dash.jsonl"
o=$(vl "$T/v129_dash.jsonl"); check "v3.1.29: a note after a dash passes for Checked" "^$" "$o"
mkt $'📌 Result: Ready to merge. The setup update is pushed.\nI need from you: please merge pull request 114.\nConfidence: High · Status: Checked' "$T/v129_badblock.jsonl"
o=$(vl "$T/v129_badblock.jsonl"); check "v3.1.29: a bad closing block is sent back (real reply)" '"decision": "block"' "$o"
check "v3.1.29: the re-send skips a validation line that was already right" "do not repeat the validation line" "$o"
mkt $'Merged.\n---\n> 📌 **Result:** Merged.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** Ready.' "$T/v129_noline.jsonl"
o=$(vl "$T/v129_noline.jsonl"); check "v3.1.29: only the validation line missing -> send back" '"decision": "block"' "$o"
check "v3.1.29: the re-send is only the validation line" "Send only the validation line" "$o"
o=$(cd "$H" && python3 -c "
import re,sys;sys.path.insert(0,'.')
from _common import load_config
p=load_config()['validation_line_pattern']
for s in ['Confidence: High · Status: Checked — PR checked','Confidence: Low · Status: Proposed','Confidence: High · Status: Validated — npm test 4/4','Confidence: High · Status: Checked.','Confidence: High · Status: Checkedx','Confidence: High · Status: Done']:
  m=re.search(p,s); print(m.group(2).split()[0] if m else 'none')" | tr '\n' ' ')
check "v3.1.29: the status word is read the same way by every check" "^Checked Proposed Validated Checked none none $" "$o"
check "v3.1.29: rules allow a short note after any status" "a short note after" "$(cat $H/../rules/CLAUDE-rules.md)"
# --- v3.1.29: session start stays under Claude Code's 10,000-character cut; the main session reads the rules first
o=$(echo '{"session_id":"rf1"}' | python3 $H/session-start.py)
n=$(printf '%s' "$o" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['hookSpecificOutput']['additionalContext']))")
check "v3.1.29: session start text is under 10,000 characters ($n)" "yes" "$([ "$n" -lt 10000 ] && echo yes || echo no)"
check "v3.1.29: session start no longer carries the rules text" "clean" "$(echo "$o" | grep -c 'Global Working Rules' | sed 's/^0$/clean/')"
check "v3.1.29: session start keeps the loaded line the pointer looks for" "\[session-start\] Rules v" "$o"
check "v3.1.29: session start names the rules file to read first" "FIRST, before any other tool or reply: read the full working rules" "$o"
check "v3.1.29: the closing block format is inside the first 10,000 characters" "I need from you" "$o"
rg(){ echo "$1" | HZ_RULES_FIRST_OFF= python3 $H/rules-first-guard.py; }
RP=$(cd "$H" && python3 -c "import sys;sys.path.insert(0,'.');from _common import RULES_PATH;print(RULES_PATH)")
o=$(rg '{"session_id":"rf1","tool_name":"Bash","tool_input":{"command":"git status"}}'); check "v3.1.29: a command before the rules are read is refused with the path" "Read the working rules first" "$o"
o=$(rg '{"session_id":"rf1","tool_name":"Grep","tool_input":{"pattern":"x"}}'); check "v3.1.29: searching is allowed before the rules are read" "^$" "$o"
o=$(rg '{"session_id":"rf1","tool_name":"Edit","agent_id":"w1","tool_input":{"file_path":"a.js"}}'); check "v3.1.29: a worker is never stopped by the rules-first check" "^$" "$o"
o=$(rg "{\"session_id\":\"rf1\",\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$RP\"}}"); check "v3.1.29: reading the rules file is allowed" "^$" "$o"
o=$(rg '{"session_id":"rf1","tool_name":"Bash","tool_input":{"command":"git status"}}'); check "v3.1.29: after the rules are read, commands pass" "^$" "$o"
o=$(rg '{"session_id":"rf2","tool_name":"Bash","tool_input":{"command":"git status"}}'); check "v3.1.29: a new session must read the rules again" "Read the working rules first" "$o"
o=$(rg '{"session_id":"rf3","tool_name":"Read","tool_input":{"file_path":"C:\\Users\\h\\.cache\\hz-rules\\3.1.29\\rules\\CLAUDE-rules.md"}}'); o=$(rg '{"session_id":"rf3","tool_name":"Bash","tool_input":{"command":"ls"}}'); check "v3.1.29: a Windows path to the rules counts as read" "^$" "$o"
echo '{"session_id":"rf3"}' | python3 $H/session-start.py >/dev/null
o=$(rg '{"session_id":"rf3","tool_name":"Bash","tool_input":{"command":"ls"}}'); check "v3.1.29: a new session start (or /compact) asks for the rules again" "Read the working rules first" "$o"
o=$(echo '{"session_id":"rf4","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"ls"}}' | HZ_RULES_FIRST_OFF= python3 $H/dispatch.py PreToolUse); check "v3.1.29: the switchboard runs the rules-first check" "Read the working rules first" "$o"
rm -f "$PROJ/.claude/state/rules-read.json"
python3 -c "import json;p='$H/config.json';d=json.load(open(p));d['session_start_max_chars']=1500;json.dump(d,open(p,'w'))"
o=$(echo '{"session_id":"rf5"}' | python3 $H/session-start.py)
n=$(printf '%s' "$o" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['hookSpecificOutput']['additionalContext']))")
check "v3.1.29: over the limit, the facts move to a file instead of being cut ($n)" "yes" "$([ "$n" -lt 1500 ] && echo yes || echo no)"
check "v3.1.29: ...and the session is told to read that file" "session-facts.md" "$o"
check "v3.1.29: ...and the facts file holds the closing block format" "I need from you" "$(cat "$PROJ/.claude/state/session-facts.md")"
cp "$T/config.bak" "$H/config.json"
# --- v3.1.30 batch 1 (safety): pull request last, back to draft, ready at the end, no waiting, background time limit
mk130(){ python3 - "$@" <<'PYEOF'
import json, sys
out, spec = sys.argv[1], sys.argv[2:]
recs, n = [{"type":"user","message":{"role":"user","content":"go"}}], 0
def tu(name, inp, done=True):
    global n; n += 1; i = f"t{n}"
    recs.append({"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":i,"name":name,"input":inp}]}})
    if done: recs.append({"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":i,"content":"ok"}]}})
for s in spec:
    k, _, v = s.partition(":")
    if k in ("worker","reviewer"): tu("Agent", {"subagent_type": "opus-worker" if k=="worker" else "reviewer", "prompt": "x"})
    elif k == "running": tu("Agent", {"subagent_type": "opus-worker", "prompt": "x"}, done=False)
    elif k == "bash": tu("Bash", {"command": v})
    elif k == "text": recs.append({"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":v}]}})
open(out,"w").write("\n".join(json.dumps(r) for r in recs)+"\n")
PYEOF
}
gpr(){ python3 -c "import json,sys;print(json.dumps({'tool_name':'Bash','transcript_path':sys.argv[1],'tool_input':{'command':sys.argv[2]}}))" "$1" "$2" | python3 $H/git-guard.py; }
gmcp(){ python3 -c "import json,sys;print(json.dumps({'tool_name':sys.argv[2],'transcript_path':sys.argv[1],'tool_input':json.loads(sys.argv[3])}))" "$1" "$2" "$3" | python3 $H/git-guard.py; }
mk130 "$T/b1a.jsonl" worker:; o=$(gpr "$T/b1a.jsonl" "gh pr create --title x --body y"); check "v3.1.30: no pull request after a worker without the reviewer" "open the pull request last" "$o"
mk130 "$T/b1b.jsonl" worker: reviewer:; o=$(gpr "$T/b1b.jsonl" "gh pr create --title x --body y"); check "v3.1.30: pull request allowed after worker then reviewer" "^$" "$o"
mk130 "$T/b1c.jsonl" worker: reviewer: running:; o=$(gpr "$T/b1c.jsonl" "git push -u origin claude/x && gh pr create --fill"); check "v3.1.30: no pull request while a worker runs (real PR 118 order)" "still running" "$o"
mk130 "$T/b1d.jsonl" bash:"git status"; o=$(gpr "$T/b1d.jsonl" "gh pr create --fill"); check "v3.1.30: a setup pull request with no workers passes" "^$" "$o"
o=$(gmcp "$T/b1a.jsonl" mcp__github__create_pull_request '{"title":"x"}'); check "v3.1.30: the GitHub tool follows pull request last too" "open the pull request last" "$o"
o=$(gmcp "$T/b1b.jsonl" mcp__github__update_pull_request '{"pullNumber":118,"draft":true}'); check "v3.1.30: switching an open pull request back to draft is allowed" "^$" "$o"
o=$(gmcp "$T/b1b.jsonl" mcp__github__create_pull_request '{"title":"x","draft":true}'); check "v3.1.30: opening a new pull request as a draft is still refused" "not as drafts" "$o"
wpr(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'Agent','session_id':'b1','transcript_path':sys.argv[1],'tool_input':{'subagent_type':'opus-worker','prompt':sys.argv[2]}}))" "$1" "$2" | python3 $H/worker-guard.py; }
HO=$'Task: PR 4 fix pass\nLevel: Complex\nMap: js/21-money-data.js lines 1600-1700\nfix the gaps'
# v3.1.30: open pull requests are tracked by branch (git-guard marks them); a merged one on an old branch never blocks
git switch -q -c claude/pr118 2>/dev/null || git checkout -q -b claude/pr118
gs(){ python3 -c "import json,sys;print(json.dumps({'tool_name':'Bash','session_id':'b1','transcript_path':sys.argv[1],'tool_input':{'command':sys.argv[2]}}))" "$1" "$2" | python3 $H/git-guard.py; }
mk130 "$T/b1e.jsonl" worker: reviewer:; gs "$T/b1e.jsonl" "gh pr create --fill" >/dev/null
check "v3.1.30: opening a pull request marks its branch ready" '"claude/pr118": "ready"' "$(cat $PROJ/.claude/state/pr-branches.json)"
o=$(wpr "$T/b1e.jsonl" "$HO"); check "v3.1.30: a fix worker on the branch of a ready pull request is refused (real PR 118 case)" "Switch it back to draft first" "$o"
o=$(wpr "$T/b1e.jsonl" $'PR: #118 merged\n'"$HO"); check "v3.1.30: a merged pull request does not block the next worker" "^$" "$o"
o=$(wpr "$T/b1e.jsonl" $'PR: #118 not touched\n'"$HO"); check "v3.1.30: a worker that leaves the branch alone may say so" "^$" "$o"
gs "$T/b1e.jsonl" "gh pr ready 118 --undo" >/dev/null
check "v3.1.30: back to draft is recorded" '"claude/pr118": "draft"' "$(cat $PROJ/.claude/state/pr-branches.json)"
o=$(wpr "$T/b1e.jsonl" "$HO"); check "v3.1.30: after back to draft the fix worker may start" "^$" "$o"
FINAL=$'Fixed.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Ready to merge.\n> 👉 **I need from you:** Merge 118.\n> ➡️ **Next:** done.'
mk130 "$T/b1g.jsonl" worker: reviewer: text:"$FINAL"
o=$(echo "{\"transcript_path\":\"$T/b1g.jsonl\",\"session_id\":\"b1\"}" | python3 $H/pr-ready-guard.py); check "v3.1.30: a final answer with the pull request still in draft is sent back" "still a draft" "$o"
gs "$T/b1e.jsonl" "gh pr ready 118" >/dev/null
o=$(echo "{\"transcript_path\":\"$T/b1g.jsonl\",\"session_id\":\"b1\"}" | python3 $H/pr-ready-guard.py); check "v3.1.30: marked ready again -> the final answer passes" "^$" "$o"
git switch -q -c claude/next-stage 2>/dev/null || git checkout -q -b claude/next-stage
o=$(wpr "$T/b1e.jsonl" "$HO"); check "v3.1.30: the next stage on a new branch is not blocked by an earlier pull request (real session: 14 workers)" "^$" "$o"
git checkout -q - ; git checkout -q - 2>/dev/null; git checkout -q master 2>/dev/null || git checkout -q main 2>/dev/null
rm -f "$PROJ/.claude/state/pr-branches.json"
wt(){ python3 -c "import json,sys;print(json.dumps({'tool_name':'Bash','tool_input':{'command':sys.argv[1],'run_in_background':sys.argv[2]=='bg'}}))" "$1" "$2" | python3 $H/wait-guard.py; }
o=$(wt "sleep 30 && cat out.txt" fg); check "v3.1.30: sleep 30 is refused" "No waiting commands" "$o"
o=$(wt "sleep 2 && npm test" fg); check "v3.1.30: a short sleep of 2 seconds passes" "^$" "$o"
o=$(wt 'until grep -q "DONE" .claude/state/worker.log; do sleep 20; done' fg); check "v3.1.30: a wait-for-the-worker loop is refused" "No waiting commands" "$o"
o=$(wt "tail -f .claude/state/worker.log" fg); check "v3.1.30: tail -f is refused" "No waiting commands" "$o"
o=$(wt "npm test" bg); check "v3.1.30: a background command without a time limit is refused" "needs a time limit" "$o"
o=$(wt "timeout 1800 npm test" bg); check "v3.1.30: a background command with timeout 1800 passes" "^$" "$o"
o=$(wt "timeout 3h npm test" bg); check "v3.1.30: a time limit over 30 minutes is refused" "needs a time limit" "$o"
REAL11=$'cd "/d/User/Heng Z/Documents/GitHub/Weekly-Planner" && python - <<\'EOF\' 2>/dev/null || python3 - <<\'EOF2\'\nimport re\np=\'js/21-money-data.js\'\nEOF\nimport re\nEOF2\nsed -n 1660,1695p js/21-money-data.js; git diff --stat | tail -1'
o=$(wt "$REAL11" bg); check "v3.1.30: the real 11 h 49 m background script is refused without a limit" "needs a time limit" "$o"
o=$(wt $'python3 - <<\'EOF\'\nimport time\n# sleep 60 here is text, not a command\nEOF' fg); check "v3.1.30: text inside a here-document is not a waiting command" "^$" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"sleep 60"}}' | python3 $H/dispatch.py PreToolUse); check "v3.1.30: the switchboard runs the waiting check" "No waiting commands" "$o"
# --- v3.1.30 batch 2 (compare): compare and conversion instructions, Proof line, by-screen list, skill names
A="$H/../agents"
o=$(echo '{"session_id":"b2s"}' | python3 $H/session-start.py)
check "v3.1.30: session start names the compare instructions" "compare-instructions.md" "$o"
n=$(printf '%s' "$o" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['hookSpecificOutput']['additionalContext']))")
check "v3.1.30: session start still under 10,000 characters ($n)" "yes" "$([ "$n" -lt 10000 ] && echo yes || echo no)"
C=$(cat "$A/compare-instructions.md")
check "v3.1.30: compare: three screen sizes" "phone 390×844, iPad 820×1180, PC 1440×900" "$C"
check "v3.1.30: compare: in code, unchanged screens not opened" "Do not open pictures of screens that did not change" "$C"
check "v3.1.30: compare: figures the app names in its References" "the values the app shows for the same inputs before the change" "$C"
check "v3.1.30: compare: unplanned change is a bug" "An unplanned change is a bug" "$C"
check "v3.1.30: compare: unapproved difference becomes a picture pair" "mockup and build side by side, numbered" "$C"
check "v3.1.30: compare: the Proof line" "Proof: pictures <n> screens × 3 sizes" "$C"
V=$(cat "$A/conversion-instructions.md")
check "v3.1.30: conversion: coverage list first" "features-coverage.txt" "$V"
check "v3.1.30: conversion: history to docs/archive" "move to \`docs/archive/\`" "$V"
check "v3.1.30: conversion: ARCHITECTURE rules marked" "checked by <script>" "$V"
check "v3.1.30: conversion: rule documents to tests" "names the test that proves it" "$V"
check "v3.1.30: conversion: database rules test only after the tool runs" "only after the test tool is shown to run" "$V"
check "v3.1.30: conversion: the app names its own references" "Add \`## References\` to \`FEATURES.md\`" "$V"
O=$(grep -n -i -E "money|allowance|family rules|weekly-planner|data-owner" "$H/../rules/CLAUDE-rules.md" "$A"/*.md "$H/../seed/FEATURES.md" | head -3)
check "v3.1.30: central rules, instructions and seed stay general (no app-specific words)" "^$" "$O"
check "v3.1.30: the seed list has a References section for app-specific checks" "## References" "$(cat $H/../seed/FEATURES.md)"
check "v3.1.30: worker instructions point to the compare instructions" "follow \`compare-instructions.md\`" "$(cat $A/opus-worker-instructions.md)"
check "v3.1.30: reviewer blocks a missing Proof line before the pull request" "a missing or partial Proof line blocks" "$(cat $A/reviewer-instructions.md)"
check "v3.1.30: the seed list is by screen" "feature-list: by-screen" "$(cat $H/../seed/FEATURES.md)"
check "v3.1.30: the seed list is still seen as the unfilled template" "<app or plan name>" "$(cat $H/../seed/FEATURES.md)"
mkrg(){ python3 - "$1" "$2" "$PROJ" <<'PYEOF'
import json,sys
out,kept,proj=sys.argv[1:4]
txt="Done.\n\n| Regression table | Result |\n|---|---|\n| Kept | "+kept+" |\n| Added | none |\n| Intentionally removed | none |\n| Missing | none |\n\nConfidence: High · Status: Checked"
R=[{"type":"user","message":{"role":"user","content":"fix the bug"}},
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"e1","name":"Edit","input":{"file_path":proj+"/js/app.js"}}]}},
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"e1","content":"ok"}]}},
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"e2","name":"Edit","input":{"file_path":proj+"/WORKING_RECORD.md"}}]}},
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"e2","content":"ok"}]}},
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":txt}]}}]
open(out,"w").write("\n".join(json.dumps(r) for r in R)+"\n")
PYEOF
}
rgx(){ echo "{\"transcript_path\":\"$1\",\"stop_hook_active\":false}" | { rm -f "$PROJ/.claude/state/record-rounds.json"; python3 $H/record-guard.py; }; }
cp FEATURES.md "$T/features.bak"
printf '<!-- feature-list: by-screen -->\n# FEATURES — test app — manifest v2\n## Today\n- login — Proof: smoke login\n' > FEATURES.md
mkrg "$T/rg1.jsonl" "41 features"; o=$(rgx "$T/rg1.jsonl"); check "v3.1.30: by-screen list: Kept without proof is sent back" "Kept row names its proof" "$o"
mkrg "$T/rg2.jsonl" "41 features · Proof: pictures 9 screens × 3 sizes, 2 changed (all planned) · tests 120/120"; o=$(rgx "$T/rg2.jsonl"); check "v3.1.30: by-screen list: Kept with proof passes" "^$" "$o"
cp "$T/features.bak" FEATURES.md
o=$(rgx "$T/rg1.jsonl"); check "v3.1.30: a list not converted yet works as before" "^$" "$o"
o=$(grep -rnE "hz-(outcome-audit|web-app-audit|task-planner|sql-excel-auditor)" "$H/../rules" "$H/../agents" "$H/../skills" "$H/skill-router.json" | grep -v "were merged into" | head -3)
check "v3.1.30: no central file sends work to a retired skill" "^$" "$o"
check "v3.1.30: the manifest lists the compare instructions" "agents/compare-instructions.md" "$(cat $H/../MANIFEST.txt)"
check "v3.1.30: the manifest lists the conversion instructions" "agents/conversion-instructions.md" "$(cat $H/../MANIFEST.txt)"
check "v3.1.30: the manifest lists the new checks" "hooks/wait-guard.py" "$(grep -E 'wait-guard|pr-ready-guard' $H/../MANIFEST.txt | tr '\n' ' ')"
# --- v3.1.30 batch 3: from the real 3.1.29 Weekly-Planner money session (4b4ef8bd, 5 pull requests)
o=$(wt "sleep 590; echo waited" bg); check "v3.1.30 real: the main session's 'Wait for the PR 4 fix-pass worker' timer is refused (62 such in the session)" "No waiting commands" "$o"
o=$(wt "sleep 120; echo waited" bg); check "v3.1.30 real: 'Wait two minutes for the explorers' is refused" "No waiting commands" "$o"
NOTE=$'<task-notification>\n<task-id>af2dce1f14543ecec</task-id>\n<tool-use-id>toolu_01EQ7gDRMLSiEyW1Vod1NAQE</tool-use-id>\n<status>completed</status>\n<summary>Agent "Verify copy, flow and old-screen claims" finished</summary>\n</task-notification>'
o=$(python3 -c "import json,sys;print(json.dumps({'session_id':'n1','prompt':sys.argv[1]}))" "$NOTE" | python3 $H/plan-gate.py); check "v3.1.30 real: a worker notice gets no plan-gate text (79 of 106 in the session)" "^$" "$o"
o=$(python3 -c "import json,sys;print(json.dumps({'session_id':'n1','prompt':sys.argv[1]}))" "$NOTE" | python3 $H/skill-router.py); check "v3.1.30 real: a worker notice gets no skill-router text" "^$" "$o"
o=$(python3 -c "import json,sys;print(json.dumps({'session_id':'n1','prompt':'Fix the money page layout and logic, all of it'}))" | python3 $H/plan-gate.py); check "v3.1.30: a real request still gets the plan-gate text" "plan-gate" "$o"
python3 - "$T/async.jsonl" "$NOTE" <<'PYEOF'
import json,sys
out,note=sys.argv[1],sys.argv[2]
R=[{"type":"user","message":{"role":"user","content":"go"}},
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"toolu_01EQ7gDRMLSiEyW1Vod1NAQE","name":"Agent","input":{"subagent_type":"opus-worker","prompt":"x"}}]}},
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_01EQ7gDRMLSiEyW1Vod1NAQE","content":[{"type":"text","text":"Async agent launched successfully. The agent is working in the background."}]}]}},
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"r1","name":"Agent","input":{"subagent_type":"reviewer","prompt":"x"}}]}},
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"r1","content":"Verdict: no blocking problems"}]}}]
open(out,"w").write("\n".join(json.dumps(r) for r in R)+"\n")
open(out.replace(".jsonl","-done.jsonl"),"w").write("\n".join(json.dumps(r) for r in R+[{"type":"user","message":{"role":"user","content":note}}])+"\n")
PYEOF
o=$(gpr "$T/async.jsonl" "gh pr create --fill"); check "v3.1.30 real: a background worker that only says 'launched' still counts as running" "still running" "$o"
o=$(gpr "$T/async-done.jsonl" "gh pr create --fill"); check "v3.1.30 real: its 'completed' notice ends it" "^$" "$o"
o=$(wt 'cd "/d/User/Heng Z/Documents/GitHub/Weekly-Planner" && SMOKE_CHROMIUM="C:/Program Files/Google/Chrome/Application/chrome.exe" npm run test:smoke > "$T/smoke.txt" 2>&1' bg); check "v3.1.30 real: the background smoke run without a limit is refused" "needs a time limit" "$o"
o=$(wt 'cd "/d/User/Heng Z/Documents/GitHub/Weekly-Planner"; export SMOKE_CHROMIUM="C:/Program Files/Google/Chrome/Application/chrome.exe"; timeout 1500 npm run test:smoke > out.txt' bg); check "v3.1.30 real: a limit after cd and settings passes (a worker's real form)" "^$" "$o"
# --- v3.1.30 batch 4: planner helper with fallback, main-session model notice, ready-to-merge notice
ST="$H/../../stub"
check "v3.1.30: planner is pinned to the first-choice model and only reads" "model: claude-fable-5-1" "$(cat $ST/planner.md)"
check "v3.1.30: planner only reads" "tools: Read, Grep, Glob" "$(cat $ST/planner.md)"
check "v3.1.30: planner-opus is the fallback on Opus 5.5" "model: claude-opus-5-5" "$(cat $ST/planner-opus.md)"
check "v3.1.30: the setup update carries the planner files" "planner.md" "$(grep -o 'planner[-a-z]*\.md' $H/stubupdate.py | tr '\n' ' ')"
check "v3.1.30: the planner files travel with the rules" "planner-opus.md" "$(ls $H/../stub-files)"
P3=$(mktemp -d); mkdir -p "$P3/.claude/agents"; cp "$ST/settings.json" "$P3/.claude/"; cp "$ST/sonnet-worker.md" "$ST/opus-worker.md" "$ST/reviewer.md" "$ST/explore.md" "$P3/.claude/agents/"; cp "$ST/hz-loader.py" "$P3/.claude/"; cp "$ST/CLAUDE-pointer.md" "$P3/CLAUDE.md"
o=$(cd "$H" && python3 -c "import sys;from stubcheck import stub_status;from _common import load_config;print(stub_status(load_config(), sys.argv[1]))" "$P3")
check "v3.1.30: an app on the 3.1.28 setup is told to update (one setup pull request)" "planner" "$o"
pw(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'Agent','session_id':'p4','tool_input':{'subagent_type':sys.argv[1],'prompt':sys.argv[2]}}))" "$1" "$2" | python3 $H/worker-guard.py; }
o=$(pw planner $'Planner instructions: x\nwrite Plan v1'); check "v3.1.30: the planner may start" "^$" "$o"
o=$(pw planner-opus $'Planner instructions: x\nwrite Plan v1'); check "v3.1.30: planner-opus without a reason is refused (planner first)" "Send 'planner' first" "$o"
o=$(pw planner-opus $'Fallback: model claude-fable-5-1 is not available\nPlanner instructions: x'); check "v3.1.30: planner-opus with 'Fallback:' may start" "^$" "$o"
PL=$'# Plan v1 — Test — Awaiting approval\n\n| Summary |\n|---|\n| What changes for you: a new button on the Today screen that opens the week, so you reach the week in one tap. |\n\nStages to finish\n1. Claude — Build — add it\n2. You — Check — merge\n2 stages: one build, one check.\n'
mkpl(){ python3 - "$1" "$2" <<'PYEOF'
import json,sys
out,with_planner=sys.argv[1],sys.argv[2]=='yes'
R=[{"type":"user","message":{"role":"user","content":"plan it"}}]
if with_planner:
    R+=[{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"pl1","name":"Agent","input":{"subagent_type":"planner","prompt":"x"}}]}},
        {"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"pl1","content":"plan text"}]}}]
open(out,"w").write("\n".join(json.dumps(r) for r in R)+"\n")
PYEOF
}
mkpl "$T/pl_no.jsonl" no; mkpl "$T/pl_yes.jsonl" yes
pgp(){ python3 -c "import json,sys;print(json.dumps({'hook_event_name':'PreToolUse','tool_name':'ExitPlanMode','transcript_path':sys.argv[1],'tool_input':{'plan':sys.argv[2]}}))" "$1" "$2" | HZ_PLANNER_CHECK_OFF= python3 $H/plan-guard.py; }
o=$(pgp "$T/pl_no.jsonl" "$PL"); check "v3.1.30: a full plan the main session wrote itself is sent back" "written by the planner helper" "$o"
o=$(pgp "$T/pl_yes.jsonl" "$PL"); check "v3.1.30: a full plan from the planner helper is not sent back for that" "clean" "$(echo "$o" | grep -c 'written by the planner helper' | sed 's/^0$/clean/')"
check "v3.1.30: planner instructions: agreed points and nothing dropped" "Agreed points: <n> of <n> in the plan" "$(cat $H/../agents/planner-instructions.md)"
o=$(echo '{"session_id":"p4s"}' | python3 $H/session-start.py); check "v3.1.30: session start names the planner instructions" "planner-instructions.md" "$o"
n=$(printf '%s' "$o" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['hookSpecificOutput']['additionalContext']))")
check "v3.1.30: session start still under 10,000 characters ($n)" "yes" "$([ "$n" -lt 10000 ] && echo yes || echo no)"
mkm(){ python3 - "$1" "$2" "$3" <<'PYEOF'
import json,sys
out,model,extra=sys.argv[1:4]
R=[{"type":"user","message":{"role":"user","content":"hi"}},
{"type":"assistant","message":{"role":"assistant","model":model,"content":[{"type":"text","text":"⏳ Working on: x · 1 of 2"}]}}]
open(out,"w").write("\n".join(json.dumps(r) for r in R)+"\n")
PYEOF
}
mkm "$T/m_fable.jsonl" claude-fable-5-1 x; mkm "$T/m_opus.jsonl" claude-opus-5-5 x
o=$(echo "{\"transcript_path\":\"$T/m_fable.jsonl\",\"session_id\":\"mf1\"}" | python3 $H/stats.py); check "v3.1.30: a session on Fable gets one notice to switch to Opus" "type /model opus" "$o"
o=$(echo "{\"transcript_path\":\"$T/m_fable.jsonl\",\"session_id\":\"mf1\"}" | python3 $H/stats.py); check "v3.1.30: ...only once per session" "clean" "$(echo "$o" | grep -c '/model opus' | sed 's/^0$/clean/')"
o=$(echo "{\"transcript_path\":\"$T/m_opus.jsonl\",\"session_id\":\"mo1\"}" | python3 $H/stats.py); check "v3.1.30: a session on Opus gets no switch notice" "clean" "$(echo "$o" | grep -c '/model opus' | sed 's/^0$/clean/')"
mkn(){ python3 - "$1" "$2" "$3" <<'PYEOF'
import json,sys
out,need,push=sys.argv[1:4]
R=[{"type":"user","message":{"role":"user","content":"finish"}}]
if push=='yes':
    R+=[{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","id":"n1","name":"PushNotification","input":{"message":"Weekly-Planner: pull request #120 is ready to merge"}}]}},
        {"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"n1","content":"sent"}]}}]
R+=[{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nConfidence: High · Status: Checked\n---\n> 📌 **Result:** Ready to merge.\n> 👉 **I need from you:** "+need+"\n> ➡️ **Next:** next stage."}]}}]
open(out,"w").write("\n".join(json.dumps(r) for r in R)+"\n")
PYEOF
}
rn(){ echo "{\"transcript_path\":\"$1\",\"session_id\":\"$2\"}" | python3 $H/ready-notice-guard.py; }
mkn "$T/n1.jsonl" "Merge pull request #120 on GitHub." no; o=$(rn "$T/n1.jsonl" rn1); check "v3.1.30: a ready-to-merge answer without a notice is sent back" "PushNotification" "$o"
mkn "$T/n2.jsonl" "Merge pull request #120 on GitHub." yes; o=$(rn "$T/n2.jsonl" rn2); check "v3.1.30: with the notice sent it passes" "^$" "$o"
mkn "$T/n3.jsonl" "Answer decision 1." no; o=$(rn "$T/n3.jsonl" rn3); check "v3.1.30: an answer that asks for no merge needs no notice" "^$" "$o"
mkn "$T/n4.jsonl" "合并 #120。" no; o=$(rn "$T/n4.jsonl" rn4); check "v3.1.30: a Chinese merge request also needs the notice" "PushNotification" "$o"
check "v3.1.30: the switchboard runs the notice check" "ready-notice-guard.py" "$(cat $H/config.json)"
echo; echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
