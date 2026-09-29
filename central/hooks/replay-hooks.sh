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
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n> 📌 **Result:** login works again.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** I open the pull request.\n---\n\nRegression table\n| Feature | Status |\n| login | kept |\n\nConfidence: Medium · Status: Validated — npm test 12/12"}]}}
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
o=$(cg "$T/done_claim.jsonl" false); check "completion: done claim with open item is blocked" "Auto-fix round 1 of 3" "$o"
check "completion: block names the open item" "export" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: round 2 despite stop_hook_active" "Auto-fix round 2 of 3" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: round 3" "Auto-fix round 3 of 3" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: cap reached demands the limit statement" "Auto-fix limit reached" "$o"
o=$(cg "$T/done_claim.jsonl" true); check "completion: never loops past the cap" "^$" "$o"
rm -f .claude/state/completion-rounds.json
# --- v3.1.14: rounds are counted per user prompt, so the hook's own feedback cannot reset them.
# Five blocks in a row on one prompt: the 4th says the limit is reached, the 5th passes.
echo '{"prompt":"finish the plan"}' | python3 $H/plan-gate.py >/dev/null
cp "$T/done_claim.jsonl" "$T/loop.jsonl"
feedback(){ # a Stop-hook block reaches the transcript as another user record, then the session answers again
  cat >> "$T/loop.jsonl" <<J
{"type":"user","uuid":"fb$1","message":{"role":"user","content":"Not done: continue with 'export' now."}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"All done.\n\nConfidence: High · Status: Validated — npm test"}]}}
J
}
o=$(cg "$T/loop.jsonl" false); check "loop: block 1" "Auto-fix round 1 of 3" "$o"
feedback 1; o=$(cg "$T/loop.jsonl" true); check "loop: feedback does not reset the counter" "Auto-fix round 2 of 3" "$o"
feedback 2; o=$(cg "$T/loop.jsonl" true); check "loop: block 3" "Auto-fix round 3 of 3" "$o"
feedback 3; o=$(cg "$T/loop.jsonl" true); check "loop: block 4 says the limit is reached" "Auto-fix limit reached" "$o"
feedback 4; o=$(cg "$T/loop.jsonl" true); check "loop: block 5 passes" "^$" "$o"
rm -f .claude/state/completion-rounds.json
# scope: rows that are identical on origin/main belong to earlier rounds
o=$(cg "$T/done_claim.jsonl" false); check "completion: only this branch's rows are counted" "Completion: 1 of 3 done (33%)" "$o"
check "completion: an earlier round's row is not listed" "clean" "$(echo "$o" | grep -c 'earlier round' | sed 's/^0$/clean/')"
check "completion: open items are listed one per line, names only" '\\n- export' "$o"
rm -f .claude/state/completion-rounds.json
git update-ref -d refs/remotes/origin/main
o=$(cg "$T/done_claim.jsonl" false); check "completion: unreadable base shows the line but never blocks" "Completion: 1 of 4 done (25%)" "$o"
check "completion: unreadable base does not block on open items" "clean" "$(echo "$o" | grep -c 'Auto-fix round' | sed 's/^0$/clean/')"
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
o=$(cg "$T/done_claim.jsonl" false); check "completion: pause is single-use" "Auto-fix round 1 of 3" "$o"
rm -f .claude/state/completion-rounds.json
printf '# WORKING RECORD\n\n## Hotspot counter\n| Area / feature | Fix rounds | Recurrences | Regressions caused | Workarounds/exceptions | Last symptom | Rewrite-vs-repair reviewed? |\n|---|---|---|---|---|---|---|\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n| login | COMPLETE | npm test 12/12 |\n| export | COMPLETE | |\n' > WORKING_RECORD.md
o=$(cg "$T/done_claim.jsonl" false); check "completion: all complete still needs the Completion line" "Completion: 2 of 2 done (100%)" "$o"
cat > "$T/done_line.jsonl" <<J
{"type":"user","uuid":"u4","message":{"role":"user","content":"finish the plan"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nCompletion: 1 of 2 done (50%)\n\nConfidence: High · Status: Validated — npm test"}]}}
J
o=$(cg "$T/done_line.jsonl" false); check "completion: wrong count is corrected" "does not match" "$o"
cat > "$T/done_ok.jsonl" <<J
{"type":"user","uuid":"u5","message":{"role":"user","content":"finish the plan"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Edit","input":{"file_path":"$PROJ/js/app.js"}}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done.\n\nCompletion: 2 of 2 done (100%)\n\nConfidence: High · Status: Validated — npm test"}]}}
J
o=$(cg "$T/done_ok.jsonl" false); check "completion: COMPLETE without evidence is caught" "without evidence" "$o"
sed -i 's/| export | COMPLETE | |/| export | COMPLETE | manual check |/' WORKING_RECORD.md
o=$(cg "$T/done_ok.jsonl" false); check "completion: correct line with evidence passes" "^$" "$o"
o=$(echo '{}' | python3 $H/session-start.py); check "session-start: no completion line when nothing open" "clean" "$(echo "$o" | grep -c '\[completion\]' | sed 's/^0$/clean/')"
printf '| again | NOT STARTED | |\n' >> WORKING_RECORD.md
o=$(echo '{}' | python3 $H/session-start.py); check "session-start: completion line when items open" "Completion: 2 of 3 done (67%)" "$o"
# v3.1.14: at most five open items are listed, the rest are counted
for i in 1 2 3 4 5 6; do printf '| open-%s | NOT STARTED | |\n' "$i" >> WORKING_RECORD.md; done
o=$(echo '{}' | python3 $H/session-start.py); check "long open list is cut after five names" "+2 more in the record" "$o"
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
vl(){ echo "{\"transcript_path\":\"$1\",\"stop_hook_active\":false}" | python3 $H/validation-line.py; }
cat > "$T/first_noversion.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install the stub"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I'll start by reading the current state."}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}
{"type":"user","message":{"role":"user","content":[{"type":"tool_result","content":"ok"}]}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n> 📌 **Result:** installed.\n> 👉 **I need from you:** merge the pull request.\n> ➡️ **Next:** health check.\n---\n\nConfidence: High · Status: Checked"}]}}
J
pn 1
o=$(vl "$T/first_noversion.jsonl"); check "first reply must open with the version, not a preamble" "very first line must be 'Rules v" "$o"
# v3.1.14: the first-reply check follows the prompt number, so Stop-hook feedback (another user record in the
# transcript) does not turn the same prompt into a later reply
cat > "$T/first_feedback.jsonl" <<J
{"type":"user","message":{"role":"user","content":"install the stub"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n> 📌 **Result:** installed.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** health check."}]}}
{"type":"user","message":{"role":"user","content":"This reply is missing its closing line."}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"> 📌 **Result:** installed.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** health check.\n---\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/first_feedback.jsonl"); check "feedback does not end the first reply" "very first line must be 'Rules v" "$o"
pn 2
cat > "$T/second_notop.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\n> 📌 **Result:** ready.\n> 👉 **I need from you:** nothing.\n> ➡️ **Next:** waiting.\n---\n\nConfidence: High · Status: Checked"}]}}
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"The hook now checks X in file y.py.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/second_notop.jsonl"); check "final answer without the quote top is sent back" "quote block of three lines" "$o"
check "later replies need no version line" "clean" "$(echo "$o" | grep -c 'first reply of the session' | sed 's/^0$/clean/')"
cat > "$T/second_top.jsonl" <<J
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Rules v3.1.11 · main\nResult: ready.\nI need from you: nothing.\nNext: waiting.\n\nConfidence: High · Status: Checked"}]}}
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"📌 Result: the check now runs at every start.\n👉 I need from you: nothing\n> ➡️ **Next:** nothing to do.\n---\n\nDetails: hook y.py.\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/second_top.jsonl"); check "quote top accepted with or without the quote marker and bold" "^$" "$o"
# v3.1.14: the icons are part of the labels
cat > "$T/second_noicons.jsonl" <<J
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"> **Result:** the check now runs.\n> **I need from you:** nothing\n> **Next:** nothing to do.\n---\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/second_noicons.jsonl"); check "labels without icons are sent back" "quote block of three lines" "$o"
cat > "$T/second_plainarrow.jsonl" <<J
{"type":"user","message":{"role":"user","content":"what changed?"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"> 📌 **Result:** the check now runs.\n> 👉 **I need from you:** nothing\n> ➡ **Next:** nothing to do.\n---\n\nConfidence: High · Status: Checked"}]}}
J
o=$(vl "$T/second_plainarrow.jsonl"); check "arrow without the invisible character is accepted" "^$" "$o"
o=$(vl "$T/prog_earlier.jsonl"); check "progress report needs no plain top" "^$" "$o"
# stub check
o=$(echo '{}' | python3 $H/session-start.py); check "stub outdated is reported in plain words" "OUTDATED" "$o"
check "stub report names the missing pieces" "Sonnet worker" "$o"
S="$T/stubrepo"; rm -rf "$S"; mkdir -p "$S/.claude/agents"
cp "$H/../../stub/settings.json" "$S/.claude/settings.json"
cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$S/.claude/agents/"
cp "$H/../../stub/CLAUDE-pointer.md" "$S/CLAUDE.md"
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
check "opus-worker runs on the session model" "yes" "$(grep -qx 'model: inherit' "$H/../../stub/opus-worker.md" && echo yes)"
check "sonnet-worker is pinned to the exact Sonnet 5.5 ID" "yes" "$(grep -qx 'model: claude-sonnet-5-5' "$H/../../stub/sonnet-worker.md" && echo yes)"
M="$T/modelrepo"; rm -rf "$M"; mkdir -p "$M/.claude/agents"
cp "$H/../../stub/settings.json" "$M/.claude/settings.json"; cp "$H/../../stub/sonnet-worker.md" "$H/../../stub/opus-worker.md" "$M/.claude/agents/"
cp "$H/../../stub/CLAUDE-pointer.md" "$M/CLAUDE.md"
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
dp(){ python3 $H/dispatch.py; }
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | dp); check "switchboard passes on a git-guard deny" '"deny"' "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"npm test"}}' | dp); check "switchboard quiet on a harmless command" "^$" "$o"
o=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"x"}}' | dp); check "switchboard skips checks for other tools" "^$" "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"transcript_path\":\"$T/noline.jsonl\",\"stop_hook_active\":false}" | dp); check "switchboard passes on a Stop block" '"decision": "block"' "$o"
o=$(echo "{\"hook_event_name\":\"Stop\",\"transcript_path\":\"$T/second_top.jsonl\",\"stop_hook_active\":false}" | dp); check "switchboard quiet when every Stop check passes" "^$" "$o"
o=$(echo '{"hook_event_name":"UserPromptSubmit","prompt":"the sync layer keeps breaking"}' | dp); check "switchboard joins prompt contexts" "Executor: opus-worker" "$o"
check "switchboard answers once for the prompt event" "1" "$(echo "$o" | grep -c hookSpecificOutput)"
o=$(echo '{"hook_event_name":"SubagentStop"}' | dp); check "switchboard quiet on an event with no checks" "^$" "$o"
check "stub hands every forwarded event to the switchboard" "5" "$(python3 -c "import json;h=json.load(open('$H/../../stub/settings.json'))['hooks'];print(sum(1 for e in ('UserPromptSubmit','PreToolUse','PostToolUse','Stop','SubagentStop') if 'dispatch.py' in json.dumps(h.get(e,[]))))")"
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
