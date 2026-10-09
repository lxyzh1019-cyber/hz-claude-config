#!/bin/bash
# usage: scenario.sh <hooks dir> <label>
HOOKS=$1; LABEL=$2; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
rm -rf $B && mkdir -p $B/home $B/proj/.claude/agents && cp "${OW:-$HERE/../../stub/opus-worker.md}" $B/proj/.claude/agents/opus-worker.md
( cd $B/proj && git init -q && printf '# FEATURES — harness\n- a\n' > FEATURES.md && printf '# WORKING RECORD\n' > WORKING_RECORD.md \
  && git add -A && git -c user.email=t@t -c user.name=t commit -qm init && git checkout -qb claude/harness )
cd $B
python3 - "$HOOKS" "$B" <<'PY'
import json,sys
hooks,B=sys.argv[1],sys.argv[2]
hook=f"python3 -B {hooks}/dispatch.py"
st={"hooks":{e:[{"matcher":".*","hooks":[{"type":"command","command":hook}]}] for e in ("PreToolUse","PostToolUse")},"permissions":{"allow":["Agent","Bash(*)","Read","Task"]}}
st["hooks"]["UserPromptSubmit"]=[{"hooks":[{"type":"command","command":hook}]}]
json.dump(st,open(f"{B}/proj/.claude/settings.json","w"))
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
PY
SID=""
for n in 1 2 3 4; do
  python3 -c "
import json,sys
n=int(sys.argv[1])
json.dump([{'tools':[{'id':f'toolu_w{n}','name':'Agent','input':{'subagent_type':'opus-worker','description':f'worker {n}','run_in_background':True,'prompt':f'Task: W{n}\nSize: S\nLevel: Complex\nMap: not needed - harness test\nDo the step.'}}]},{'text':f'Working on W{n}.'}],open('script.json','w'))" $n
  cp "$HERE/stand_in_model.py" server.py
  HARNESS_LOG=$B/requests.log python3 server.py 8126 script.json > server.out 2>&1 &
  SP=$!; sleep 0.7
  cd proj
  if [ -z "$SID" ]; then R=""; else R="--resume $SID"; fi
  HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:8126 ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 timeout 40 ${CLAUDE_BIN:-claude} -p "start worker $n" $R --output-format json > ../out$n.txt 2>&1 < /dev/null
  SID=$(python3 -c "import json;print(json.load(open('../out$n.txt'))['session_id'])" 2>/dev/null || echo "$SID")
  cd ..; kill $SP 2>/dev/null; wait $SP 2>/dev/null; sleep 0.3
done
T=$(ls $B/home/.claude/projects/*/*.jsonl | head -1)
python3 - "$T" <<'PY'
import json,sys
for l in open(sys.argv[1]):
    r=json.loads(l); c=(r.get('message') or {}).get('content')
    if isinstance(c,list):
        for b in c:
            if isinstance(b,dict) and b.get('type')=='tool_result' and str(b.get('tool_use_id','')).startswith('toolu_w'):
                t=json.dumps(b.get('content'))
                print(b['tool_use_id'], 'REFUSED: '+t[:110] if 'hook error' in t else 'started')
PY
