#!/usr/bin/env python3
"""v3.3.7 (piece 2): replay every plan Write, Edit and ExitPlanMode of a real session file through plan-write-marks.py
and plan-guard.py of one rules version, in a temporary project. Each plan edit is one whole-file write, as the hook
does (the Edit is applied to the replayed file with the marks taken out). The transcript each hook reads is the real
session up to that step. Prints one line per showing: Edmonton time, title, Rev, marks, and the "What changed since"
number against the newest mark.
Usage: python3 replay_plan_showings.py <repo dir> <session.jsonl>
       python3 replay_plan_showings.py <repo dir> --synthetic      (one plan file, 4 showings, plus a higher Plan vN)
Prints a JSON line "RESULT {...}" at the end for other tests."""
import json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta

R = os.path.abspath(sys.argv[1]); H = os.path.join(R, "central", "hooks")
sys.path.insert(0, H)
import planmarks  # noqa: E402

PY = sys.executable
SQ = "🟦🟩🟧🟪🟥🟨🟫⬛"


def edm(ts):
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    # MDT (UTC-6) from the second Sunday of March, MST (UTC-7) from the first Sunday of November
    y = t.year
    mar = datetime(y, 3, 8 + (6 - datetime(y, 3, 8).weekday()) % 7, 9, tzinfo=t.tzinfo)
    nov = datetime(y, 11, 1 + (6 - datetime(y, 11, 1).weekday()) % 7, 8, tzinfo=t.tzinfo)
    return (t - timedelta(hours=6 if mar <= t < nov else 7)).strftime("%b %d %I:%M %p").replace(" 0", " ")


class Proj:
    def __init__(self):
        self.P = tempfile.mkdtemp(prefix="hz-planreplay-")
        os.makedirs(os.path.join(self.P, ".claude", "state")); os.makedirs(os.path.join(self.P, "plans"))
        subprocess.run("git init -q -b main && git config user.email t@t && git config user.name t && git commit -q "
                       "--allow-empty -m c && git switch -qc work-1", shell=True, cwd=self.P)
        self.T = os.path.join(self.P, ".claude", "t.jsonl")
        open(self.T, "w").close()

    def env(self):
        e = {k: v for k, v in os.environ.items() if not k.startswith("HZ_")}
        e.update(CLAUDE_PROJECT_DIR=self.P, PYTHONDONTWRITEBYTECODE="1", HZ_RULES_FIRST_OFF="1", PYTHONUTF8="1",
                 PYTHONIOENCODING="utf-8")
        return e

    def hook(self, script, inp):
        r = subprocess.run([PY, os.path.join(H, script)], input=json.dumps(inp), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=self.env(), cwd=self.P)
        try:
            return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        except ValueError:
            return {"raw": r.stdout[-400:], "err": r.stderr[-400:]}

    def path(self, name):
        return os.path.join(self.P, "plans", name)

    def write(self, name, content, sid="s1"):
        inp = {"hook_event_name": "PreToolUse", "tool_name": "Write", "session_id": sid, "transcript_path": self.T,
               "tool_input": {"file_path": self.path(name), "content": content}}
        out = self.hook("plan-write-marks.py", inp)
        up = ((out.get("hookSpecificOutput") or {}).get("updatedInput") or {}).get("content")
        open(self.path(name), "w", encoding="utf-8", newline="").write(up if isinstance(up, str) else content)

    def show(self, name, sid="s1"):
        text = open(self.path(name), encoding="utf-8").read()
        inp = {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "session_id": sid,
               "transcript_path": self.T, "tool_input": {"plan": text, "planFilePath": self.path(name)}}
        out = self.hook("plan-guard.py", inp)
        hs = out.get("hookSpecificOutput") or {}
        deny = hs.get("permissionDecision") == "deny"
        why = str(hs.get("permissionDecisionReason") or "")
        if deny and "added the coloured change marks" in why:   # the marks round: shown again with the file's text
            text2 = open(self.path(name), encoding="utf-8").read()
            inp["tool_input"]["plan"] = text2
            out = self.hook("plan-guard.py", inp)
            hs = out.get("hookSpecificOutput") or {}
            deny = hs.get("permissionDecision") == "deny"; why = str(hs.get("permissionDecisionReason") or "")
        final = open(self.path(name), encoding="utf-8").read()
        d = describe(final, deny, why)
        try:   # the Rev the check counted (a Rev whose changes are all in Technical details has no marks line)
            st = json.load(open(os.path.join(self.P, ".claude", "state", "plan-store.json"), encoding="utf-8"))
            d["rev"] = int((st["plans"].get(st.get("last") or "") or {}).get("rev") or d["rev"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return d


def describe(final, deny, why):
    m = re.search(r"\*\*Rev (\d+)\*\* marks (\d+) changed line", final)
    newest = int(m.group(1)) if m else None
    marks = int(m.group(2)) if m else 0
    s = re.search(r"(?i)What changed since\s*\**\s*Rev\s*(\d+)", final)
    since = int(s.group(1)) if s else None
    title = next((l for l in final.splitlines() if re.match(r"^#*\s*Plan v\d+", l)), "")
    rev = re.search(r"Rev (\d+)", title)
    title_marked = any(ch in title for ch in SQ)
    return {"title": re.sub(r"^#+\s*", "", title)[:70], "rev": int(rev.group(1)) if rev else (newest or 1),
            "marks": marks, "newest": newest, "since": since, "title_marked": title_marked, "refused": deny,
            "why": why[:160]}


def apply_edit(cur, inp):
    cur_s = planmarks.strip_marks(cur)
    edits = inp.get("edits") or [inp]
    for e in edits:
        old, new = planmarks.strip_marks(e.get("old_string") or ""), planmarks.strip_marks(e.get("new_string") or "")
        if not old or old not in cur_s:
            return None
        cur_s = cur_s.replace(old, new) if e.get("replace_all") else cur_s.replace(old, new, 1)
    return cur_s


def replay_session(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    results = {}
    for r in recs:
        m = r.get("message") or {}
        if isinstance(m.get("content"), list):
            for c in m["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    results[c.get("tool_use_id")] = (str(c.get("content")), r.get("toolUseResult"))
    p = Proj(); rows = []
    with open(p.T, "w", encoding="utf-8") as tf:
        for r in recs:
            if r.get("type") == "assistant" and not r.get("isSidechain"):
                for c in (r.get("message") or {}).get("content") or []:
                    if not isinstance(c, dict) or c.get("type") != "tool_use":
                        continue
                    n, inp = c["name"], c.get("input") or {}
                    fp = str(inp.get("file_path") or inp.get("planFilePath") or "")
                    name = re.split(r"[\\/]", fp)[-1]
                    res = results.get(c["id"], ("", None))
                    if "tool_use_error" in res[0] or not re.search(r"[\\/]plans[\\/][^\\/]+\.md$", fp):
                        continue
                    tf.flush()
                    sid = r.get("sessionId") or "s1"
                    if n == "Write":
                        p.write(name, inp.get("content") or "", sid)
                    elif n in ("Edit", "MultiEdit"):
                        cur = open(p.path(name), encoding="utf-8").read() if os.path.exists(p.path(name)) else ""
                        new = apply_edit(cur, inp)
                        if new is None and isinstance(res[1], dict) and isinstance(res[1].get("originalFile"), str):
                            new = apply_edit(res[1]["originalFile"], inp)
                        if new is not None:
                            p.write(name, new, sid)
                    elif n == "ExitPlanMode" and os.path.exists(p.path(name)):
                        d = p.show(name, sid); d["when"] = edm(r["timestamp"]); d["outcome"] = (
                            "approved" if "approved your plan" in res[0] else "sent back" if "doesn't want to proceed" in res[0]
                            else "other"); rows.append(d)
            tf.write(json.dumps(r) + "\n")
    return rows


def synthetic():
    base = ("# Plan v1 — Lake panel — Awaiting approval\n\n**Summary**\n- Goal: the lake panel shows depth. Done when: "
            "the panel test passes.\n- I need from you: approve.\n\n**What changed since Rev 1** (first showing: First "
            "version)\n- First version.\n\n**Decisions:**\nIf I receive no objection, I use the recommended option for "
            "each open decision.\n1. Depth units? **A** metres (ends here) · **B** feet (brings back: a switch) · "
            "Recommend: A\n\n**Stops**\n- Merge #— and device check.\n\nTechnical details: js/lake-sheet.js\n")
    p = Proj(); f = "lake.md"; rows = []
    reject = lambda: open(p.T, "a", encoding="utf-8").write(json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x", "is_error": True, "content": "The user doesn't want to proceed with this tool use."}]}}) + "\n")

    def approve(text):
        open(p.T, "a", encoding="utf-8").write(json.dumps({"type": "user", "toolUseResult": {"plan": text, "isAgent": False,
            "filePath": p.path(f)}, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "y",
            "content": "User has approved your plan. You can now start coding."}]}}) + "\n")
    p.write(f, base); rows.append(p.show(f)); reject()                                       # (1) first version
    t2 = base.replace("Lake panel", "Lake panel with depth")                                  # (2) title reworded only
    p.write(f, t2); rows.append(p.show(f)); reject()
    t3 = t2.replace("Lake panel with depth", "Depth in the lake panel").replace("shows depth", "shows depth in metres")
    p.write(f, t3); rows.append(p.show(f)); approve(open(p.path(f), encoding="utf-8").read())  # (3) title + one line
    t4 = planmarks.strip_marks(open(p.path(f), encoding="utf-8").read()).replace("Depth in the lake panel", "Lake depth panel") \
        .replace("the panel test passes", "the panel test and the phone check pass")
    p.write(f, t4); rows.append(p.show(f))                                                   # (4) title + one line
    t5 = t4.replace("Plan v1", "Plan v2", 1)                                                  # a higher Plan vN
    p.write(f, t5); rows.append(p.show(f))
    return rows


if __name__ == "__main__":
    rows = synthetic() if sys.argv[2] == "--synthetic" else replay_session(sys.argv[2])
    for i, d in enumerate(rows, 1):
        print(f"{i:>2} {d.get('when', '')!s:>16}  Rev {d['rev']}  marks {d['marks']:>3}  newest mark Rev {d['newest']}  "
              f"'What changed since Rev {d['since']}'  title marked {d['title_marked']}  "
              f"{'REFUSED ' + d['why'][:60] if d['refused'] else ''} {d.get('outcome', '')} · {d['title'][:46]}")
    print("RESULT " + json.dumps(rows, ensure_ascii=False))
