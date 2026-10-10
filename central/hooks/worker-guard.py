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
# v3.2.10: a dynamic workflow starts its helpers with agent() inside a script, not with the Agent tool, so the checks
# below never see them. Each helper must still get its role file (the rules for workers) in its prompt. One refusal
# with the fix; a second try passes, so a session that cannot comply never loops.
if str(data.get("tool_name") or "") == "Workflow":
    script = str(inp.get("script") or "")
    if "agent(" in script and not re.search(r"Role file:|Worker instructions:", script):
        _flag = os.path.join(STATE_DIR, "workflow-role-refused.json")
        try:
            _seen = json.load(open(_flag, encoding="utf-8"))
        except (OSError, ValueError):
            _seen = []
        key = f"{data.get('session_id')}:{prompt_number(data.get('session_id'))}"
        if key not in _seen:
            os.makedirs(STATE_DIR, exist_ok=True)
            json.dump((_seen + [key])[-50:], open(_flag, "w", encoding="utf-8"))
            log("worker-guard", {"workflow": "no role file"})
            deny_tool("Every agent() prompt in this workflow starts with the worker rules: add the line 'Role file: "
                      "<rules folder>/agents/opus-worker-instructions.md - read it first with the Read tool' (use "
                      "reviewer-instructions.md for a helper that only checks). A helper that edits files names its "
                      "files ('Files: ...'), and no two helpers edit the same file. A helper that makes tests faster "
                      "also gets the line 'Task kind: test speed'. Then start the workflow again.")
    raise SystemExit(0)
sub = str(inp.get("subagent_type") or "").strip()
text = "\n".join(str(v) for k, v in inp.items() if isinstance(v, str) and k in ("prompt", "description", "task"))

# v3.1.30: the foreground-only refusal is retired. Claude Code (2.1.288) starts every worker in the background
# ("requestShape": "background") whatever the hand-over asks, so the refusal only cost a retry. The main session now
# ends its turn with one "⏳ Working on" line and continues when the worker's notice arrives (wait-guard refuses
# sleep timers).
# v3.1.30: planners in order of preference (the agent files pin the models); a later one only after the earlier one
# failed because its model is not available on this account
_planners = cfg.get("planner_helpers") or ["planner", "planner-opus"]
if sub in _planners:
    try:
        from _common import live_proof
        live_proof("planner", {"helper": sub, "fallback": bool(re.search(r"^\s*\**Fallback:", text, re.M | re.I))})
    except ImportError:
        pass
if sub in _planners[1:] and not re.search(r"^\s*\**Fallback:\**\s*\S", text, re.M | re.I):
    deny_tool(f"Send '{_planners[0]}' first: it plans on the first-choice model. Use '{sub}' only when {_planners[0]} "
              "failed because its model is not available; then start the hand-over with 'Fallback: <the error>'.")
if sub in cfg.get("read_only_helpers", []):
    raise SystemExit(0)
workers = ("opus-worker", "sonnet-worker")
if sub not in workers:
    deny_tool(f"Only opus-worker or sonnet-worker may do work (asked for '{sub or 'a general helper'}'). Hand this to "
              "sonnet-worker if it is Routine, to opus-worker if it is Complex.")

# v3.2.9: no switching a pull request back to draft (owner, 9 Oct: the draft/ready flip-flop is what we avoid). A
# pull request opens last, after green tests; while it is open, merge-guard keeps me from being asked to merge on red.

# v3.2.0: up to 3 workers at once. A worker that starts while another runs gets its own worktree (a second working
# folder on its own branch), so they never edit the same files; the plan's parallel group is named.
from _common import open_workers
_open = open_workers(read_transcript(data.get("transcript_path")), workers, data.get("transcript_path"),
                     exclude_id=data.get("tool_use_id"))
# v3.2.11: no fixed cap. The limits are files (each lane has its own files and worktree), the usage limit and the
# owner's stops; above 5 lanes the session is told the usage cost once. 9 Oct: 3 lanes ran at once without trouble.
_max = int(cfg.get("max_parallel_workers", 0))
if _max and len(_open) >= _max:
    deny_tool(f"{len(_open)} workers already run; the limit is {_max}. Wait for one to report, then start this one.")
_lane_notice = None
if len(_open) + 1 > int(cfg.get("parallel_notice_above", 5)):
    _lane_notice = (f"[lanes] {len(_open) + 1} workers now run at once. Each one uses the usage limit at the same time; "
                    "start more only when the stages have their own files and end in one joined stop.")
if _open and not (re.search(r"^\s*\**Worktree:\**\s*\S", text, re.M | re.I)
                  and re.search(r"^\s*\**Files:\**\s*\S", text, re.M | re.I)):
    deny_tool("Another worker is running. A parallel worker works in its own worktree and names its files, so no two "
              "workers edit the same file. Make one with 'git worktree add ../<repo>-<lane> -b claude/<lane>' and add "
              "the lines 'Worktree: <folder>', 'Files: <the files it changes>' and 'Group: <lane from the plan>'.")
if _open:
    try:
        from _common import live_proof
        live_proof("parallel-workers", {"running": len(_open) + 1})
    except ImportError:
        pass

task = re.search(r"^\s*\**Task:\**\s*(\S.*)$", text, re.M | re.I)
level = re.search(r"^\s*\**Level:\**\s*(Routine|Complex)\b", text, re.M | re.I)
if not task or not level:
    deny_tool("Start the hand-over with two lines: 'Task: <the stage name from the plan>' and 'Level: Routine' or "
              "'Level: Complex'. Ask: must the worker find or decide something? No = Routine: the answer is known, even "
              "across many files (a fix with a repro, wording, layout, an exact table of values, a rename, moving code "
              "to one helper with a check, test data from a measured list). Yes = Complex: an unknown cause, a design "
              "choice, shared data, settings, sync, security rules or the data model.")
lvl = level.group(1).lower()
# v3.2.0: the stage's size from the plan (S, M, L), so the actual time can be compared with the estimate
if not re.search(r"^\s*\**Size:\**\s*[SML]\b", text, re.M | re.I) and not os.environ.get("HZ_STAGE_TAGS_OFF"):
    deny_tool("Add the line 'Size: S', 'Size: M' or 'Size: L' to the hand-over: the stage's size from the plan "
              "(S about 15 min, M about 45, L about 90). It lets the session see when a stage runs over.")
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
            if st in ("reviewer", "reviewer-light"):
                stuck_since_review = False
        elif b.get("type") == "tool_result" and uses.get(b.get("tool_use_id")) in workers:
            res = b.get("content")
            res = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
            if re.search(r'(^|\n|\\n|")\s*\**Stuck:', res):
                stuck_since_review = True
from _common import small_job as _sj7, agent_on_pc as _aop7
if stuck_since_review and not _sj7(cfg) and _aop7("reviewer"):   # v3.2.7: a small job lets the main session decide
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
    from _common import complex_hits   # v3.2.5: whole lower-case words outside file names (ARCHITECTURE.md, Sister Sync)
    hits = complex_hits(text, cfg.get("complex_words", []))
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
if _lane_notice:
    from _common import add_context as _ac
    _ac("PreToolUse", _lane_notice)
