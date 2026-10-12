#!/usr/bin/env python3
"""v3.2.17: the real Claude Code program in a terminal (pexpect + pyte), a scripted stand-in model, and the real central
checks as hooks. Usage: python3 scenario_v3217.py <central dir> [scenario ...]   (needs CLAUDE_BIN; pip pexpect pyte)
Scenarios:
  window  - what the approval window shows: how the marks are added, and whether 'allow' skips the owner
  plan    - the real plan check: a changed Rev of an approved plan shows coloured marks; the owner still approves;
            the plan Claude Code keeps at the approval holds the marks (the trial passes)
  ask     - tappable questions without a notice are refused; after the notice the question window opens
  notice  - a waiting answer without a notice is sent back once; the session sends it and ends with 'Notice sent.'
  lag     - P03: how often the session file lags behind the final answer at a Stop, and whether an end-of-answer
            check (the merge check) still reads the right answer"""
import json, os, re, shutil, subprocess, sys, time
import pexpect, pyte

CENTRAL = os.path.abspath(sys.argv[1]); WANT = sys.argv[2:] or ["window", "plan", "ask", "notice", "lag"]
HERE = os.path.dirname(os.path.abspath(__file__)); CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
BASE = os.environ.get("HARNESS_DIR", "/tmp/hz-harness-3217"); PORT = [8170]
ok_all = []


def say(name, ok, detail=""):
    ok_all.append(bool(ok)); print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:300]!r}"))


def setup(label, hooks, extra_files=None):
    B = os.path.join(BASE, label); shutil.rmtree(B, ignore_errors=True)
    os.makedirs(B + "/home"); os.makedirs(B + "/proj/.claude/state"); os.makedirs(B + "/proj/plans")
    json.dump({"projects": {f"{B}/proj": {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True}},
               "hasCompletedOnboarding": True, "theme": "dark",
               "customApiKeyResponses": {"approved": ["sk-fake"], "rejected": []}}, open(f"{B}/home/.claude.json", "w"))
    json.dump({"plansDirectory": "./plans", "hooks": hooks}, open(f"{B}/proj/.claude/settings.json", "w"))
    for k, v in (extra_files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(B, "proj", k)), exist_ok=True)
        open(os.path.join(B, "proj", k), "w", encoding="utf-8").write(v)
    subprocess.run("git init -q && git add -A && git -c user.email=t@t -c user.name=t commit -qm start", shell=True,
                   cwd=B + "/proj")
    return B


def dispatch_hooks(events):
    cmd = {"type": "command", "command": f"python3 -B {CENTRAL}/hooks/dispatch.py"}
    out = {}
    for ev, matcher in events.items():
        out[ev] = [dict({"matcher": matcher} if matcher else {}, hooks=[cmd])]
    return out


class Run:
    def __init__(self, B, script, mode="plan", env_extra=None):
        self.B = B; PORT[0] += 1; port = str(PORT[0])
        json.dump(script, open(f"{B}/script.json", "w"))
        self.srv = subprocess.Popen(["python3", os.path.join(HERE, "stand_in_plan.py"), port, f"{B}/script.json"], cwd=B,
                                    env=dict(os.environ, HARNESS_LOG=f"{B}/req.log"))
        time.sleep(0.8)
        env = dict(os.environ, HOME=B + "/home", ANTHROPIC_BASE_URL="http://127.0.0.1:" + port, ANTHROPIC_API_KEY="sk-fake",
                   IS_SANDBOX="1", DISABLE_AUTOUPDATER="1", TERM="xterm-256color", CLAUDE_PROJECT_DIR=B + "/proj",
                   HZ_RULES_FIRST_OFF="1", PT=B, **(env_extra or {}))
        self.scr = pyte.Screen(170, 70); self.st = pyte.ByteStream(self.scr)
        self.ch = pexpect.spawn(CLAUDE, ["--permission-mode", mode], cwd=B + "/proj", env=env, dimensions=(70, 170))
        self.all = ""
        self.pump(15)

    def pump(self, t):
        end = time.time() + t
        while time.time() < end:
            try:
                self.st.feed(self.ch.read_nonblocking(100000, timeout=0.3))
            except pexpect.TIMEOUT:
                pass
            except pexpect.EOF:
                break
        s = self.screen()
        self.all += "\n" + s
        return s

    def screen(self):
        return "\n".join(l.rstrip() for l in self.scr.display if l.strip())

    def type(self, text, wait=15):
        for c in text:
            self.ch.send(c); self.pump(0.05)
        self.pump(1); self.ch.send("\r")
        return self.pump(wait)

    def key(self, k, wait=8):
        self.ch.send(k)
        return self.pump(wait)

    def close(self):
        self.ch.terminate(force=True); self.srv.kill()

    def transcript(self):
        import glob
        fs = glob.glob(f"{self.B}/home/.claude/projects/*/*.jsonl")
        return [json.loads(l) for f in fs for l in open(f) if l.strip()]


SQ = "🟦🟩🟧🟪"
PLAN1 = ("# Plan v1 — Test — Approved\n\n**Quick read** · 20 words · about 1 min\n\n**Summary**\n- Goal: a test.\n"
         "- Done: 0 of 2.\n- I need from you: approve.\n\n**What changed since First version**\n- First version.\n\n"
         "**Decisions:** None open.\n\n**Next steps**\n- Stage 1: LINE-A.\n- Stage 2: LINE-B.\n\nStages to finish\n"
         "2 stages: 1 build and 1 check by you.\n1. Build it · Claude · Build · proof: tests · size: S\n"
         "2. Merge it · You · Check · stop: merge\n\nTechnical details\n- none\n")
PLAN2 = PLAN1.replace("# Plan v1 — Test — Approved", "# Plan v1 Rev 2 — Test — Awaiting approval").replace(
    "- Stage 2: LINE-B.", "- Stage 2: LINE-B, now green.")

if "window" in WANT:   # the program alone: four ways to add marks
    hook = os.path.join(BASE, "window-hook.py"); os.makedirs(BASE, exist_ok=True)
    open(hook, "w").write(
        "import json,sys,os\nd=json.load(sys.stdin);inp=dict(d.get('tool_input') or {});m=os.environ['HMODE']\n"
        "f=inp.get('planFilePath') or '';p=inp.get('plan') or (open(f).read() if f and os.path.exists(f) else '')\n"
        "new=p.replace('LINE-B','\\U0001F7E9 **Rev 2** \\u2014 LINE-B')\nout={'hookEventName':'PreToolUse'}\n"
        "if m=='file' and f: open(f,'w').write(new)\n"
        "if m=='allow': out.update(permissionDecision='allow',updatedInput=dict(inp,plan=new))\n"
        "if m=='ask': out.update(permissionDecision='ask',updatedInput=dict(inp,plan=new))\n"
        "if m in('allow','ask'): print(json.dumps({'hookSpecificOutput':out}))\n")
    for m in ("none", "file", "allow", "ask"):
        B = setup("window-" + m, {"PreToolUse": [{"matcher": "ExitPlanMode", "hooks": [{"type": "command",
                                                                                        "command": f"python3 {hook}"}]}]})
        r = Run(B, [{"text": "Writing.", "tools": [{"id": "w1", "name": "Write", "input": {"file_path": "PLANPATH", "content": PLAN1.replace("Approved", "Awaiting approval")}}]},
                    {"text": "Here is the plan.", "tools": [{"id": "p1", "name": "ExitPlanMode", "input": {}}]},
                    {"text": "DONE-AFTER-PLAN"}], env_extra={"HMODE": m})
        s = r.type("make a plan", 18); r.close()
        shown = "Would you like to proceed?" in s
        marks = "Rev 2 — LINE-B" in s or "🟩 Rev 2" in s
        auto = "User approved Claude's plan" in s
        print(f"      window/{m}: window shown={shown} marks on screen={marks} approved without the owner={auto}")
        if m == "file":
            say("window: marks written into the plan file show in the window, and the owner still approves", shown and marks and not auto, s[-600:])
        if m == "allow":
            say("window: 'allow' approves the plan without the owner (why the check never answers allow)", auto and not marks, s[-600:])
        if m == "ask":
            say("window: 'ask' with a changed plan shows no marks (the window reads the plan file)", shown and not marks, s[-600:])

if "plan" in WANT:   # the real plan check: Rev 2 of an approved Plan v1
    B = setup("plan", dispatch_hooks({"UserPromptSubmit": None, "PreToolUse": "ExitPlanMode|AskUserQuestion|Write|Edit"}),
              {"plans/test-v1.md": PLAN1})
    r = Run(B, [{"text": "Writing.", "tools": [{"id": "w1", "name": "Write", "input": {"file_path": "PLANPATH", "content": PLAN2}}]},
                {"text": "Here is Rev 2.", "tools": [{"id": "p1", "name": "ExitPlanMode", "input": {}}]},
                {"text": "DONE-AFTER-APPROVAL"}])
    s = r.type("show me the change as a Rev", 20)
    shown = "Would you like to proceed?" in s
    say("plan: the plan check passes the Rev of an approved plan at once and the window shows it", shown
        and "sent back" not in r.all, s[-800:])
    say("plan: the changed line carries the coloured Rev 2 mark in the window", re.search(r"Rev 2\*{0,2} — Stage 2: LINE-B, now green", s), s[-800:])
    say("plan: the window waits for the owner (no approval by the check)", "User approved" not in s, s[-300:])
    s = r.key("2", 10)   # "Yes, manually approve edits"
    if "DONE-AFTER-APPROVAL" not in r.all:
        s = r.key("\r", 10)
    tr = r.transcript(); r.close()
    kept = [x.get("toolUseResult") for x in tr if isinstance(x.get("toolUseResult"), dict) and "plan" in x["toolUseResult"]]
    say("plan: the plan Claude Code kept at the approval holds the marks (the B trial passes)",
        kept and any(q in kept[-1]["plan"] for q in SQ), (kept[-1]["plan"][:200] if kept else "no approval record", s[-300:]))
    lp = open(f"{B}/proj/.claude/state/live-proof.jsonl").read() if os.path.exists(f"{B}/proj/.claude/state/live-proof.jsonl") else ""
    say("plan: live proof says the marks were written into the plan file", "written into the plan file" in lp, lp[-300:])

QUESTION = {"questions": [{"question": "Keep the row colour?", "header": "Row", "multiSelect": False, "options": [
    {"label": "Keep (Recommended)", "description": "Nothing changes. Ends here."},
    {"label": "Change", "description": "A new colour. Brings back: one picture check."}]}]}
if "ask" in WANT:
    B = setup("ask", dispatch_hooks({"UserPromptSubmit": None, "PreToolUse": "ExitPlanMode|AskUserQuestion"}))
    r = Run(B, [{"text": "One question.", "tools": [{"id": "q1", "name": "AskUserQuestion", "input": QUESTION}]},
                {"text": "Notice first.", "tools": [{"id": "n1", "name": "PushNotification", "input": {"message": "Test: 1 question waiting", "status": "proactive"}}]},
                {"text": "Asking again.", "tools": [{"id": "q2", "name": "AskUserQuestion", "input": QUESTION}]},
                {"text": "ANSWER-RECEIVED"}], mode="default")
    s = r.type("ask me one question", 25)
    log = open(f"{B}/req.log", encoding="utf-8").read()
    say("ask: the first question without a notice is refused by the check", "First send me one phone notice" in log, log[-500:])
    say("ask: after the notice the question window opens with the recommended option first",
        "Keep (Recommended)" in s and "Ends here." in s, s[-700:])
    r.close()

WAIT = ("Round 1 is ready.\n\nConfidence: High · Status: Checked\n\n**❓ Decisions**\n1. Keep the row colour? Recommend: keep. "
        "Ends here.\n\n---\n> 📌 **Result:** Waiting on your decision. Round 1 is built.\n> 👉 **I need from you:** Answer the "
        "one question.\n> ➡️ **Next:** I finish Round 1.")
if "notice" in WANT:
    B = setup("notice", dispatch_hooks({"UserPromptSubmit": None, "PreToolUse": "ExitPlanMode|AskUserQuestion", "Stop": None}))
    r = Run(B, [{"text": WAIT},
                {"text": "", "tools": [{"id": "n1", "name": "PushNotification", "input": {"message": "Test: 1 question waiting", "status": "proactive"}}]},
                {"text": "Notice sent."}, {"text": "UNEXPECTED-THIRD-ANSWER"}], mode="default")
    s = r.type("finish round 1", 30)
    log = open(f"{B}/req.log", encoding="utf-8").read()
    say("notice: the waiting answer without a notice is sent back once", "No phone notice went out for this stop" in log, log[-400:])
    say("notice: the session sent the notice and ended with 'Notice sent.'", "Notice sent." in s, s[-500:])
    say("notice: the answer is not written twice and nothing more is sent back", r.all.count("Round 1 is ready.") >= 1
        and "UNEXPECTED-THIRD-ANSWER" not in r.all and log.count("No phone notice went out") == 1, s[-500:])
    r.close()

if "lag" in WANT:
    probe = os.path.join(BASE, "lag-probe.py"); os.makedirs(BASE, exist_ok=True)
    open(probe, "w").write(
        "import json,sys,os\nd=json.load(sys.stdin)\nlast=''\n"
        "for l in open(d['transcript_path'],encoding='utf-8'):\n"
        "    r=json.loads(l)\n"
        "    if r.get('type')=='assistant':\n"
        "        tx=[b.get('text','') for b in (r.get('message') or {}).get('content') or [] if isinstance(b,dict) and b.get('type')=='text']\n"
        "        if tx: last='\\n'.join(tx)\n"
        "open(os.environ['PT']+'/lag.txt','a').write(('same' if last.strip()==str(d.get('last_assistant_message') or '').strip() else 'lag')+'\\n')\n")
    # a copy of the rules with one extra end-of-answer check that reads the answer the way every check does
    PC = os.path.join(BASE, "central-probe"); shutil.rmtree(PC, ignore_errors=True); shutil.copytree(CENTRAL, PC)
    open(os.path.join(PC, "hooks", "zz-lag-check.py"), "w").write(
        "import json,os\nfrom _common import read_hook_input, read_transcript, last_assistant_text\nd=read_hook_input()\n"
        "seen=last_assistant_text(read_transcript(d.get('transcript_path'))).strip()\n"
        "open(os.environ['PT']+'/check-read.txt','a').write(('same' if seen==str(d.get('last_assistant_message') or '').strip() else 'old')+'\\n')\n")
    _cf = json.load(open(os.path.join(PC, "hooks", "config.json"), encoding="utf-8")); _cf["dispatch"]["Stop"].insert(0, "zz-lag-check.py")
    json.dump(_cf, open(os.path.join(PC, "hooks", "config.json"), "w", encoding="utf-8"))
    hooks = {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": f"python3 -B {PC}/hooks/dispatch.py"}]}],
             "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": f"python3 -B {PC}/hooks/dispatch.py"}]}],
             "Stop": [{"hooks": [{"type": "command", "command": f"python3 {probe}"},
                                 {"type": "command", "command": f"python3 -B {PC}/hooks/dispatch.py"}]}]}
    B = setup("lag", hooks)
    _s = json.load(open(f"{B}/proj/.claude/settings.json")); _s["permissions"] = {"allow": ["Bash(git push:*)"]}
    json.dump(_s, open(f"{B}/proj/.claude/settings.json", "w"))
    subprocess.run(f"git init -q --bare {B}/remote.git && git remote add origin {B}/remote.git && git switch -q -c claude/x",
                   shell=True, cwd=B + "/proj")
    OK = ("Checked.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Still being worked on. Step 1 is done.\n"
          "> 👉 **I need from you:** Nothing now.\n> ➡️ **Next:** Step 2.")
    MERGE = OK.replace("Still being worked on. Step 1 is done.", "Ready to merge. Step 2 is done.").replace(
        "Nothing now.", "Merge #1.")
    steps = [{"text": OK}, {"text": OK}, {"text": "", "tools": [{"id": "b1", "name": "Bash", "input": {"command": "git push -q origin claude/x"}}]},
             {"text": MERGE}, {"text": OK}, {"text": OK}]
    r = Run(B, steps, mode="default")
    for prompt in ("one", "two", "push it"):
        r.type(prompt, 15)
    r.close()
    lags = open(f"{B}/lag.txt").read().split() if os.path.exists(f"{B}/lag.txt") else []
    log = open(f"{B}/req.log", encoding="utf-8").read()
    print(f"      lag: Stops seen {len(lags)}, session file behind the final answer {lags.count('lag')}")
    reads = open(f"{B}/check-read.txt").read().split() if os.path.exists(f"{B}/check-read.txt") else []
    print(f"      lag: what the checks read: {reads.count('same')} final answers, {reads.count('old')} older answers")
    say("lag: every end-of-answer check reads the final answer, even when the file lags", reads and "old" not in reads, (lags, reads))
    say("lag: the merge request without a check reading is sent back (the check read the right answer)",
        "Before you ask me to merge, read the checks" in log, (lags, log[-300:]))

print(f"\nreal program: {sum(ok_all)} of {len(ok_all)} passed")
