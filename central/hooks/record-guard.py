#!/usr/bin/env python3
"""Stop hook: if this turn changed the repository's files (directly, or through a dispatched worker), the working
record must be updated and a regression table produced. Governance-only edits are exempt; files outside the
repository (for example Claude Code's own plan files) never count."""
import json, os, re, subprocess, sys
from _common import (PROJECT_DIR, SEED_DIR, work_dir, in_repo, is_progress_report, read_hook_input, load_config, read_transcript, last_turn, last_assistant_text,
                     tool_uses, is_governance_path, block, use_round)

data = read_hook_input()
cfg = load_config()


def send_back(reason):
    """v3.1.23: at most auto_fix_max_rounds send-backs per user prompt (prompt number from UserPromptSubmit), like
    the format check — another check's block no longer makes this one step aside. stop_hook_active only when the
    prompt number is unknown."""
    r = use_round("record", data.get("session_id"), int(cfg["auto_fix_max_rounds"]))
    if r is None and data.get("stop_hook_active"):
        sys.exit(0)
    if r is not None and not r[1]:
        sys.exit(0)
    block(reason)


records_all = read_transcript(data.get("transcript_path"))
turn = last_turn(records_all)
edits = tool_uses(turn, {"Edit", "Write", "MultiEdit", "NotebookEdit"})
dispatched = bool(tool_uses(turn, {"Agent", "Task"}))
paths = [(e.get("input") or {}).get("file_path") or (e.get("input") or {}).get("path") or "" for e in edits]


def inside_project(p):
    return in_repo(p)   # v3.2.5: edits in a worktree of this repository count


def repo_has_source_changes():
    """True/False from git status (governance paths and hook state ignored); None if git is unavailable."""
    try:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if path.startswith(".claude/state") or is_governance_path(path, cfg):
            continue
        return True
    return False


source_paths = [p for p in paths if p and inside_project(p) and not is_governance_path(p, cfg)]


def turn_start_epoch(records):
    from datetime import datetime
    for rec in records:
        ts = rec.get("timestamp")
        if ts:
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
    return None


def record_changed_outside_edits():
    """Record updated by a shell command: modified since the turn began, or showing in git status."""
    rec_path = os.path.join(work_dir(), cfg["record_file"])
    start = turn_start_epoch(turn)
    if start is not None:
        try:
            return os.path.getmtime(rec_path) >= start
        except OSError:
            return False
    try:  # no timestamp in the transcript: fall back to git status
        r = subprocess.run(["git", "status", "--porcelain", "--", cfg["record_file"]], cwd=work_dir(),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        return r.returncode == 0 and bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return False


record_touched = (any(p.endswith(cfg["record_file"]) for p in paths if inside_project(p))
                  or record_changed_outside_edits())
if not source_paths:
    if not dispatched or repo_has_source_changes() is False:
        sys.exit(0)  # nothing in the repository changed this turn
text = last_assistant_text(turn)
problems = []
features_path = os.path.join(PROJECT_DIR, cfg["features_file"])
try:
    features_is_template = "<app or plan name>" in open(features_path, encoding="utf-8").read()
except OSError:
    features_is_template = True
if features_is_template:
    send_back(f"{cfg['features_file']} is missing or still the unfilled template, so no regression check is possible. "
          f"Before you finish: if it is missing, make it and {cfg['record_file']} from the templates in {SEED_DIR}. "
          "Then put the app's current locked features into it (hz-change-guard). Make the regression "
          f"table and update {cfg['record_file']}.")
# v3.2.7: the record is written at plan approval, at a stage end and before the pull request, not at every event
# (Figure-Skate 8 Oct: 24 main steps, 4.5 min on record, feature list and plan bookkeeping in a 53-minute session)
_stage_event = False
for _r in turn:
    _c = (_r.get("message") or {}).get("content")
    for _b in _c if isinstance(_c, list) else []:
        if not isinstance(_b, dict):
            continue
        if _b.get("type") == "tool_use" and (_b.get("name") in ("ExitPlanMode", "SubagentHandback")
                                             or re.search(r"gh pr create|create_pull_request", json.dumps(_b.get("input"))) or
                                             "create_pull_request" in str(_b.get("name"))):
            _stage_event = True
    if _r.get("type") == "user" and re.search(r"Subagent hand-back|<task-notification>", json.dumps(_r)[:4000]):
        _stage_event = True
if not record_touched and _stage_event:
    problems.append(f"update {cfg['record_file']} (request ledger, hotspot counter, deliverable ledger)")
progress = is_progress_report(text, records_all, cfg)
if not progress and not re.search(cfg["regression_table_pattern"], text):
    problems.append(f"include the regression table against {cfg['features_file']} in exactly this shape (four rows, "
                    "these first-column words):\n| Regression table | Result |\n|---|---|\n| Kept | … |\n| Added | … |\n"
                    "| Intentionally removed | … |\n| Missing | … |\nUpdate the manifest if features changed. It goes above the closing lines")
# v3.1.30: a converted feature list (first line <!-- feature-list: by-screen -->) asks the Kept row for its proof
if not progress and re.search(cfg["regression_table_pattern"], text):
    try:
        converted = "feature-list: by-screen" in open(os.path.join(PROJECT_DIR, cfg["features_file"]),
                                                       encoding="utf-8").read(400)
    except OSError:
        converted = False
    kept = re.search(r"(?im)^\|\s*\**kept\**\s*\|(.*)$", text)
    if converted and not (kept and re.search(r"proof:\s*\S", kept.group(1), re.I)):
        problems.append(f"{cfg['features_file']} is a by-screen list. So the regression table's Kept row names its "
                        "proof. Take it from the compare instructions, not from memory. Shape: '| Kept | <n> features · "
                        "Proof: pictures <n> screens × <sizes> sizes, <k> changed (all planned) · tests <passed>/<total> |'")
if problems:
    send_back("Implementation happened this turn but the record is incomplete. Before finishing: " + "; ".join(problems) + ".")
sys.exit(0)
