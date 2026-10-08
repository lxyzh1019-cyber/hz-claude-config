#!/usr/bin/env python3
"""UserPromptSubmit hook: plan tier, fix-counter reminder, hotspot redesign alerts, and the prompt counter
(the number the completion guard keys its auto-fix rounds on, so its own feedback cannot reset them)."""
import json, sys
import os, re
from _common import (read_hook_input, load_config, count_bullets, log, hotspot_alerts, FIX_WORDS,
                     completion_summary, bump_prompt_number, handoff_text, STATE_DIR, prompt_number,
                     take_fixes)

data = read_hook_input()
prompt = data.get("prompt") or ""
cfg = load_config()
bump_prompt_number(data.get("session_id"))
# v3.1.31: format, wording and record problems from the last answer were saved, not sent back — fix them now
_fixes = take_fixes(data.get("session_id"))
if _fixes:
    try:
        from _common import live_proof
        live_proof("saved-fixes", {"handed_on": len(_fixes)})
    except ImportError:
        pass
FIX_TEXT = ("[fix first] Your last answer had these problems. Fix any file or record item now. Do not write about "
            "the fixes. Follow the formats in your next answer:\n" +
            "\n".join(f"- {f}" for f in _fixes)) if _fixes else ""
# v3.2.0: memory budget for the main session — one notice each time it passes another 100 k above the budget
def memory_notice():
    try:
        from _common import read_transcript as _rt
        _ctx = 0
        for _r in reversed(_rt(data.get("transcript_path"))):
            _u = (_r.get("message") or {}).get("usage") if _r.get("type") == "assistant" and not _r.get("isSidechain") \
                else None
            if _u:
                _ctx = sum(int(_u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens",
                                                         "cache_creation_input_tokens"))
                break
        _budget = int(cfg.get("main_memory_max", 200000))
        if _ctx < _budget:
            return ""
        _lvl = (_ctx - _budget) // 100000
        _sp = os.path.join(STATE_DIR, "memory-notice.json")
        try:
            _seen = json.load(open(_sp, encoding="utf-8"))
        except (OSError, ValueError):
            _seen = {}
        if _seen.get(str(data.get("session_id") or "")) == _lvl:
            return ""
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump({str(data.get("session_id") or ""): _lvl}, open(_sp, "w", encoding="utf-8"))
        return (f"[memory] Each step now re-reads about {round(_ctx / 1000)} k tokens (budget {round(_budget / 1000)} k). "
                "At the next stage break, put 'Type /compact' in the 'I need from you' line. Send long work to fresh "
                "workers.")
    except Exception:
        return ""


MEM_TEXT = memory_notice()


# v3.2.0: measured stop signals. A worker stopped by a limit, a stage over twice its size, or a worker that reports
# "Stuck:" means the plan no longer fits: the main session shows the next Rev with the problem and its solution.
def stop_notice():
    reasons = []
    sp = os.path.join(STATE_DIR, "stop-signals.json")
    try:
        sig = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        sig = []
    for s in sig:
        if not s.get("told"):
            reasons.append(s.get("reason") or "a worker stopped")
            s["told"] = True
    if re.search(r"(?m)(^|>)\s*\**Stuck:", str(data.get("prompt") or "")):
        reasons.append("a worker reported 'Stuck:'")
    if not reasons:
        return ""
    try:
        json.dump(sig, open(sp, "w", encoding="utf-8"))
    except OSError:
        pass
    try:
        from _common import live_proof
        live_proof("stop-for-plan", {"reasons": reasons})
    except ImportError:
        pass
    return ("[stop for plan] " + "; ".join(reasons) + ". Before more build work, show the next Rev of the plan in "
            "plan mode: the problem, its cause, and your recommended solution. A small fix that changes no approved "
            "result may go on; say why in one line.")


# v3.2.1: background full test runs, measured when their notice arrives (the real case: 30 min, stopped, exit 124)
try:
    from _common import background_test_note as _btn, read_transcript as _rt2
    TEST_TEXT = _btn(cfg, _rt2(data.get("transcript_path")))
except Exception as _e:
    TEST_TEXT = ""
    log("plan-gate", {"test_speed_error": str(_e)[:200]})   # never blocks a prompt
STOP_TEXT = stop_notice()
# v3.1.30: a worker or background-command notice is not a request of mine. In the Weekly-Planner money session 79 of
# 106 plan-gate texts went to such notices ("Full Plan vN is required (90 bullets)"), 128,000 characters re-read on
# every later step.
# v3.2.2: report timing — at each finish notice, say whether anything still runs (one full report at the end)
TIMING_TEXT = ""
if prompt.lstrip().startswith("<task-notification>") and not os.environ.get("HZ_REPORT_TIMING_OFF"):
    try:
        from _common import still_running as _sr, read_transcript as _rt3, WAIT_TEXT as _WT, REPORT_TEXT as _RT
        import formats as _F
        # the notice itself may not be in the session file yet when this check runs: count it as read
        _recs = _rt3(data.get("transcript_path")) + [{"type": "user", "message": {"role": "user", "content": prompt}}]
        _left = _sr(_recs, data.get("transcript_path"))
        TIMING_TEXT = (_WT.format(what=", ".join(_left[:3]) + (f" and {len(_left) - 3} more" if len(_left) > 3 else ""),
                                  line=_F.WORKING_LINE) if _left else _RT)
    except Exception as _e:
        log("plan-gate", {"timing_error": str(_e)[:200]})
if prompt.lstrip().startswith("<task-notification>"):
    log("plan-gate", {"skipped": "task notification", "fixes": len(_fixes)})
    _ctx_txt = "\n".join(x for x in (FIX_TEXT, TEST_TEXT, STOP_TEXT, MEM_TEXT, TIMING_TEXT) if x)
    if _ctx_txt:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": _ctx_txt}}))
    sys.exit(0)
bullets = count_bullets(prompt)
low = prompt.lower()
triggers = [t for t in cfg["design_triggers"] if t in low]
msgs = []
SKIP_PHRASES = ("skip the plan", "skip plan", "no plan", "without a plan", "don't plan", "do not plan",
                "run it directly", "run directly", "execute directly", "do it directly")
skip = any(p in low for p in SKIP_PHRASES)

if skip:
    log("plan-gate", {"tier": "skipped by user"})
    msgs.append("[plan-gate] The user explicitly asked to skip the plan: carry out the request directly. "
                "Hotspot blocks, git-guard and the Stop-hook checks still apply.")
elif bullets >= 3 or triggers:
    why = f"{bullets} bullets" if bullets >= 3 else "design/diagnostic trigger: " + ", ".join(triggers)
    log("plan-gate", {"tier": "full", "why": why})
    msgs.append(f"[plan-gate] Full 'Plan vN — Title — Awaiting approval' is required for this request ({why}). "
                "Do not edit files before approval. If this is a follow-up on an already approved plan, show the next "
                "version in plan mode; the plan check adds the coloured marks by itself. "
                + ("Executor: opus-worker (Diagnostic/Redesign trigger)." if triggers else
                   "Name the helper and level for every Claude stage: sonnet-worker for Level: Routine, opus-worker "
                   "for Level: Complex (shared data, settings, sync, data model, diagnosis, design)."))
elif bullets >= 1 or len(prompt) > 200:
    log("plan-gate", {"tier": "micro", "bullets": bullets})
    msgs.append("[plan-gate] Micro-plan tier: target, files touched, one-line approach, one success check, "
                "'Checked against:' and 'Removes/consolidates:' lines — then wait for approval. Escalate to a full "
                "Plan vN if the work touches shared state, config, or the data model. Executor: sonnet-worker.")

if (msgs and not skip) or any(w in low for w in FIX_WORDS):
    msgs.append("[plan-gate] Before proposing: read the request ledger and hotspot rows in "
                f"{cfg['record_file']} for the area this touches; state them under 'Checked against:'.")
if any(w in low for w in FIX_WORDS):
    msgs.append("[plan-gate] This looks like a fix. In the same turn, update the area's hotspot row: +1 fix round; "
                "+1 recurrence if the same symptom came back; +1 regression if an earlier fix caused this; "
                "+1 workaround for each exception or compensating patch added.")

alerts = hotspot_alerts(cfg)
if alerts:
    log("plan-gate", {"hotspot_alerts": alerts})
    msgs += ["[hotspot] " + a for a in alerts]

# planner suggestion: only when a plan is required. The hook cannot switch models; the user runs /model fable.
if msgs and not skip and (bullets >= 3 or triggers):
    signals = [s for s in cfg["fable_planner_signals"] if s in low]
    strong = [a for a in alerts if "redesign threshold" in a]
    why = []
    if strong:
        why.append("an area is at the rewrite-vs-repair threshold")
    if len(triggers) >= cfg["fable_planner_min_triggers"]:
        why.append(f"{len(triggers)} design/diagnostic triggers in one request")
    if signals:
        why.append("investigation wording: " + ", ".join(signals[:3]))
    if why:
        log("plan-gate", {"planner": "fable suggested", "why": why})
        try:   # v3.1.28: the plan check asks for the reviewer before this plan goes out
            os.makedirs(STATE_DIR, exist_ok=True)
            json.dump({"session": str(data.get("session_id") or ""), "n": prompt_number(data.get("session_id")),
                       "why": "; ".join(why)}, open(os.path.join(STATE_DIR, "plan-review.json"), "w", encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            pass
        msgs.append("[reviewer] Big or risky plan: before presenting it, send the reviewer (moment: Before a plan) "
                    "with the draft plan and the area's ledger and hotspot rows, and fix what it finds.")
        msgs.append("[planner] Big or risky plan (" + "; ".join(why) + "): the planner helper writes it.")
    # v3.2.0: the planner helper writes a new plan and big changes; later Revs and versions come from the main session
    msgs.append("[planner] A new plan is written by the 'planner' helper (planner file, plan shape, agreed points). "
                "Save what it returns in one step and show it. Later Revs and versions, and micro-plans, are yours. "
                "Tag each stage: files, after, level, tests, group (stages in the same group run in parallel).")

# pause: the next final report may stand with open ledger items (completion-guard honours this once)
if any(ph in low for ph in cfg["pause_phrases"]):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        open(os.path.join(STATE_DIR, "completion-pause"), "w").close()
        msgs.append("[completion] Pause acknowledged: this reply may end with open ledger items; state the Completion line honestly.")
    except OSError:
        pass

comp = completion_summary(cfg)
sid = data.get("session_id") or ""

# v3.1.24: resuming from a restart line — switch to its branch and read the record before anything else
resume = re.search(r"\bcontinue\s+(.+?)\s+on branch\s+([\w./-]+)", prompt, re.I)
if resume:
    br = resume.group(2).rstrip(".;,`")
    msgs.append(f"[resume] This session continues earlier work. First switch to branch {br} (fetch it from origin if it "
                f"is only on GitHub), read '## Where we are' in {cfg['record_file']} and the newest plan file in plans/, "
                "then tell me the plan name, its newest Plan vN, the Completion lines and the next stage. Wait for my OK "
                "before changing anything.")

# v3.1.24: hand-off after a merge, or once a session is long — done by the session itself, in one reply
handoff_why = ""
if re.search(r"\bmerged\b", low) and not comp["total"]:
    msgs.append("[hand-off] I merged. After confirming it, update '## Where we are' in the working record and commit "
                "and push it; if more work follows, carry on in this session (v3.1.28: never suggest a new one).")
elif re.search(r"\bmerged\b", low):
    handoff_why = "I merged a stage. After confirming the merge, "
else:
    try:
        used = int((json.load(open(os.path.join(STATE_DIR, "session-tokens.json"), encoding="utf-8")) or {}).get(sid, 0))
    except (OSError, ValueError, TypeError):
        used = 0
    warned = os.path.join(STATE_DIR, "long-session-warned.txt")
    try:
        already = sid and sid in open(warned, encoding="utf-8").read().split()
    except OSError:
        already = False
    if sid and used >= int(cfg.get("fresh_session_hint_tokens", 1500000)) and comp["total"] and not already:
        handoff_why = (f"This session is long ({round(used / 1e6, 1)} M tokens): every step re-reads all of it. Keep "
                       "going without stopping, but keep this main session lean from now on: hand each remaining stage "
                       "to a fresh worker, read only its short report, and do not read screenshots or large files here. "
                       "At the next stage break, ")
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(warned, "a", encoding="utf-8") as f:
                f.write(sid + "\n")
        except OSError:
            pass
# v3.2.1: only when one Build stage is left, and said as a future step (3.2.0 sent it every prompt, with a lessons line
# that said "the build of this plan is done" — the session rightly called it untrue)
if (not handoff_why and not resume and comp.get("check_total") and comp["total"] and not comp.get("build_done")
        and comp["total"] - comp["complete"] <= 1):
    msgs.append("[hand-off] Build is not finished yet. Only when the last Build stage finishes, in that same reply, "
                + handoff_text(cfg, comp, after_build=True))
if handoff_why and not resume:
    log("plan-gate", {"handoff": handoff_why[:40]})
    msgs.append("[hand-off] " + handoff_why + handoff_text(cfg, comp))

if comp["total"] and comp["open"]:
    msgs.append("[completion] " + comp["display"] + "\n— this plan's ledger rows; the final report carries "
                "these lines (just before the validation line) and may claim done only when nothing is open." +
                ("" if comp["scoped"] else " The base branch could not be read, so nothing is blocked on this count."))

# v3.2.0: night work in two steps. "night check": every open question plus the overnight plan, while I can still answer.
# "good night": start, with my answers. After 9 PM Edmonton time, one reminder per evening to type "night check".
NIGHT_CHECK = cfg.get("night_check_phrases") or ["night check", "before bed", "before i sleep", "睡前"]
NIGHT = cfg.get("night_phrases") or ["good night", "goodnight", "going to sleep", "going to bed", "晚安", "睡觉了", "去睡了"]
try:
    from _common import live_proof as _lp
except ImportError:
    _lp = lambda *a, **k: None
if any(ph in low for ph in NIGHT_CHECK):
    log("plan-gate", {"night": "check"})
    _lp("night-work", {"step": "night check"})
    msgs.append("[night check] I sleep soon. In this reply, list every open question at once, numbered, each with your "
                "recommendation. Then list what you will do overnight: the stages in order, and which pull requests "
                "you will stack on which branch. Start nothing yet; wait for my answers and my 'good night'.")
elif any(ph in low for ph in NIGHT):
    log("plan-gate", {"night": True})
    _lp("night-work", {"step": "good night"})
    msgs.append("[night] I am away now. Use my answers. Keep working on every approved stage that needs no other answer "
                "from me. Stack pull requests as usual: branch from the earlier unmerged branch, with that branch as "
                "the base, at most 3 unmerged. I merge them in order in the morning. "
                "Never merge. When a new question comes up, take your own recommendation if it changes no app behaviour and "
                "no stored data and can be undone: build it on its branch and note 'built on my recommendation — "
                "undone if you say no'. Show no plan at night; in the morning, show the next Rev with these decisions "
                "marked, and the pull requests in merge order. Only an app change, a data change or a destructive "
                "step waits for me.")
else:
    try:
        from _common import edmonton_hour
        from datetime import datetime as _d
        _ev = _d.now().strftime("%Y-%m-%d")
        _np = os.path.join(STATE_DIR, "evening-reminder.json")
        try:
            _done = json.load(open(_np, encoding="utf-8")).get("day")
        except (OSError, ValueError):
            _done = None
        if edmonton_hour() >= int(cfg.get("evening_hour", 21)) and _done != _ev and comp.get("open"):
            os.makedirs(STATE_DIR, exist_ok=True)
            json.dump({"day": _ev}, open(_np, "w", encoding="utf-8"))
            msgs.append("[evening] It is evening in Edmonton and work is still open. In your next final answer, add one "
                        "sentence to the 'I need from you' line: \"Before you sleep, type 'night check'.\"")
    except Exception:
        pass
if STOP_TEXT:
    msgs.insert(0, STOP_TEXT)
if TEST_TEXT:
    msgs.insert(0, TEST_TEXT)
if MEM_TEXT:
    msgs.append(MEM_TEXT)
if FIX_TEXT:
    msgs.insert(0, FIX_TEXT)
if msgs:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": "\n".join(msgs)}}))
sys.exit(0)
