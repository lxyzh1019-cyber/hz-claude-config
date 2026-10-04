#!/usr/bin/env python3
"""Stop hook that never blocks. It speaks to me through Claude Code's systemMessage (no AI turn, no cost) — the
one notice my app is proven to show ("Stop says: …"):
- the version line `Rules v<version> · <branch> · setup <state>`, on the session's first reply and with every
  summary (the session-start notice is not shown in the desktop app, so the version moved here in v3.1.23);
- when a reply is a finished answer (Status Checked or Validated), a short session summary: tokens and time by
  model (main session and helpers), how much of the tokens was re-reading, hand-overs, refusals and send-backs.
Helper (subagent) records are read from the main transcript (sidechain records), from the session's subagents
folder, or — when neither exists — from the totals Claude Code attaches to each finished hand-over.
Every run logs what it showed, or why it showed nothing, to .claude/state/stats.jsonl."""
import glob, json, os, re, subprocess, sys
from datetime import datetime
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, read_stats, log,
                     central_version, PROJECT_DIR, STATE_DIR)

data = read_hook_input()
cfg = load_config()
tp = data.get("transcript_path") or ""
sid = data.get("session_id") or ""
records = read_transcript(tp)
text = last_assistant_text(records)
m = re.search(cfg["validation_line_pattern"], text or "")
final = bool(m) and m.group(2).split()[0] in ("Checked", "Validated")


def version_line():
    try:
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_DIR, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError, UnicodeError):
        branch = "unknown"
    try:
        from stubcheck import stub_status
        stub = stub_status(cfg, PROJECT_DIR)
    except Exception:
        stub = ""
    if os.path.exists(os.path.join(STATE_DIR, "setup-pending.json")):
        stub = "waiting"   # rewritten on disk at session start; the setup pull request is not merged yet
    elif stub.startswith("OUTDATED"):
        try:   # the setup-update branch exists: the pull request is waiting for my merge
            refs = subprocess.run(["git", "for-each-ref", "--format=%(refname)", "refs/heads/hz-setup-update-*",
                                   "refs/remotes/origin/hz-setup-update-*"], cwd=PROJECT_DIR, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError, UnicodeError):
            refs = ""
        stub = "waiting" if refs else stub
    word = ("current" if stub.startswith("current") else "waiting for your merge" if stub.startswith("waiting")
            else "needs attention" if stub else "unknown")
    return f"Rules v{central_version()} · {branch} · setup {word}"


shown_path = os.path.join(STATE_DIR, "version-shown.json")
try:
    shown = json.load(open(shown_path, encoding="utf-8"))
except (OSError, ValueError):
    shown = {}


def mark_shown():
    shown.clear() if len(shown) > 50 else None
    shown[sid] = True
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(shown, open(shown_path, "w", encoding="utf-8"))
    except OSError:
        pass


if not final:
    if sid and not shown.get(sid):
        mark_shown()
        log("stats", {"shown": "version only", "why": "first reply, not a finished answer"})
        print(json.dumps({"systemMessage": version_line()}))
    else:
        log("stats", {"shown": "nothing", "why": "not a finished answer (Status Checked or Validated)"})
    sys.exit(0)


def label(model):
    s = (model or "").lower()
    for k in ("fable", "opus", "sonnet", "haiku"):
        if k in s:
            return k.capitalize()
    return model or "other"


def ts(rec):
    try:
        return datetime.fromisoformat(str(rec.get("timestamp", "")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def is_prompt(rec):
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    return isinstance(c, str) or (isinstance(c, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c))


tokens, seconds, seen = {}, {}, set()
reread = [0]   # tokens that re-read context already sent before (cache reads)
CAP = 60 * 60


def add_file(recs):
    last_t, last_model, waiting_on_helper = None, None, False
    for rec in recs:
        t = ts(rec)
        if rec.get("type") == "assistant":
            msg = rec.get("message") or {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            helper_call = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                              for b in content)
            mid = msg.get("id") or id(rec)
            lab = label(msg.get("model"))
            u = msg.get("usage") or {}
            if mid not in seen and u:
                seen.add(mid)
                tokens[lab] = tokens.get(lab, 0) + sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                reread[0] += int(u.get("cache_read_input_tokens") or 0)
            if t is not None and last_t is not None:
                seconds[lab] = seconds.get(lab, 0) + min(max(t - last_t, 0), CAP)
            last_model, waiting_on_helper = lab, helper_call
        elif t is not None and last_t is not None and last_model and not is_prompt(rec) and not waiting_on_helper:
            seconds[last_model] = seconds.get(last_model, 0) + min(max(t - last_t, 0), CAP)   # tool time
        elif rec.get("type") == "user":
            waiting_on_helper = False   # the helper's own records carry that time
        if t is not None:
            last_t = t


main = [r for r in records if not r.get("isSidechain")]
side = [r for r in records if r.get("isSidechain")]
add_file(main)
helper_found = bool(side)
if side:
    add_file(side)
for pattern in (os.path.splitext(tp)[0] + "/subagents/*.jsonl", os.path.join(os.path.dirname(tp), sid, "subagents", "*.jsonl")):
    for f in sorted(glob.glob(pattern)):
        helper_found = True
        add_file(read_transcript(f))

# hand-overs, from the main transcript
handovers, escalated, results = {}, 0, {}
uses = {}
for rec in main:
    for b in ((rec.get("message") or {}).get("content") or []) if isinstance((rec.get("message") or {}).get("content"), list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
            inp = b.get("input") or {}
            st = str(inp.get("subagent_type") or "helper")
            handovers[st] = handovers.get(st, 0) + 1
            uses[b.get("id")] = st
            if re.search(r"Escalated from sonnet-worker:", str(inp.get("prompt") or ""), re.I):
                escalated += 1
    tur = rec.get("toolUseResult")
    if isinstance(tur, dict) and not helper_found:
        tid = next((b.get("tool_use_id") for b in ((rec.get("message") or {}).get("content") or [])
                    if isinstance(b, dict) and b.get("type") == "tool_result"), None)
        st = uses.get(tid)
        if st:
            lab = {"opus-worker": "Opus", "sonnet-worker": "Sonnet"}.get(st, st)
            tot = tur.get("totalTokens") or sum(int((tur.get("usage") or {}).get(k) or 0) for k in (
                "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            tokens[lab] = tokens.get(lab, 0) + int(tot or 0)
            reread[0] += int((tur.get("usage") or {}).get("cache_read_input_tokens") or 0)
            if tur.get("totalDurationMs"):
                seconds[lab] = seconds.get(lab, 0) + int(tur["totalDurationMs"]) / 1000

total = sum(tokens.values())
try:   # v3.1.24: the prompt hook reads this to ask for the hand-off once the session is long
    tp_ = os.path.join(STATE_DIR, "session-tokens.json")
    try:
        st_ = json.load(open(tp_, encoding="utf-8"))
    except (OSError, ValueError):
        st_ = {}
    st_ = {k: v for k, v in st_.items()} if len(st_) < 50 else {}
    st_[sid] = total
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st_, open(tp_, "w", encoding="utf-8"))
except OSError:
    pass
if not total:
    mark_shown()
    log("stats", {"shown": "version only", "why": "no token counts in the transcript"})
    print(json.dumps({"systemMessage": version_line()}))
    sys.exit(0)


def big(n):
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{round(n / 1e3)} k"


order = sorted(tokens, key=lambda k: -tokens[k])
lines = [version_line(), "Session summary",
         "Tokens: " + " · ".join(f"{k} {round(100 * tokens[k] / total)}%" for k in order) + f" ({big(total)})"
         + (f" — {big(reread[0])} of it re-reading what was already sent" if reread[0] else "")]
if seconds:
    lines.append("Time: " + " · ".join(f"{k} {max(1, round(seconds[k] / 60))} min" for k in order if k in seconds))
names = {"opus-worker": "Opus", "sonnet-worker": "Sonnet"}
ho = " · ".join(f"{names.get(k, k)} {v}" for k, v in sorted(handovers.items())) or "none"
lines.append(f"Hand-overs: {ho}" + (f" · escalated {escalated}" if escalated else ""))
st = read_stats(sid)
lines.append(f"Refused: planner edits {st.get('refused:routing-guard', 0)} · hand-overs {st.get('refused:worker-guard', 0)}"
             f" · plans sent back {st.get('refused:plan-guard', 0)} · Send-backs: {st.get('sendbacks', 0)}")
if total >= int(cfg.get("fresh_session_hint_tokens", 1500000)):
    lines.append("This session is long: at the next stage break the session hands off and gives you a restart line.")
mark_shown()
log("stats", {"shown": "summary", "tokens": total, "reread": reread[0]})
print(json.dumps({"systemMessage": "\n".join(lines)}))
