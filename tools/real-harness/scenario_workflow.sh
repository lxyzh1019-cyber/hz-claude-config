#!/bin/bash
# usage: scenario_workflow.sh <central dir of the rules to serve> <label> <app repo folder>
# v3.2.10: the real Claude Code program runs a dynamic workflow in a copy of a real app repository, with the served
# rules and the app hook list as that version's setup update writes it. The main session first starts a workflow whose
# helpers have no role file, then one whose helpers do. Helper A makes tests faster (22 test runs), B edits and commits
# a file on the work branch, C reads its role file. Prints what each was told and what the checks did.
# Needs CLAUDE_BIN (npm pack @anthropic-ai/claude-code-linux-x64).
CENTRAL=$1; LABEL=$2; APP=$3; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
WEB=${WEB_PORT:-8131}; MOD=${MODEL_PORT:-8132}
rm -rf $B && mkdir -p $B/home $B/web $B/bin && cp -r "$APP" $B/proj && cp -r "$CENTRAL" $B/web/central
python3 - "$B/proj/.claude/settings.json" "$B/web/central/stub-files/settings.json" <<'PY'
import json,sys
app=json.load(open(sys.argv[1])); stub=json.load(open(sys.argv[2]))
app["hooks"]["PreToolUse"]=[dict(g,matcher=s.get("matcher",g.get("matcher"))) for g,s in zip(app["hooks"]["PreToolUse"],stub["hooks"]["PreToolUse"])]
json.dump(app,open(sys.argv[1],"w"),indent=2)
PY
cd $B/web && setsid python3 -m http.server $WEB >/dev/null 2>&1 < /dev/null & WP=$!
git init -q --bare $B/remote.git
( cd $B/proj && git remote remove origin 2>/dev/null; git remote add origin $B/remote.git; git push -q origin HEAD:refs/heads/main >/dev/null 2>&1
  git fetch -q origin; git checkout -q -b claude/workflow-test; git config user.email t@t; git config user.name t )
printf '#!/bin/sh\necho "$@" >> %s/gh-args.txt\necho https://github.com/o/r/pull/7\n' $B > $B/bin/gh
printf '#!/bin/sh\necho "fake npm $@: 1 passing"\n' > $B/bin/npm; chmod +x $B/bin/*
ROLE=$B/home/.cache/hz-rules/role.md
python3 - "$B" <<'PY'
import json,sys
B=sys.argv[1]
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
def script(role):
    r = "Role file: " + B + "/web/central/agents/opus-worker-instructions.md\\n" if role else ""
    tk = "Task kind: test speed\\n" if role else ""
    return ("export const meta = { name: 'harness-test', description: 'Hook test', phases: [{title:'Run'}] }\nphase('Run')\n"
            "return await parallel([\n"
            f"  () => agent('{r}{tk}WFAGENT A: make the tests faster', {{label:'A'}}),\n"
            f"  () => agent('{r}Files: css/b.css\\nWFAGENT B: change b.css and commit it', {{label:'B'}}),\n"
            f"  () => agent('{r}WFAGENT C: run the tests', {{label:'C'}}),\n"
            f"  () => agent('{r}WFAGENT D: run the tests once', {{label:'D'}}),\n])\n")
json.dump([{"text":"Starting the workflow.","tools":[{"id":"toolu_wf0","name":"Workflow","input":{"script":script(False)}}]},
           {"text":"Adding the role files.","tools":[{"id":"toolu_wf1","name":"Workflow","input":{"script":script(True)}}]},
           {"text":"⏳ Working on: workflow · Build 0 of 1 done"},{"text":"Workflow finished."}],open(f'{B}/main.json','w'))
PY
cd $B && setsid python3 "$HERE/stand_in_workflow.py" $MOD main.json "$B/web/central/agents/opus-worker-instructions.md" > srv.out 2>&1 < /dev/null & SP=$!; sleep 0.8
cd $B/proj && PATH=$B/bin:$PATH HZ_CENTRAL_URL=http://127.0.0.1:$WEB/central/ HOME=$B/home \
  ANTHROPIC_BASE_URL=http://127.0.0.1:$MOD ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 IS_SANDBOX=1 \
  timeout 420 ${CLAUDE_BIN:-claude} -p "ultracode: make the tests faster with a workflow of three agents" --permission-mode bypassPermissions --output-format json > ../out.json 2>../err.txt < /dev/null
kill $SP $WP 2>/dev/null; wait $SP $WP 2>/dev/null
cd $B
echo "== $LABEL"
echo "rules loaded: $(grep -o 'Rules v[0-9.]* loaded' req.log | head -1)"
echo "workflow without role files: $(grep -m1 -o 'Every agent() prompt in this workflow starts with the worker rules' req.log || echo 'not refused')"
echo "wait line at workflow start: $(grep -c 'the workflow you are starting' req.log)"
echo "helper A (test speed) requests: $(grep -c 'agent A step' req.log); at run 20: $(grep 'agent A step 20 ' req.log | sed 's/.*LAST: //' | cut -c1-100)"
echo "helper A stopped at 20: $(grep -c 'agent A .*Test-run limit reached (20)' req.log)"
echo "helper B wrote and committed: file=$(test -f proj/css/b.css && echo yes || echo no) commit=$(git -C proj log --oneline -1 | grep -c 'b from workflow') refused=$(grep 'agent B' req.log | grep -c -i 'refus\|denied\|not allowed\|git-guard')"
echo "helper C read its role file and went on: $(grep -c 'agent C step 2 ' req.log)"
echo "helper D background test refused, then run in the foreground: refused=$(grep -c 'test in the foreground' proj/.claude/state/worker-budget.jsonl 2>/dev/null) then=$(grep -c 'agent D step 2 ' req.log)"
python3 - "$B" <<'PY'
import json,sys,glob,os
B=sys.argv[1]; d=glob.glob(B+'/home/.claude/projects/*/')[0]
wf=glob.glob(d+'*/subagents/workflows/*/agent-*.jsonl')
print("workflow helper records:",len(wf))
try:
    st=json.load(open(B+'/proj/.claude/state/worker-steps.json'))
    print("worker step source:",sorted(set(v.get('source') for v in st['agents'].values())))
except Exception as e: print("worker-steps:",e)
PY
python3 $B/web/central/hooks/plan_report.py "make the tests faster" --dir "$(ls -d $B/home/.claude/projects/*/ | head -1)" 2>/dev/null | grep -E "Helpers started|Parallel candidates" | head -2
