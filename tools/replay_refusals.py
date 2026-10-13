#!/usr/bin/env python3
# v3.3.0 side-by-side A: replays every step a session refused through the same check of another rules version
# (worker hand-overs get the Test: line that 3.3.0 requires). Usage: python3 tools/replay_refusals.py <central dir>
import json,glob,os,re,subprocess,sys,collections,shutil
CENTRAL=sys.argv[1]; S='/home/claude/s2'; base='ef185ec5-3e30-4c29-b604-e39df5a7aa8a'
P='/home/claude/ab/proj2'; shutil.rmtree(P,ignore_errors=True); os.makedirs(P+'/.claude')
os.system(f'cp -r /home/claude/st2/state {P}/.claude/state; cd {P} && git init -q && git config user.email t@t && git config user.name t && git checkout -q -b claude/r2 && git commit -q --allow-empty -m c')
MAP=[('full test suite','wait-guard.py'),('Read the central rules','rules-read-guard.py'),('No waiting','wait-guard.py'),('test runs. Find all','worker-budget.py'),('Test-run limit','worker-budget.py'),('open the pull request','git-guard.py'),('needs no worktree','worker-guard.py'),('[skip ci]','git-guard.py'),('Plan sent back','plan-guard.py')]
out=collections.Counter()
for f in [S+'/'+base+'.jsonl']+glob.glob(S+'/'+base+'/subagents/*.jsonl'):
    agent=None if f.endswith(base+'.jsonl') else os.path.basename(f)[6:-6]
    lines=open(f).read().splitlines(); res={}
    for l in lines:
        r=json.loads(l); c=(r.get('message') or {}).get('content')
        for b in (c if isinstance(c,list) else []):
            if b.get('type')=='tool_result':
                t=b.get('content'); res[b.get('tool_use_id')]=(t if isinstance(t,str) else json.dumps(t))[:400]
    for i,l in enumerate(lines):
        r=json.loads(l); c=(r.get('message') or {}).get('content')
        if r.get('type')!='assistant' or not isinstance(c,list): continue
        for b in c:
            if b.get('type')!='tool_use' or 'hook error' not in res.get(b['id'],'')[:200]: continue
            was=res[b['id']]; sc=next((s for k,s in MAP if k in was),None)
            tp='/home/claude/ab/t2.jsonl'
            _ls=list(lines[:i])
            if agent:   # v3.3.0 hand-overs carry a Test: line
                for j,_l in enumerate(_ls):
                    _r=json.loads(_l)
                    if _r.get('type')=='user':
                        c0=(_r.get('message') or {}).get('content')
                        if isinstance(c0,str): _r['message']['content']=c0+"\nTest: npm run test:failed"
                        elif isinstance(c0,list) and c0 and c0[0].get('type')=='text': c0[0]['text']+="\nTest: npm run test:failed"
                        _ls[j]=json.dumps(_r); break
            open(tp,'w').write("\n".join(_ls)+"\n")
            inp={"hook_event_name":"PreToolUse","session_id":"ab","transcript_path":tp,"tool_name":b['name'],"tool_input":b.get('input') or {},"tool_use_id":b['id']}
            if agent: inp["agent_id"]=agent
            o=subprocess.run(['python3','-B',CENTRAL+'/hooks/'+sc],input=json.dumps(inp),capture_output=True,text=True,env=dict(os.environ,CLAUDE_PROJECT_DIR=P,HZ_RULES_FIRST_OFF='1'),cwd=P).stdout
            now=('still refused: '+(re.search(r'Reason": "(.{0,55})',o).group(1) if re.search(r'Reason": "(.{0,55})',o) else '?')) if '"deny"' in o else ('fixed in place' if 'updatedInput' in o or '"allow"' in o else 'not refused')
            out[(sc,now)]+=1
for (k,n),v in sorted(out.items()): print(f"{v:3} | {k:20} | {n}")
print('total',sum(out.values()),'| still refused',sum(v for (k,n),v in out.items() if n.startswith('still refused')))
