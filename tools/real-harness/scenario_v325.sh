#!/bin/bash
# usage: scenario_v325.sh <hooks dir> <label>
# v3.2.5, the real Claude Code program with the real checks as hooks. Three things from the Weekly-Planner Stage 7 session:
#  1. a helper's hand-back text arrives as the user's prompt (plan-gate must stay silent);
#  2. a command moved to the background after its time limit (the session file must show it as still running);
#  3. the session works in a worktree and writes a restart line for its real plan (the hand-off check must not demand the
#     closed plan of the main folder).
HOOKS=$1; LABEL=$2; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
rm -rf $B && mkdir -p $B/home $B/proj/.claude && cd $B/proj
git init -q -b main . && git config user.email t@t && git config user.name t
rec(){ printf '# WR\n\n## Deliverable ledger\n| Deliverable | State | Evidence |\n|---|---|---|\n%s\n' "$1"; }
rec '| Old plan · Stage 1 of 1 — closed work | COMPLETE | tests |' > WORKING_RECORD.md; printf '# FEATURES\n- a\n' > FEATURES.md
git add -A && git commit -qm base && git worktree add -q -b feat $B/wt
rec '| Old plan · Stage 1 of 1 — closed work | COMPLETE | tests |
| New plan · Stage 1 of 2 — first | COMPLETE | tests |
| New plan · Stage 2 of 2 — second | QUEUED — after Stage 1 | |' > $B/wt/WORKING_RECORD.md
python3 - "$HOOKS" "$B" <<'PY'
import json,sys
hooks,B=sys.argv[1],sys.argv[2]
hook=f"python3 -B {hooks}/dispatch.py"
st={"hooks":{e:[{"matcher":".*","hooks":[{"type":"command","command":hook}]}] for e in ("PreToolUse","PostToolUse")},"permissions":{"allow":["Bash(*)","Read","Agent"]}}
for e in ("UserPromptSubmit","Stop"): st["hooks"][e]=[{"hooks":[{"type":"command","command":hook}]}]
json.dump(st,open(f"{B}/proj/.claude/settings.json","w"))
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
FINAL="Plan status.\n\nContinue New plan on branch feat; next: Stage 2 of 2 — second.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Still being worked on.\n> 👉 **I need from you:** Nothing now.\n> ➡️ **Next:** Stage 2."
json.dump([{"tools":[{"id":"toolu_r1","name":"Bash","input":{"command":f'cd "{B}/wt" && head -5 WORKING_RECORD.md',"description":"read the record in the worktree"}}]},
           {"tools":[{"id":"toolu_s1","name":"Bash","input":{"command":"python3 -c \"import time; time.sleep(25)\"","timeout":2000,"description":"a slow command"}}]},
           {"text":FINAL}],open(f"{B}/script.json","w"))
PY
cp "$HERE/stand_in_model.py" $B/server.py; cd $B
PORT=${PORT:-8160}
HARNESS_LOG=$B/requests.log python3 server.py $PORT script.json > server.out 2>&1 & SP=$!; sleep 0.7
cd proj
HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:$PORT ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 HZ_REPORT_TIMING_OFF=1 timeout 120 ${CLAUDE_BIN:-claude} -p "run the stage" --output-format json > ../out.txt 2>&1 < /dev/null
kill $SP 2>/dev/null; wait $SP 2>/dev/null; cd $B
echo "--- 2. the real message for a command moved to the background:"
python3 - "$B" "$HOOKS" <<'PY'
import json,sys,glob
B,H=sys.argv[1:3]; sys.path.insert(0,H)
T=sorted(glob.glob(B+'/home/.claude/projects/*/*.jsonl'))[0]
R=[json.loads(l) for l in open(T)]
for r in R:
    for b in ((r.get('message') or {}).get('content') or []):
        if isinstance(b,dict) and b.get('type')=='tool_result' and b.get('tool_use_id')=='toolu_s1':
            print("   result:",json.dumps(b.get('content'))[:170])
import os; os.environ['CLAUDE_PROJECT_DIR']=B+'/proj'
import _common as C
fn=getattr(C,'still_running',None)
last=max(i for i,r in enumerate(R) if r.get('type')=='assistant')   # the moment of the final answer (the Stop check)
print("   still running when the final answer is written:", fn(R[:last+1],T) if fn else "function not in these rules")
ef=B+'/proj/.claude/state/report-early.jsonl'
print("   early report noticed by the Stop check:", open(ef).read().strip()[:120] if os.path.exists(ef) else "no")
PY
echo "--- 3. what the hand-off check saved for the next step (wrong plan demanded?):"
cat $B/proj/.claude/state/pending-fixes.json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin) if sys.stdin.readable() else {}
fx=[x for v in d.values() for x in v]
print('   saved fixes:',len(fx)); [print('   -',x[:200]) for x in fx]" 2>/dev/null || echo "   saved fixes: 0"
