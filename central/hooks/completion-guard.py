#!/usr/bin/env python3
"""Stop hook: a final report may not claim done while the deliverable ledger has open items.
- On an implementation turn (source edits or a dispatched worker), a final report carries the ledger's
  Completion lines just before the validation line; a wrong count is corrected.
- Only ledger rows added or changed on this branch against origin/main count: rows from earlier rounds never block.
  When origin/main cannot be read, the Completion line is still shown but open items never block.
- If items are still open (neither COMPLETE nor BLOCKED), the report is blocked and the session continues with the
  next open item — at most auto_fix_max_rounds send-backs per user prompt, for every reason together (the loop guard, keyed on the prompt number written by
  the UserPromptSubmit hook, so this hook's own feedback cannot reset it; stop_hook_active alone is NOT a reason to
  exit here, unlike the other Stop hooks). After the cap, the report must say so and list the open items.
- A user prompt with a pause phrase (plan-gate writes .claude/state/completion-pause) lets one final report stand.
- Progress reports (workers still running), plans awaiting approval, and answers on non-implementation turns pass."""
import json, os, re, sys
from _common import (PROJECT_DIR, STATE_DIR, read_hook_input, load_config, read_transcript, last_turn,
                     last_assistant_text, tool_uses, is_governance_path, is_progress_report, completion_summary,
                     prompt_number, block, log, handoff_text)

data = read_hook_input()
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
turn = last_turn(records)
text = last_assistant_text(turn)
comp = completion_summary(cfg)
if not text or not comp["total"]:
    sys.exit(0)
if is_progress_report(text, records, cfg):
    sys.exit(0)
m = re.search(cfg["validation_line_pattern"], text)
final_claim = bool(m) and m.group(2).split()[0] in ("Checked", "Validated")
if not final_claim:
    sys.exit(0)  # a plan (Proposed), an Uncertain answer, or no validation line (validation-line.py handles that)

pause = os.path.join(STATE_DIR, "completion-pause")
if os.path.exists(pause):
    try:
        os.remove(pause)
    except OSError:
        pass
    log("completion-guard", {"pause": True, "line": comp["line"]})
    sys.exit(0)

# loop guard: rounds per user prompt. The prompt number is written by the UserPromptSubmit hook, so the
# feedback this hook sends back — another user record in the transcript — cannot reset the count.
rounds_path = os.path.join(STATE_DIR, "completion-rounds.json")
n = prompt_number(data.get("session_id"))
key = f"{data.get('session_id') or ''}:{n}" if n else str(
    (turn[0].get("uuid") or turn[0].get("timestamp") or len(records)) if turn else len(records))
try:
    rounds = json.load(open(rounds_path, encoding="utf-8"))
except (OSError, ValueError):
    rounds = {}
used = int(rounds.get(key, 0))


def bump():
    rounds.clear() if len(rounds) > 50 else None
    rounds[key] = used + 1
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(rounds, open(rounds_path, "w", encoding="utf-8"))
    except OSError:
        pass


edits = tool_uses(turn, {"Edit", "Write", "MultiEdit", "NotebookEdit"})
paths = [(e.get("input") or {}).get("file_path") or (e.get("input") or {}).get("path") or "" for e in edits]
root = os.path.normcase(os.path.abspath(PROJECT_DIR))
def inside(p):
    full = os.path.normcase(os.path.abspath(os.path.join(PROJECT_DIR, p)))
    return full == root or full.startswith(root + os.sep)
implementation = (any(p and inside(p) and not is_governance_path(p, cfg) for p in paths)
                  or bool(tool_uses(turn, {"Agent", "Task"})) or used > 0)
stated = re.search(cfg["completion_line_pattern"], text)
if not implementation and not stated:
    sys.exit(0)  # a question answered mid-project: no completion claim made, nothing to check

cap = int(cfg["auto_fix_max_rounds"])
if used >= cap:
    sys.exit(0)  # this prompt's send-back is spent: never loop, whatever the reason
open_items = comp["open"] if comp["scoped"] else []
wrong_count = stated and (int(stated.group(1)) != comp["complete"] or int(stated.group(2)) != comp["total"])

reasons = []
if open_items:
    reasons.append(f"Not done: this branch's work still has {len(open_items)} open item(s): " + "; ".join(open_items[:6]) +
                   f". Continue with '{open_items[0]}' now — dispatch it to the right worker or execute it as the approved "
                   "plan allows, and update its ledger row with evidence. An item you cannot finish in this round gets "
                   "state BLOCKED — <reason> in the ledger, or you write 'Auto-fix limit reached' and list it with why. "
                   "This is the only send-back for this request.")
elif not stated:
    reasons.append("Implementation happened this turn: add the completion lines before the validation line.")
# v3.1.26: a wrong count alone is not worth a whole extra turn — the notice shows me the line from the record
if comp.get("build_done") and comp.get("check_open") and comp.get("plan"):
    # v3.1.24: the hand-off is due in the report where Build reaches 100% — once per plan: the restart line then
    # stands in '## Where we are' (pushed), which every later session reads
    try:
        record = open(os.path.join(PROJECT_DIR, cfg["record_file"]), encoding="utf-8", errors="replace").read()
    except OSError:
        record = ""
    if not re.search(r"Continue\s+" + re.escape(comp["plan"]), text + "\n" + record):
        reasons.append("Build is at 100% and only checks are left: " + handoff_text(cfg, comp, after_build=True))
    # v3.1.28: before done, the reviewer checks the changes against the plan (fresh, small memory)
    if not re.search(r"Reviewer before done\s*\(\s*" + re.escape(comp["plan"]), text + "\n" + record, re.I):
        reasons.append("Before done: send the reviewer (subagent 'reviewer', moment: Before done) with the plan file and "
                       "the list of changed files; fix the blocking problems it finds (each fix is a new Build row); "
                       "then write 'Reviewer before done (" + comp["plan"] + "): <verdict>' in '## Where we are' and push "
                       "it with the hand-off.")
if comp.get("untagged_checks"):   # v3.1.24: the label keeps a check a check after it is ticked COMPLETE
    reasons.append("Add ' (Check)' to the end of these row names in the ledger, so they still count as Check once "
                   "they are COMPLETE: " + "; ".join(comp["untagged_checks"][:6]) + ".")
if comp["no_evidence"]:
    reasons.append("COMPLETE without evidence in the deliverable ledger: " + ", ".join(comp["no_evidence"]) +
                   ". Fill the Evidence cell (what ran and its result) or set the state back to PARTIAL.")
if not reasons and wrong_count:
    print(json.dumps({"systemMessage": "Completion (from the record): " + comp["line"]}))
    sys.exit(0)
if reasons:
    if wrong_count:
        reasons.append("The stated Completion line does not match the ledger; use the lines below.")
    bump()
    log("completion-guard", {"send_back": used + 1, "open": open_items})
    work = bool(open_items) or any(r.startswith("Before done: send the reviewer") for r in reasons)
    block(" ".join(reasons) + "\nPut these lines just before the validation line (the three closing lines stay last):\n"
          + comp["display"], kind="work" if work else None)
sys.exit(0)
