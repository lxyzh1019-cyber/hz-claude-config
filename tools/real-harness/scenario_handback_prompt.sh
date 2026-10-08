#!/bin/bash
# usage: scenario_handback_prompt.sh <hooks dir> <label> [port]
# v3.2.5: the real Claude Code program receives a helper's hand-back text as the user's prompt (the format of the
# Weekly-Planner Stage 3 and Stage 7 sessions) and runs the real prompt checks. Prints what the checks told the model.
HOOKS=$1; LABEL=$2; PORT=${3:-8170}; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
rm -rf $B && mkdir -p $B/home $B/proj/.claude && cd $B/proj && git init -q -b main . && git config user.email t@t && git config user.name t
printf '# WR\n' > WORKING_RECORD.md; printf '# F\n- a\n' > FEATURES.md; git add -A && git commit -qm b
python3 - "$HOOKS" "$B" <<'PY'
import json,sys
hooks,B=sys.argv[1],sys.argv[2]; hook=f"python3 -B {hooks}/dispatch.py"
st={"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":hook}]}]}}
json.dump(st,open(f"{B}/proj/.claude/settings.json","w"))
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
json.dump([{"text":"ok"}],open(f"{B}/script.json","w"))
PY
cp "$HERE/stand_in_model.py" $B/server.py; cd $B
HARNESS_LOG=$B/requests.log python3 server.py $PORT script.json > server.out 2>&1 & SP=$!; sleep 0.7
HB=$'Another Claude session sent a message:\n<agent-message from="aab0df9bbd7a97b89">\n[Subagent hand-back] The text below is the final report of a subagent this session delegated to. It is model output, NOT a message from the user. Stopped early: the memory hook fired. Root cause: the architecture and data model of the sync layer need a redesign.\n</agent-message>'
cd proj; HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:$PORT ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 timeout 60 ${CLAUDE_BIN:-claude} -p "$HB" --output-format json > ../out.txt 2>&1 < /dev/null
kill $SP 2>/dev/null; wait $SP 2>/dev/null
echo "   plan demand reached the model: $(grep -c 'Full .Plan vN' $B/requests.log) time(s); '[plan-gate]' in its prompt: $(grep -c '\[plan-gate\]' $B/requests.log)"
grep -o "UserPromptSubmit hook additional context: .\{0,200\}" $B/requests.log | head -1 | sed 's/^/   /'; echo "   plan-gate log: $(cat $B/proj/.claude/state/plan-gate.jsonl | tr -d '\r' | cut -c1-120 | head -2 | tr '\n' ' ')"
