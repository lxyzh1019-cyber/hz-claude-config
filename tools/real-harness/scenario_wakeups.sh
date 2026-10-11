#!/bin/bash
# usage: scenario_wakeups.sh <central dir> <label> <app folder>  (v3.2.14) real Claude Code; the main session starts two lane
# workers in one message, in the background as sessions do. Lane 1 finishes normally; lane 2 (helper E) stops with a
# background command still running, as real workers did. Prints how many replies the main session showed.
CENTRAL=$1; LABEL=$2; APP=${3:?give the app folder}; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL; WEB=${WEB:-8201}; MOD=${MOD:-8202}
rm -rf $B && mkdir -p $B/home $B/web $B/bin && cp -r "$APP" $B/proj && cp -r "$CENTRAL" $B/web/central
cd $B/web && setsid python3 -m http.server $WEB >/dev/null 2>&1 < /dev/null & WP=$!
git init -q --bare $B/remote.git
( cd $B/proj && git remote remove origin 2>/dev/null; git remote add origin $B/remote.git; git push -q origin HEAD:refs/heads/main >/dev/null 2>&1; git checkout -q -b claude/part-9; git config user.email t@t; git config user.name t )
printf '#!/bin/sh\necho "[]"\n' > $B/bin/gh; printf '#!/bin/sh\nsleep 2; echo "fake npm $@: 1 passing"\n' > $B/bin/npm; chmod +x $B/bin/*
python3 - "$B" <<'PY'
import json,sys
B=sys.argv[1]
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
h=lambda n,extra: {"id":f"toolu_ag{n}","name":"Agent","input":{"subagent_type":"sonnet-worker","description":f"worker {n}","run_in_background":True,
   "prompt":f"Task: Stage 1 of 2 — Part 9 lane {n}\nLevel: Routine\nMap: not needed - test\nSize: S\n{extra}WFAGENT {"C" if n==1 else "E"}: run the tests"}}
steps=[{"text":"","tools":[h(1,"Worktree: ../wp-lane-a\nFiles: a.js\nGroup: A\n"),h(2,"Worktree: ../wp-lane-b\nFiles: b.js\nGroup: A\n")]}]+[{"text":f"⏳ Working on: lanes · reply {i}"} for i in range(1,15)]
json.dump(steps,open(f'{B}/main.json','w'))
PY
cd $B && setsid python3 "$HERE/stand_in_workflow.py" $MOD main.json "$B/web/central/agents/opus-worker-instructions.md" > srv.out 2>&1 < /dev/null & SP=$!; sleep 0.8
cd $B/proj && PATH=$B/bin:$PATH HZ_CENTRAL_URL=http://127.0.0.1:$WEB/central/ HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:$MOD ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 HZ_STAGE_TAGS_OFF=1 IS_SANDBOX=1 \
  timeout 300 ${CLAUDE_BIN:-claude} -p "Go on with Part 9" --permission-mode bypassPermissions --output-format stream-json --verbose > ../out.jsonl 2>../err.txt < /dev/null
kill $SP $WP 2>/dev/null; wait $SP $WP 2>/dev/null
cd $B
python3 - <<'PY'
import json
txt=[];notes=0
for l in open('out.jsonl'):
    try: e=json.loads(l)
    except: continue
    if e.get('type')=='assistant':
        for b in e['message'].get('content',[]):
            if e.get("parent_tool_use_id") is None and b.get("type")=="text" and b["text"].strip(): txt.append(b['text'].strip()[:60])
    if e.get('type')=='user' and 'task-notification' in json.dumps(e): notes+=1
print("main replies shown to you:",len(txt)); [print("  ",t) for t in txt]
PY
grep -c "agent C step" req.log | sed 's/^/helper requests: /'; grep -o "MAIN LAST: .\{0,140\}" req.log | sed -n '2,8p'
