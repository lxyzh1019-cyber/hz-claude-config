#!/usr/bin/env python3
"""v3.3.7 (piece 3): facts read from the session file itself, shared by stats.py, pr_report.py and tools/scorecard.py.
- permission waits: a step whose result carries permissionDecision with source user_temporary or user_permanent waited
  for me (Builds 2-4: 10 git questions, 260 min). That time is a wait for me, never work and never a "slowest step".
- refusals and send-backs: PreToolUse hook refusals (tool results the hook refused) and Stop blocks ("Stop hook
  feedback" records), counted from the session file, not from the hooks' own state (Build 3 showed "send-backs 0").
- helper time: each helper's own file (subagents/agent-*.jsonl), first to last record. A background helper's hand-over
  returns at once, so its time in the main file is about 0 (Build 4: Explore 1.8 min, shown 0.0)."""
import glob, json, os, re
from datetime import datetime

USER_SOURCES = ("user_temporary", "user_permanent")
_HOOK_REFUSAL = re.compile(r"(?i)^\W*(error:\s*)?(PreToolUse:\S+ hook error|PreToolUse:\S+ hook blocking error)|hook error:|blocked by [^\n]{0,40}hook")


def ts(r):
    try:
        return datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def load(path):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def _blocks(r):
    c = (r.get("message") or {}).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def tool_uses(recs):
    """{tool_use_id: (timestamp, name, input, record)} for the main session."""
    out = {}
    for r in recs:
        if r.get("type") == "assistant" and not r.get("isSidechain"):
            for b in _blocks(r):
                if b.get("type") == "tool_use":
                    out[b.get("id")] = (ts(r), str(b.get("name") or ""), b.get("input") or {}, r)
    return out


def results(recs):
    """{tool_use_id: (timestamp, text, is_error, record)}."""
    out = {}
    for r in recs:
        if r.get("type") == "user" and not r.get("isSidechain"):
            for b in _blocks(r):
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    t = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                    out[b.get("tool_use_id")] = (ts(r), t, bool(b.get("is_error")), r)
    return out


def permission_waits(recs, uses=None, res=None):
    """[{id, name, command, secs, start, branch}] for steps that waited for my permission click."""
    uses = uses if uses is not None else tool_uses(recs)
    res = res if res is not None else results(recs)
    out = []
    for tid, (t1, _txt, _err, r) in res.items():
        pd = r.get("permissionDecision") or {}
        if pd.get("source") in USER_SOURCES and tid in uses:
            t0, name, inp, ur = uses[tid]
            out.append({"id": tid, "name": name, "command": str(inp.get("command") or ""),
                        "secs": max((t1 or 0) - (t0 or 0), 0) if t0 and t1 else 0, "start": t0,
                        "branch": str(r.get("gitBranch") or ur.get("gitBranch") or ""),
                        "reason": str(pd.get("reasonCode") or "")})
    return out


def wait_secs_by_id(recs, uses=None, res=None):
    return {w["id"]: w["secs"] for w in permission_waits(recs, uses, res)}


def is_hook_refusal(text, rec=None):
    pd = (rec or {}).get("permissionDecision") or {}
    if pd.get("source") == "hook" and pd.get("decision") in ("reject", "deny"):
        return True
    return bool(_HOOK_REFUSAL.search(str(text or "")[:300]))


def stop_blocks(recs):
    """Stop hook send-backs: the user records the program writes with the check's text."""
    out = []
    for r in recs:
        if r.get("type") == "user" and not r.get("isSidechain"):
            c = (r.get("message") or {}).get("content")
            t = c if isinstance(c, str) else " ".join(str(b.get("text") or "") for b in _blocks(r) if b.get("type") == "text")
            if t.lstrip().startswith("Stop hook feedback"):
                out.append({"ts": ts(r), "text": t})
    return out


def refusals(recs, uses=None, res=None):
    """[{ts, id, name, text}] for steps a hook refused (PreToolUse)."""
    uses = uses if uses is not None else tool_uses(recs)
    res = res if res is not None else results(recs)
    out = []
    for tid, (t1, txt, err, r) in res.items():
        if err and is_hook_refusal(txt, r):
            out.append({"ts": t1, "id": tid, "name": (uses.get(tid) or (0, ""))[1], "text": txt[:300]})
    return sorted(out, key=lambda x: x["ts"] or 0)


_TAG = re.compile(r"\n\s*(?:\d+\.\s*)?\[([a-z][a-z0-9-]*)\]")
_LEAD = re.compile(r"^\W*(?:Stop hook feedback:|PreToolUse:\S+ hook (?:blocking )?error:)\s*")


def check_tags(text):
    """The check names from a send-back's message tags ('[completion-guard] ...'); 3.3.6 and older wrote none."""
    return list(dict.fromkeys(_TAG.findall("\n" + _LEAD.sub("", str(text or "")))))


def sendback_count(recs):
    """Hook refusals plus Stop blocks, from the session file; by_check names each check from its message tag."""
    rf, sb = refusals(recs), stop_blocks(recs)
    by = {}
    for x in rf + sb:
        for name in check_tags(x["text"]) or ["untagged"]:
            by[name] = by.get(name, 0) + 1
    return {"refusals": len(rf), "stop_blocks": len(sb), "total": len(rf) + len(sb), "by_check": by}


def helper_files(transcript_path):
    """[(agentType, toolUseId, records)] from the session's subagents folder (and workflow helpers)."""
    base = os.path.splitext(str(transcript_path or ""))[0]
    out, seen = [], set()
    for pat in (os.path.join(base, "subagents", "*.jsonl"), os.path.join(base, "subagents", "workflows", "*", "agent-*.jsonl")):
        for f in sorted(glob.glob(pat)):
            k = os.path.normcase(os.path.realpath(f))
            if k in seen:
                continue
            seen.add(k)
            try:
                meta = json.load(open(f[:-len(".jsonl")] + ".meta.json", encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            out.append((str(meta.get("agentType") or "helper"), str(meta.get("toolUseId") or ""), load(f)))
    return out


def helper_secs(transcript_path):
    """{agentType: seconds} from each helper's own file."""
    out = {}
    for kind, _tid, recs in helper_files(transcript_path):
        tt = [ts(r) for r in recs if ts(r) is not None]
        if tt:
            out[kind] = out.get(kind, 0) + max(tt) - min(tt)
    return out

def owner_prompt(r):
    c = (r.get("message") or {}).get("content")
    return r.get("type") == "user" and isinstance(c, str) and not c.lstrip().startswith(("<", "Another Claude session"))


def session_time(recs, away_seconds=3600, pw=None, is_test=None):
    """v3.3.7: worked time, the one definition (the summary in stats.py and scorecard check 5 use it).
    worked = actual - usage-limit stops - away (waits over away_seconds for me: an owner prompt after a long gap,
    a permission click, a question or a plan approval). Short waits for me count as worked. 'left_out' lists
    each wait taken out: (start, seconds, kind)."""
    pw = pw or {}
    is_test = is_test or (lambda c: False)
    left = []
    tl = [r for r in recs if ts(r) is not None]
    if len(tl) < 2:
        return None
    wall = ts(tl[-1]) - ts(tl[0])
    limit, stops, you, workers, gh, tests, away, away_n = 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0
    last_a, in_stop = None, None
    uses, pending, prev_t = {}, set(), None
    for r in tl:
        t_ = ts(r)
        m = r.get("message") or {}
        c = m.get("content")
        _raw0 = json.dumps(r, ensure_ascii=False) if r.get("type") in ("user", "attachment", "queue-operation") else ""
        # v3.3.7 (owner, 6 Nov): a gap over away_seconds with no tool call waiting for its result is away, whatever
        # record ends it (Build 2: 872.7 min ending in a hook attachment, 268.9 min ending in a pr-link record, both
        # counted as work). A long-running tool step stays worked time; a gap that ends in my message or in a
        # background worker's finish notice keeps its own rule below.
        if prev_t is not None and t_ - prev_t > away_seconds and not pending and in_stop is None                 and not owner_prompt(r) and "<task-notification>" not in _raw0:
            away += t_ - prev_t
            away_n += 1
            left.append((prev_t, t_ - prev_t, "idle gap ending in a " + str(r.get("subtype") or r.get("type"))
                         + " record"))
            last_a = t_ if last_a is not None else last_a
        prev_t = t_
        for b in c if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                pending.discard(b.get("tool_use_id"))
        if r.get("type") == "assistant":
            if "hit your session limit" in json.dumps(c or "", ensure_ascii=False):
                in_stop, stops = t_, stops + 1
            last_a = t_
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    uses[b.get("id")] = (t_, b)
                    pending.add(b.get("id"))
        _cs = (r.get("message") or {}).get("content")
        _raw = json.dumps(r, ensure_ascii=False) if r.get("type") in ("user", "attachment", "queue-operation") else ""
        if "<task-notification>" in _raw and r.get("operation") != "remove" \
                and last_a is not None and in_stop is None:
            workers += max(t_ - last_a, 0)     # v3.2.0: the main session idles until a background worker reports
            last_a = t_
        if owner_prompt(r):
            if in_stop is not None:
                limit += t_ - in_stop
                in_stop = None
            elif last_a is not None:
                if t_ - last_a > away_seconds:     # v3.2.0: sleep or out — shown apart, left out of the shares
                    away += t_ - last_a
                    away_n += 1
                    left.append((last_a, t_ - last_a, "gap before my next message"))
                else:
                    you += t_ - last_a
        for b in c if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                t0, u = uses[b["tool_use_id"]]
                d = max(t_ - t0, 0)
                n, cmd = u.get("name"), str((u.get("input") or {}).get("command") or "")
                _w = min(pw.get(b["tool_use_id"], 0), d)   # v3.3.7: a permission click is a wait for me
                if _w and n not in ("AskUserQuestion", "ExitPlanMode"):
                    if _w > away_seconds:
                        away += _w
                        away_n += 1
                        left.append((t0, _w, "permission click on " + str(n)))
                    else:
                        you += _w
                    d -= _w
                if n in ("AskUserQuestion", "ExitPlanMode"):
                    if d > away_seconds:
                        away += d
                        away_n += 1
                        left.append((t0, d, "answer to " + str(n)))
                    else:
                        you += d
                elif n in ("Agent", "Task"):
                    workers += d
                elif n == "Bash" and re.search(r"\bgh\s+run\b", cmd):
                    gh += d
                elif n == "Bash" and is_test(cmd):
                    tests += d
    active = max(wall - limit - away, 1)
    other = max(active - you - workers - gh - tests, 0)
    return {"wall": wall, "limit": limit, "stops": stops, "active": active, "away": away, "away_n": away_n,
            "left_out": left,
            "parts": [("short waits for you", you), ("workers", workers), ("GitHub waits", gh),
                      ("main session test runs", tests), ("main session other", other)]}
