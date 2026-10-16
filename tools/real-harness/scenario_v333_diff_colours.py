# v3.3.3: real program check that the plan window colours the check's green (new) and red (removed) lines.
# Usage: CLAUDE_BIN=<claude> python3 tools/real-harness/scenario_v333_diff_colours.py
import sys,os,json,time
sys.path.insert(0,'" + os.path.dirname(os.path.abspath(__file__)) + "')
sys.argv=['x','/home/claude/v33/central','none']
import importlib.util
spec=importlib.util.spec_from_file_location('sc','" + os.path.dirname(os.path.abspath(__file__)) + "/scenario_v3217.py')
src=open('" + os.path.dirname(os.path.abspath(__file__)) + "/scenario_v3217.py').read()
src=src[:src.find('SQ = "')]   # helpers only
src=src.replace('os.path.join(HERE, "stand_in_plan.py")','"" + os.path.dirname(os.path.abspath(__file__)) + "/stand_in_plan.py"'); exec(compile(src,'sc','exec'))
PLAN="# Plan v1 Rev 2 — Test — Awaiting approval\n\n**Summary**\n- I need from you: approve.\n\n**What changed since Rev 1**\n- Summary: 1 new line, 1 removed\n🎨 Changes by section (green new, red removed)\n```diff\n@@ Summary @@\n- I need from you: answer 3 questions.\n+ I need from you: approve.\n```\n\n**Stops**\n- Merge.\n"
B=setup('diffcolor',{})
r=Run(B,[{"text":"Writing.","tools":[{"id":"w1","name":"Write","input":{"file_path":"PLANPATH","content":PLAN}}]},{"text":"Plan.","tools":[{"id":"p1","name":"ExitPlanMode","input":{}}]},{"text":"END"}])
s=r.type("make a plan",20)
found={}
for y,line in r.scr.buffer.items():
    txt="".join(line[x].data for x in sorted(line))
    for key in ("+ I need from you: approve","- I need from you: answer 3"):
        if key in txt:
            x=txt.find(key)+3
            found[key]=(line[x].fg, line[x].bg)
r.close()
print(json.dumps(found))
print([l for l in s.splitlines() if 'need from you' in l])
