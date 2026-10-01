#!/usr/bin/env python3
"""Stop hook that never blocks: when a reply is a finished answer (Status Checked or Validated), show the user a
short session summary through Claude Code's systemMessage (no AI turn, no cost):
tokens and time by model (main session and helpers), hand-overs, refusals and send-backs.
Helper (subagent) records are read from the main transcript (sidechain records), from the session's subagents
folder, or — when neither exists — from the totals Claude Code attaches to each finished hand-over."""
import glob, json, os, re, sys
from datetime import datetime
from _common import read_hook_input, load_config, read_transcript, last_assistant_text, read_stats

data = read_hook_input()
cfg = load_config()
tp = data.get("transcript_path") or ""
records = read_transcript(tp)
text = last_assistant_text(records)
m = re.search(cfg["validation_line_pattern"], text or "")
if not m or m.group(2).split()[0] not in ("Checked", "Validated"):
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
sid = data.get("session_id") or ""
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
            if tur.get("totalDurationMs"):
                seconds[lab] = seconds.get(lab, 0) + int(tur["totalDurationMs"]) / 1000

total = sum(tokens.values())
if not total:
    sys.exit(0)


def big(n):
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{round(n / 1e3)} k"


order = sorted(tokens, key=lambda k: -tokens[k])
lines = ["Session summary",
         "Tokens: " + " · ".join(f"{k} {round(100 * tokens[k] / total)}%" for k in order) + f" ({big(total)})"]
if seconds:
    lines.append("Time: " + " · ".join(f"{k} {max(1, round(seconds[k] / 60))} min" for k in order if k in seconds))
names = {"opus-worker": "Opus", "sonnet-worker": "Sonnet"}
ho = " · ".join(f"{names.get(k, k)} {v}" for k, v in sorted(handovers.items())) or "none"
lines.append(f"Hand-overs: {ho}" + (f" · escalated {escalated}" if escalated else ""))
st = read_stats(sid)
lines.append(f"Refused: planner edits {st.get('refused:routing-guard', 0)} · hand-overs {st.get('refused:worker-guard', 0)}"
             f" · plans sent back {st.get('refused:plan-guard', 0)} · Send-backs: {st.get('sendbacks', 0)}")
if total >= int(cfg.get("fresh_session_hint_tokens", 1500000)):
    lines.append("This session is long: start a fresh session for the next stage — it costs less per step.")
print(json.dumps({"systemMessage": "\n".join(lines)}))
