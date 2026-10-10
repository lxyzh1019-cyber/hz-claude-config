#!/usr/bin/env python3
"""Stop hook (v3.1.24): the plan file holds every revision, and a hand-off to a fresh session really works.
- A reply that names "Plan vN" above the newest plan file in plans/ is sent back: a plan change agreed in chat is
  presented in plan mode as the next Plan vN, so the plan file always carries the latest version.
- The ledger's plan name carries no version number: when it says "Plan vK" below the newest plan file, the rows
  are renamed (plan name only), so the restart line and the plan file never disagree.
- A reply with a restart line ("Continue <plan> on branch <branch>; next: …") is checked: the plan name matches
  the ledger, the branch is this one, WORKING_RECORD.md is committed and pushed, and every row that is not
  complete is listed.
At most auto_fix_max_rounds send-backs per user prompt; stop_hook_active only when the prompt number is unknown."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, completion_summary,
                     newest_plan_version, current_branch, restart_line, run_text, use_round, block, log, PLAN_NUMBER)

data = read_hook_input()
cfg = load_config()
text = last_assistant_text(read_transcript(data.get("transcript_path"))) or ""
if not text:
    sys.exit(0)
problems = []

newest = newest_plan_version()
named = [int(n) for n in PLAN_NUMBER.findall(text)]
comp = None
if newest:
    if named and max(named) > newest:
        problems.append(f"This reply names Plan v{max(named)}, but the newest plan file in plans/ is Plan v{newest}. "
                        "Show a plan change agreed in chat in plan mode, so the plan file has every version. Until "
                        f"then it is Plan v{newest}.")
    comp = completion_summary(cfg)
    pv = PLAN_NUMBER.search(comp.get("plan") or "")
    if pv and int(pv.group(1)) < newest:
        problems.append(f"The ledger names this plan with 'Plan v{pv.group(1)}', but the newest plan file is Plan "
                        f"v{newest}. Rename the plan's rows in {cfg['record_file']} to the plan name only (no "
                        "version number, no R-number); the version lives in the plan file.")


def norm(s):
    return re.sub(r"[`*\s]+", " ", s or "").strip(" .;")


rm = re.search(r"Continue (?P<plan>.+?) on branch (?P<branch>[\w./-]+)", text)
if rm:
    comp = comp or completion_summary(cfg)
    branch = current_branch()
    if comp.get("plan") and norm(rm.group("plan")) != norm(comp["plan"]):
        problems.append(f"The restart line must use the plan name exactly as in the ledger: `{restart_line(comp, branch)}`")
    if rm.group("branch").rstrip(".;,`") != branch:
        problems.append(f"The restart line names branch {rm.group('branch')}, but this session is on {branch}.")
    rec = cfg["record_file"]
    try:
        dirty = run_text(["git", "status", "--porcelain", "--", rec], timeout=10).stdout.strip()
        up = run_text(["git", "rev-list", "--count", "@{u}..HEAD"], timeout=10)
        unpushed = up.returncode != 0 or up.stdout.strip() not in ("", "0")
    except Exception:
        dirty, unpushed = "", False
    if dirty or unpushed:
        problems.append(f"Commit and push {rec} to {branch} before giving the restart line: a new session reads "
                        "the record from GitHub, not from this session.")
    # v3.2.10: the Completion lines are Now / Next / Later; every queued row is no longer listed (Weekly-Planner
    # 9 Oct: a send-back for 6 queued rows made the list 25 lines long)
    if comp.get("total") and not re.search(cfg["completion_line_pattern"], text):
        problems.append("Show the Completion lines (Now, Next, Later) with the restart line.")

if not problems:
    sys.exit(0)
r = use_round("handoff", data.get("session_id"), int(cfg["auto_fix_max_rounds"]))
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
log("handoff-guard", {"problems": len(problems)})
block(" ".join(problems) + " Send only what is missing or wrong, then the validation line and the three closing lines.")
