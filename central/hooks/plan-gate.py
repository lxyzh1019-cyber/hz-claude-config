#!/usr/bin/env python3
"""UserPromptSubmit hook: plan tier, fix-counter reminder, hotspot redesign alerts, and the prompt counter
(the number the completion guard keys its auto-fix rounds on, so its own feedback cannot reset them)."""
import json, sys
import os, re
from _common import (read_hook_input, load_config, count_bullets, log, hotspot_alerts, FIX_WORDS,
                     completion_summary, bump_prompt_number, handoff_text, STATE_DIR, prompt_number)

data = read_hook_input()
prompt = data.get("prompt") or ""
cfg = load_config()
bump_prompt_number(data.get("session_id"))
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
                "Do not edit files before approval. If this is a follow-up on an already approved plan, present the "
                "revision with Rev-N colour-square markers (🟦🟩🟧🟪, no HTML) instead of a new plan. "
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
        msgs.append("[planner] Suggest /model fable before writing this plan (session-only; the next session is back on "
                    "the account default): " + "; ".join(why) + ". Otherwise plan on the session's own model. State which one applied at the top of the plan.")
    else:
        msgs.append("[planner] The session's model plans (account default: Opus 5.5).")

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
if (not handoff_why and not resume and comp.get("check_total") and comp["total"] and not comp.get("build_done")):
    # v3.1.24: Build and Check are counted apart; the hand-off happens in the report where Build reaches 100%
    msgs.append("[hand-off] When the last Build stage is finished, " + handoff_text(cfg, comp, after_build=True))
if handoff_why and not resume:
    log("plan-gate", {"handoff": handoff_why[:40]})
    msgs.append("[hand-off] " + handoff_why + handoff_text(cfg, comp))

if comp["total"] and comp["open"]:
    msgs.append("[completion] " + comp["display"] + "\n— this plan's ledger rows; the final report carries "
                "these lines (just before the validation line) and may claim done only when nothing is open." +
                ("" if comp["scoped"] else " The base branch could not be read, so nothing is blocked on this count."))

if msgs:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": "\n".join(msgs)}}))
sys.exit(0)
