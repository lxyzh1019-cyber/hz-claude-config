#!/usr/bin/env python3
"""UserPromptSubmit hook: plan tier, fix-counter reminder, and hotspot redesign alerts."""
import json, sys
from _common import read_hook_input, load_config, count_bullets, log, hotspot_alerts, FIX_WORDS

data = read_hook_input()
prompt = data.get("prompt") or ""
cfg = load_config()
bullets = count_bullets(prompt)
low = prompt.lower()
triggers = [t for t in cfg["design_triggers"] if t in low]
msgs = []

if bullets >= 3 or triggers:
    why = f"{bullets} bullets" if bullets >= 3 else "design/diagnostic trigger: " + ", ".join(triggers)
    log("plan-gate", {"tier": "full", "why": why})
    msgs.append(f"[plan-gate] Full 'Plan vN — Title — Awaiting approval' is required for this request ({why}). "
                "Do not edit files before approval. If this is a follow-up on an already approved plan, present the "
                "revision with Rev-N colour-square markers (🟦🟩🟧🟪, no HTML) instead of a new plan.")
elif bullets >= 1 or len(prompt) > 200:
    log("plan-gate", {"tier": "micro", "bullets": bullets})
    msgs.append("[plan-gate] Micro-plan tier: target, files touched, one-line approach, one success check, "
                "'Checked against:' and 'Removes/consolidates:' lines — then wait for approval. Escalate to a full "
                "Plan vN if the work touches shared state, config, or the data model.")

if msgs or any(w in low for w in FIX_WORDS):
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

if msgs:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": "\n".join(msgs)}}))
sys.exit(0)
