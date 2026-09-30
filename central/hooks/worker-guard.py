#!/usr/bin/env python3
"""PreToolUse hook on the worker tool (Agent/Task). Hard rules for handing work to a helper:
1. Foreground only: the main session waits silently and sends one report at the end.
2. Only opus-worker and sonnet-worker do work (read-only look-around helpers such as Explore may run).
3. Every hand-over starts with "Task: <stage name from the plan>" and "Level: Routine" or "Level: Complex".
4. Routine goes to sonnet-worker; Complex goes to opus-worker. Opus may take a Routine task only when the hand-over
   says "Escalated from sonnet-worker: <reason>".
5. Sonnet never gets a hand-over that mentions complex work (diagnosis, design, data model, shared data, sync, ...).
6. At most two Sonnet tries per task for each request of mine; the third goes to Opus as an escalation."""
import json, os, re
from _common import read_hook_input, load_config, deny_tool, prompt_number, STATE_DIR, log

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
sub = str(inp.get("subagent_type") or "").strip()
text = "\n".join(str(v) for k, v in inp.items() if isinstance(v, str) and k in ("prompt", "description", "task"))

if any("background" in k.lower() and v for k, v in inp.items()):
    deny_tool("Workers run in the foreground: start this worker again without running it in the background, and wait "
              "for it silently. To run several at once, start them together in one step.")
if sub in cfg.get("read_only_helpers", []):
    raise SystemExit(0)
workers = ("opus-worker", "sonnet-worker")
if sub not in workers:
    deny_tool(f"Only opus-worker or sonnet-worker may do work (asked for '{sub or 'a general helper'}'). Hand this to "
              "sonnet-worker if it is Routine, to opus-worker if it is Complex.")

task = re.search(r"^\s*\**Task:\**\s*(\S.*)$", text, re.M | re.I)
level = re.search(r"^\s*\**Level:\**\s*(Routine|Complex)\b", text, re.M | re.I)
if not task or not level:
    deny_tool("Start the hand-over with two lines: 'Task: <the stage name from the plan>' and 'Level: Routine' or "
              "'Level: Complex'. Routine = a small, clear change with a known answer (a fix with a repro, wording, "
              "layout, docs, a test for an understood change). Complex = finding an unknown cause, design, anything "
              "touching shared data, settings, sync or the data model. When unsure: Complex.")
lvl = level.group(1).lower()
escalated = re.search(r"Escalated from sonnet-worker:\s*\S", text, re.I)
if lvl == "routine" and sub == "opus-worker" and not escalated:
    deny_tool("Level: Routine goes to sonnet-worker. Opus takes a Routine task only after Sonnet has escalated it: then "
              "start the hand-over with 'Escalated from sonnet-worker: <reason>'.")
if lvl == "complex" and sub == "sonnet-worker":
    deny_tool("Level: Complex goes to opus-worker, never to sonnet-worker.")
if sub == "sonnet-worker":
    low = text.lower()
    hits = [w for w in cfg.get("complex_words", []) if w in low]
    if hits:
        deny_tool("This hand-over mentions complex work (" + ", ".join(hits[:4]) + "), so it is Level: Complex and goes "
                  "to opus-worker.")
    n = prompt_number(data.get("session_id")) or 0
    key = f"{data.get('session_id') or ''}:{n}:{task.group(1).strip().lower()[:80]}"
    path = os.path.join(STATE_DIR, "sonnet-tries.json")
    try:
        tries = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        tries = {}
    used = int(tries.get(key, 0))
    if used >= int(cfg.get("sonnet_max_tries", 2)):
        deny_tool(f"sonnet-worker has had {used} tries at '{task.group(1).strip()}' for this request. Hand it to "
                  "opus-worker, starting with 'Escalated from sonnet-worker: two tries did not finish it'.")
    tries[key] = used + 1
    if len(tries) > 200:
        tries = {key: used + 1}
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tries, f)
    except OSError:
        pass
log("worker-guard", {"worker": sub, "level": lvl, "escalated": bool(escalated)})
