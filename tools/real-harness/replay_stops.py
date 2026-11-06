#!/usr/bin/env python3
"""v3.3.7 (pieces 4 and 5): replay real Stops of a session file through one rules version's Stop checks (dispatch.py),
in a temporary project. The transcript is the real session up to the Stop; the Stop input carries the real final
answer. The state the 3.3.6 merge gate read (pr-summary.json with the checks read) is seeded as it was.
Usage: python3 replay_stops.py <repo dir> <session.jsonl> <record index> [<record index> ...]
  A record index is the line of the real "Stop hook feedback" record (or of a stop_hook_summary record).
Prints one line per Stop: Edmonton time, sent back or not, and the first words of each reason."""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta

R = os.path.abspath(sys.argv[1]); H = os.path.join(R, "central", "hooks")
PY = sys.executable


def edm(ts):
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    y = t.year
    mar = datetime(y, 3, 8 + (6 - datetime(y, 3, 8).weekday()) % 7, 9, tzinfo=t.tzinfo)
    nov = datetime(y, 11, 1 + (6 - datetime(y, 11, 1).weekday()) % 7, 8, tzinfo=t.tzinfo)
    return (t - timedelta(hours=6 if mar <= t < nov else 7)).strftime("%b %d %I:%M %p").replace(" 0", " ")


def last_text(recs):
    for r in reversed(recs):
        if r.get("type") == "assistant" and not r.get("isSidechain"):
            c = (r.get("message") or {}).get("content")
            if isinstance(c, list):
                t = "\n".join(b.get("text") or "" for b in c if isinstance(b, dict) and b.get("type") == "text").strip()
                if t:
                    return t
    return ""


def replay(path, idx, env_extra=None):
    lines = open(path, encoding="utf-8").read().splitlines()
    recs = [json.loads(l) for l in lines[:idx] if l.strip()]
    # the Stop that produced a send-back ran on the records before the feedback record
    while recs and recs[-1].get("type") == "system":
        recs.pop()
    sid = next((r.get("sessionId") for r in recs if r.get("sessionId")), "s1")
    P = tempfile.mkdtemp(prefix="hz-stop-")
    os.makedirs(os.path.join(P, ".claude", "state"))
    subprocess.run("git init -q -b main && git config user.email t@t && git config user.name t && git commit -q "
                   "--allow-empty -m c && git switch -qc work-1", shell=True, cwd=P)
    T = os.path.join(P, ".claude", "t.jsonl")
    with open(T, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    url = ""
    for r in recs:
        m = re.search(r"https://github\.com/[^\s\"'\\]+/pull/\d+", json.dumps(r.get("toolUseResult") or "") +
                      json.dumps((r.get("message") or {}).get("content") or ""))
        url = m.group(0) if m else url
    st = os.path.join(P, ".claude", "state")
    if url:   # what notice-reminder had written after the pull request opened and the checks were read
        json.dump({"url": url, "checks": "passed", "session": sid}, open(os.path.join(st, "pr-summary.json"), "w"))
        open(os.path.join(st, "pr-summary.md"), "w", encoding="utf-8").write("**Completion:** … **GitHub checks:** passed\n")
    e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
    e.update(CLAUDE_PROJECT_DIR=P, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", HZ_RULES_FIRST_OFF="1", HZ_PR_LIVE_OFF="1")
    e.update(env_extra or {})
    inp = {"hook_event_name": "Stop", "session_id": sid, "transcript_path": T, "stop_hook_active": False,
           "last_assistant_message": last_text(recs)}
    r = subprocess.run([PY, os.path.join(H, "dispatch.py")], input=json.dumps(inp), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=e, cwd=P)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    except ValueError:
        out = {"raw": r.stdout[-300:]}
    blocked = out.get("decision") == "block"
    reasons = re.findall(r"(?m)^\d+\.\s*(.{0,70})", out.get("reason") or "") if blocked else []
    if blocked and not reasons:
        reasons = [(out.get("reason") or "")[:70]]
    return {"when": edm(recs[-1]["timestamp"]) if recs and recs[-1].get("timestamp") else "?", "sent_back": blocked,
            "reasons": reasons}


if __name__ == "__main__":
    rows = [replay(sys.argv[2], int(i)) for i in sys.argv[3:]]
    for d in rows:
        print(f"{d['when']:>16}  {'SENT BACK' if d['sent_back'] else 'passes   '}  " + " | ".join(d["reasons"]))
    print("RESULT " + json.dumps(rows, ensure_ascii=False))
