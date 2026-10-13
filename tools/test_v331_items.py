#!/usr/bin/env python3
"""v3.3.1 item test (HZ_Trout_Map session start, 13 Oct). Usage: python3 tools/test_v331_items.py <repo dir> <app clone>
 1 an old setup note is cleared once the update is merged and the setup is current (no "Do the setup update first")
 2 a question right after my message needs no phone notice; after 5 minutes it does
 3 one send-back per turn: after a send-back, new problems are saved, not sent back again
 4 no self wake-ups: ScheduleWakeup is refused; the app hook list sends it to the checks (setup 3.3.1)
 5 a wake-up with nothing of the round running gets one line ('No change.'), which passes; no 'Build 0 of 0'"""
import json, os, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta, timezone
R = os.path.abspath(sys.argv[1]); H = os.path.join(R, "central", "hooks"); APP = os.path.abspath(sys.argv[2]); V = tempfile.mkdtemp()
results = []


def res(i, name, ok, detail=""):
    results.append((i, bool(ok))); print(f"{i:>2} {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  -> {str(detail)[:200]!r}"))


def env(P):
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1"); return e


def hook(s, P, inp):
    return subprocess.run(["python3", os.path.join(H, s)], input=json.dumps(inp), capture_output=True, text=True, env=env(P), cwd=P).stdout


def tx(p, recs):
    open(p, "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs)); return p


def ts(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


# 1 the app's real setup files in a repo whose setup branch is already merged into main ('settled', as #8 on 13 Oct)
P = os.path.join(V, "app"); O = os.path.join(V, "origin.git")
subprocess.run(f"git init -q --bare {O} && git init -q -b main {P}", shell=True)
shutil.copytree(os.path.join(APP, ".claude"), os.path.join(P, ".claude"), dirs_exist_ok=True)
for f in ("CLAUDE.md", "FEATURES.md", "WORKING_RECORD.md"):
    if os.path.exists(os.path.join(APP, f)):
        shutil.copy(os.path.join(APP, f), P)
subprocess.run("git config user.email t@t && git config user.name t && git add -A && git commit -qm base && "
               f"git remote add origin {O} && git switch -qc hz-setup-update-3.2.17 && git commit -q --allow-empty -m 'Setup update' && "
               "git switch -q main && git merge -q --no-ff hz-setup-update-3.2.17 -m 'Merge pull request #8 from lxyzh1019-cyber/hz-setup-update-3.2.17' && git push -q origin main hz-setup-update-3.2.17",
               shell=True, cwd=P)
os.makedirs(os.path.join(P, ".claude", "state"), exist_ok=True)
json.dump({"branch": "hz-setup-update-3.2.17"}, open(os.path.join(P, ".claude", "state", "setup-pending.json"), "w"))
ANS = "Hi.\n\nConfidence: High · Status: Checked\n\n---\n> 📌 **Result:** Waiting on your decision.\n> 👉 **I need from you:** Type your question.\n> ➡️ **Next:** I answer it."
T = tx(os.path.join(V, "t1.jsonl"), [{"type": "user", "timestamp": ts(1), "message": {"role": "user", "content": "hi"}},
                                     {"type": "assistant", "timestamp": ts(0), "message": {"role": "assistant", "content": [{"type": "text", "text": ANS}]}}])
o = hook("setup-guard.py", P, {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": T})
res(1, "no 'Do the setup update first' after the update is merged", "Do the setup update first" not in o, o[:200])
res(1, "  ...and the old note is removed", not os.path.exists(os.path.join(P, ".claude", "state", "setup-pending.json")))

# 2 questions
Q = {"questions": [{"question": "What today?", "header": "Today", "options": [
    {"label": "Just a question (Recommended)", "description": "No files change. Ends here."},
    {"label": "Fix the map", "description": "One plan. Brings back: your approval."}]}]}
def ask(minutes_ago, name):
    T2 = tx(os.path.join(V, name + ".jsonl"), [{"type": "user", "timestamp": ts(minutes_ago), "message": {"role": "user", "content": "hi"}}])
    return hook("ask-guard.py", P, {"tool_name": "AskUserQuestion", "session_id": name, "transcript_path": T2, "tool_input": Q})
o = ask(0.2, "a1")
res(2, "a question right after my message passes without a notice", '"deny"' not in o, o[:200])
o = ask(12, "a2")
res(2, "a question 12 minutes after my message needs the notice first", '"deny"' in o and "PushNotification" in o, o[:200])

# 3 one send-back per turn
T3 = tx(os.path.join(V, "t3.jsonl"), [{"type": "user", "timestamp": ts(20), "message": {"role": "user", "content": "go"}},
                                      {"type": "assistant", "timestamp": ts(0), "message": {"role": "assistant", "content": [{"type": "text", "text": ANS}]}}])
o = hook("dispatch.py", P, {"hook_event_name": "Stop", "session_id": "s3", "transcript_path": T3, "stop_hook_active": True})
res(3, "after a send-back, a missing notice is saved, not sent back again", '"block"' not in o, o[:200])
o = hook("dispatch.py", P, {"hook_event_name": "Stop", "session_id": "s4", "transcript_path": T3})
res(3, "  ...the first answer of a turn is still checked", '"block"' in o, o[:200])
# 4 wake-ups
o = hook("dispatch.py", P, {"hook_event_name": "PreToolUse", "session_id": "w", "transcript_path": T3, "tool_name": "ScheduleWakeup",
                            "tool_input": {"prompt": "check the pull request", "delaySeconds": 3000}})
res(4, "a self wake-up is refused: a stop ends the turn", '"deny"' in o and "Do not schedule a re-check" in o, o[:200])
C = os.path.join(R, "central")
st = open(os.path.join(C, "stub-files", "settings.json"), encoding="utf-8").read()
res(4, "the app hook list sends ScheduleWakeup to the checks; setup expects 3.3.1", "|ScheduleWakeup|" in st
    and '"version": "3.3.1"' in open(os.path.join(H, "_common.py"), encoding="utf-8").read())
# 5 a wake-up with nothing running
W = tx(os.path.join(V, "w.jsonl"), [{"type": "user", "timestamp": ts(30), "message": {"role": "user", "content": "go"}},
                                     {"type": "assistant", "timestamp": ts(29), "message": {"role": "assistant", "content": [{"type": "text", "text": ANS}]}}])
o = hook("plan-gate.py", P, {"hook_event_name": "UserPromptSubmit", "session_id": "w5", "transcript_path": W,
                             "prompt": "<task-notification><task-id>x</task-id><status>completed</status></task-notification>"})
res(5, "a wake-up with nothing of the round running asks for one line, not a report", "No change." in o and "full report" not in o, o[:250])
W2 = tx(os.path.join(V, "w2.jsonl"), [{"type": "user", "timestamp": ts(30), "message": {"role": "user", "content": "go"}},
                                      {"type": "assistant", "timestamp": ts(0), "message": {"role": "assistant", "content": [{"type": "text", "text": "No change."}]}}])
o = hook("dispatch.py", P, {"hook_event_name": "Stop", "session_id": "w6", "transcript_path": W2})
res(5, "'No change.' passes the end-of-answer checks", '"block"' not in o, o[:200])
res(5, "no 'Build n of m' when there is no plan", "leave \"\n" in open(os.path.join(H, "_common.py"), encoding="utf-8").read()
    or "when there is no plan" in open(os.path.join(H, "_common.py"), encoding="utf-8").read())
shutil.rmtree(V, ignore_errors=True)
items = sorted({i for i, _ in results}); ok = [i for i in items if all(o for j, o in results if j == i)]
print(f"\nchecks passed {sum(o for _, o in results)} of {len(results)} · items fully passing {len(ok)} of {len(items)}: {ok}")
