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
