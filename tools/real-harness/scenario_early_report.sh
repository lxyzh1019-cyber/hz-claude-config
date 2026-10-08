#!/bin/bash
# usage: [OBEY=1] scenario_early_report.sh <hooks dir> <label>
# v3.2.2: a background helper still runs when the main session would write its report (Weekly-Planner 2026-10-08:
# two full answers with closing lines, the first written while the reviewer and a GitHub run still went).
# OBEY=1: the scripted model follows the wait text (one ⏳ line, then one report after the finish notice).
HOOKS=$1; LABEL=$2; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
rm -rf $B && mkdir -p $B/home $B/proj/.claude/agents && cp "$HERE/../../stub/opus-worker.md" $B/proj/.claude/agents/
( cd $B/proj && git init -q && printf '# FEATURES — harness\n- a\n' > FEATURES.md && printf '# WORKING RECORD\n' > WORKING_RECORD.md \
  && git add -A && git -c user.email=t@t -c user.name=t commit -qm init && git checkout -qb claude/harness )
cd $B
python3 - "$HOOKS" "$B" <<'PY'
import json,sys,os
hooks,B=sys.argv[1],sys.argv[2]
hook=f"python3 -B {hooks}/dispatch.py"
st={"hooks":{e:[{"matcher":".*","hooks":[{"type":"command","command":hook}]}] for e in ("PreToolUse","PostToolUse")},"permissions":{"allow":["Agent","Bash(*)","Read","Task"]}}
for e in ("UserPromptSubmit","Stop"): st["hooks"][e]=[{"hooks":[{"type":"command","command":hook}]}]
json.dump(st,open(f"{B}/proj/.claude/settings.json","w"))
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
REPORT="Report.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Still being worked on.\n> 👉 **I need from you:** Nothing now.\n> ➡️ **Next:** More work."
second='⏳ Working on: W1 · Build 0 of 1 done' if os.environ.get('OBEY') else REPORT
json.dump([{'tools':[{'id':'toolu_w1','name':'Agent','input':{'subagent_type':'opus-worker','description':'worker 1','run_in_background':True,'prompt':'Task: W1\nSize: S\nLevel: Complex\nMap: not needed - harness test\nDo the step.'}}]},
           {'text':second},{'text':REPORT}],open('script.json','w'))
PY
cp "$HERE/stand_in_model.py" server.py
SUBAGENT_DELAY=${SUBAGENT_DELAY:-12} HARNESS_LOG=$B/requests.log python3 server.py 8127 script.json > server.out 2>&1 &
SP=$!; sleep 0.7
cd proj
HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:8127 ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 timeout 90 ${CLAUDE_BIN:-claude} -p "run the stage" --output-format stream-json --verbose > ../out.txt 2>&1 < /dev/null
cd ..; kill $SP 2>/dev/null; wait $SP 2>/dev/null
python3 - "$B" <<'PY'
import json,sys,glob
B=sys.argv[1]
T=sorted(glob.glob(B+'/home/.claude/projects/*/*.jsonl'))[0]
n=0
for l in open(T):
    r=json.loads(l)
    if r.get('type')=='assistant' and not r.get('isSidechain'):
        for b in (r.get('message') or {}).get('content') or []:
            if isinstance(b,dict) and b.get('type')=='text' and '📌' in b.get('text',''): n+=1
print('closing lines shown:', n)
PY
echo "session summaries shown: $(grep -c '"shown": "summary"' $B/proj/.claude/state/stats.jsonl 2>/dev/null)"
echo "early reports logged: $(cat $B/proj/.claude/state/report-early.jsonl 2>/dev/null | grep -c .)"
echo "wait text after the helper start: $(grep -c 'PreToolUse:Agent hook additional context: \[report timing\] Still running' $B/requests.log)"
echo "report text at the finish notice: $(grep -c 'Every helper and background command has finished' $B/requests.log)"
