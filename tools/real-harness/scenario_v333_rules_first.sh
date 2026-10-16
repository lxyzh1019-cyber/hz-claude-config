#!/usr/bin/env bash
# v3.3.3 fix 6: the real Claude Code program, a scripted stand-in model, and the real rules-first check as a hook.
# The session runs a read-only command, then a change, before reading the rules; then reads the rules and repeats
# the change. Usage: bash scenario_v333_rules_first.sh <central dir> <label>   (needs CLAUDE_BIN)
# Prints REFUSED or RAN for each step.
set -u
C=$(cd "$1" && pwd); L=$2; HERE=$(cd "$(dirname "$0")" && pwd); B=/tmp/hz-harness-333rf/$L; PORT=$((8300 + RANDOM % 500))
rm -rf "$B"; mkdir -p "$B/home" "$B/proj/.claude/state"
RP=$(cd "$C/hooks" && python3 -c "from _common import RULES_PATH;print(RULES_PATH)")
cat > "$B/home/.claude.json" <<J
{"projects":{"$B/proj":{"hasTrustDialogAccepted":true,"hasCompletedProjectOnboarding":true}},"hasCompletedOnboarding":true,
 "customApiKeyResponses":{"approved":["sk-fake"],"rejected":[]}}
J
cat > "$B/proj/.claude/settings.json" <<J
{"hooks":{"PreToolUse":[{"matcher":"Bash|Edit|Write","hooks":[{"type":"command","command":"python3 -B $C/hooks/dispatch.py PreToolUse"}]}]}}
J
(cd "$B/proj" && git init -q -b main && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m start)
cat > "$B/script.json" <<J
[{"text":"s1","tools":[{"id":"b1","name":"Bash","input":{"command":"git status && git log --oneline -1","description":"read"}}]},
 {"text":"s2","tools":[{"id":"b2","name":"Bash","input":{"command":"git checkout -b test-333","description":"change"}}]},
 {"text":"s3","tools":[{"id":"r1","name":"Read","input":{"file_path":"$RP"}}]},
 {"text":"s4","tools":[{"id":"b3","name":"Bash","input":{"command":"git checkout -b test-333","description":"change"}}]},
 {"text":"end"}]
J
python3 "$HERE/stand_in_plan.py" $PORT "$B/script.json" >/dev/null 2>&1 & SRV=$!; sleep 0.8
(cd "$B/proj" && HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:$PORT ANTHROPIC_API_KEY=sk-fake IS_SANDBOX=1 \
  DISABLE_AUTOUPDATER=1 CLAUDE_PROJECT_DIR=$B/proj timeout 120 "${CLAUDE_BIN:-claude}" -p "go" \
  --permission-mode bypassPermissions >/dev/null 2>&1)
kill $SRV 2>/dev/null
python3 - "$B" <<'P'
import json,glob,sys
B=sys.argv[1]; res={}
for f in glob.glob(B+"/home/.claude/projects/*/*.jsonl"):
    for l in open(f):
        r=json.loads(l); c=(r.get("message") or {}).get("content")
        if isinstance(c,list):
            for x in c:
                if isinstance(x,dict) and x.get("type")=="tool_result":
                    t=json.dumps(x.get("content"))
                    res[x["tool_use_id"]]="REFUSED" if "Read the working rules first" in t else "RAN"
names={"b1":"1 read-only git status before the rules","b2":"2 change (git checkout -b) before the rules",
       "r1":"3 Read of the rules file","b3":"4 the same change after the rules"}
for k in ("b1","b2","r1","b3"): print(f"{res.get(k,'MISSING'):8} {names[k]}")
P
