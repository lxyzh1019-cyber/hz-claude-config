#!/usr/bin/env python3
"""PreToolUse hook on the worker tool (Agent/Task). Hard rules for handing work to a helper:
1. (retired in v3.1.30: Claude Code runs workers in the background; the main session waits for the notice)
2. Only opus-worker and sonnet-worker do work (read-only look-around helpers such as Explore may run).
3. Every hand-over starts with "Task: <stage name from the plan>" and "Level: Routine" or "Level: Complex".
4. Routine goes to sonnet-worker; Complex goes to opus-worker. Opus may take a Routine task only when the hand-over
   says "Escalated from sonnet-worker: <reason>".
5. Sonnet never gets a hand-over that mentions complex work (diagnosis, design, data model, shared data, sync, ...).
6. At most two Sonnet tries per task for each request of mine; the third goes to Opus as an escalation.
7. (v3.1.28) A Complex hand-over carries the explorer's map ("Map: ...") or "Map: not needed - <reason>": in the
   Weekly-Planner Sunday v15 session, Opus workers spent 18-120 steps looking around before their first change.
8. (v3.1.28) After a worker reports "Stuck:", the reviewer goes first: no worker hand-over until a reviewer ran."""
import json, os, re
from _common import (read_hook_input, load_config, deny_tool, prompt_number, STATE_DIR, log, read_transcript,
                     pr_branch_state, current_branch)

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
sub = str(inp.get("subagent_type") or "").strip()
text = "\n".join(str(v) for k, v in inp.items() if isinstance(v, str) and k in ("prompt", "description", "task"))

# v3.1.30: the foreground-only refusal is retired. Claude Code (2.1.288) starts every worker in the background
# ("requestShape": "background") whatever the hand-over asks, so the refusal only cost a retry. The main session now
# ends its turn with one "⏳ Working on" line and continues when the worker's notice arrives (wait-guard refuses
# sleep timers).
# v3.1.30: planners in order of preference (the agent files pin the models); a later one only after the earlier one
# failed because its model is not available on this account
_planners = cfg.get("planner_helpers") or ["planner", "planner-opus"]
if sub in _planners[1:] and not re.search(r"^\s*\**Fallback:\**\s*\S", text, re.M | re.I):
    deny_tool(f"Send '{_planners[0]}' first: it plans on the first-choice model. Use '{sub}' only when {_planners[0]} "
              "failed because its model is not available; then start the hand-over with 'Fallback: <the error>'.")
if sub in cfg.get("read_only_helpers", []):
    raise SystemExit(0)
workers = ("opus-worker", "sonnet-worker")
if sub not in workers:
    deny_tool(f"Only opus-worker or sonnet-worker may do work (asked for '{sub or 'a general helper'}'). Hand this to "
              "sonnet-worker if it is Routine, to opus-worker if it is Complex.")

# v3.1.30: a ready pull request must not sit on GitHub while a worker changes its branch — switch it back to draft
# first (GitHub then turns off its merge button); the final report marks it ready again
_branch = current_branch()
_open_ready = pr_branch_state(data.get("session_id")).get(_branch) == "ready" if _branch else False
if _open_ready and not re.search(r"^\s*\**PR:\**\s*#?\d+\s+(merged|closed|back to draft|not touched)\b",
                                                  text, re.M | re.I):
    deny_tool(f"Pull request on branch {_branch} is open and ready for review, so the owner could merge it while this "
              "worker changes its branch. Switch it back to draft first (gh pr ready <number> --undo, or the GitHub "
              "tool's update_pull_request with draft true) and tell the owner '#<number> back to draft — do not "
              "merge'. If it is already merged or closed, add the line 'PR: #<number> merged' (or closed) to the "
              "hand-over. If this worker does not change that pull request's branch, add 'PR: #<number> not touched'.")

task = re.search(r"^\s*\**Task:\**\s*(\S.*)$", text, re.M | re.I)
level = re.search(r"^\s*\**Level:\**\s*(Routine|Complex)\b", text, re.M | re.I)
if not task or not level:
    deny_tool("Start the hand-over with two lines: 'Task: <the stage name from the plan>' and 'Level: Routine' or "
              "'Level: Complex'. Routine = a small, clear change with a known answer (a fix with a repro, wording, "
              "layout, docs, a test for an understood change). Complex = finding an unknown cause, design, anything "
              "touching shared data, settings, sync or the data model. When unsure: Complex.")
lvl = level.group(1).lower()
# v3.1.28: a worker that reported "Stuck:" is followed by the reviewer, not by another try
stuck_since_review = False
uses = {}
for rec in read_transcript(data.get("transcript_path")):
    if rec.get("isSidechain"):
        continue
    content = (rec.get("message") or {}).get("content")
    if not isinstance(content, list):
        continue
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
            st = str((b.get("input") or {}).get("subagent_type") or "")
            uses[b.get("id")] = st
            if st == "reviewer":
                stuck_since_review = False
        elif b.get("type") == "tool_result" and uses.get(b.get("tool_use_id")) in workers:
            res = b.get("content")
            res = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
            if re.search(r'(^|\n|\\n|")\s*\**Stuck:', res):
                stuck_since_review = True
if stuck_since_review:
    deny_tool("A worker reported 'Stuck:'. Send the reviewer first (subagent 'reviewer', moment: Stuck - with the "
              "error, the check and the changed files), then give the next worker its advice as 'Reviewer advice: ...'. "
              "Another try without it repeats the same failing test runs.")
if lvl == "complex" and sub == "opus-worker" and not re.search(r"^\s*\**Map:\**\s*\S", text, re.M | re.I):
    deny_tool("A Complex hand-over carries a map. Send Explore first (it returns which files and lines the change "
              "touches and how they connect), then add its answer as 'Map: ...'. If the worker truly needs no map, add "
              "'Map: not needed - <reason>'. Without a map, workers spent up to 120 steps looking around.")
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
