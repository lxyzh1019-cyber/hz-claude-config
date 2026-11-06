#!/usr/bin/env python3
"""PostToolUse (v3.1.31): right after a pull request opens or is marked ready for review, ask the main session to send
the owner a notice on their account (Claude Code's PushNotification tool, deferred: load it with ToolSearch). It comes
before the answer, so nothing is sent back and the answer shows once. Claude Code skips the push while the owner is
watching the session; that is fine. Workers never get it."""
import json, os, re, sys
from _common import read_hook_input, load_config, add_context, log

data = read_hook_input()
cfg = load_config()
if any(data.get(f) for f in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)
tool = str(data.get("tool_name") or "")
inp = data.get("tool_input") or {}
resp = json.dumps(data.get("tool_response") or "", ensure_ascii=False)[:2000].lower()
if re.search(r'"is_error":\s*true|"interrupted":\s*true|\berror\b.*\bpull request\b|could not|failed', resp):
    sys.exit(0)                                   # the pull request did not open
def _write_report(pr_url, checks=""):
    """v3.3.5: the summary (bold lines) and the report part; written when the pull request opens and again after the
    checks are read, so the summary holds the check result and the time up to the wait."""
    import pr_report as _pr
    from _common import PROJECT_DIR as _PD, STATE_DIR as _SD
    _plan, _rev = _pr.approved_plan()
    _name = ""
    if _plan:
        _m0 = re.match(r"#+\s*Plan v\d+[^—\n]*—\s*(.*?)\s*—", _plan.split("\n")[0])
        _name = _m0.group(1) if _m0 else ""
    _sum = _pr.summary_block(data.get("transcript_path"), pr_url, _rev, _name, checks) or ""
    _meas = _pr.measured_part(data.get("transcript_path"), _PD) or ""
    os.makedirs(_SD, exist_ok=True)
    with open(os.path.join(_SD, "pr-summary.md"), "w", encoding="utf-8") as _h:
        _h.write(_sum + "\n")
    with open(os.path.join(_SD, "pr-report.md"), "w", encoding="utf-8") as _h:
        _h.write("## Summary\n\n" + _sum + "\n\n" + _meas + "\n")
        if _plan:
            _h.write(f"\n## Approved plan (Rev {_rev})\n\n<details><summary>Show the plan</summary>\n\n{_plan}\n\n</details>\n")
    json.dump({"url": pr_url, "checks": checks, "session": str(data.get("session_id") or "")},
              open(os.path.join(_SD, "pr-summary.json"), "w", encoding="utf-8"))
    return os.path.join(_SD, "pr-summary.md").replace("\\", "/"), os.path.join(_SD, "pr-report.md").replace("\\", "/")


def _deliver(pr_url):
    """v3.3.7 (piece 4): the check puts the report and the scorecard into the pull request text itself (GitHub REST,
    never `gh pr`); Build 4 was sent back twice to paste the summary, and it landed after the closing lines.
    Returns (ok, why)."""
    import pr_text as _pt
    from _common import STATE_DIR as _SD
    _n = _pt.pr_number(pr_url)
    _parts = {"report": open(os.path.join(_SD, "pr-report.md"), encoding="utf-8").read()}
    try:   # piece 9: the scorecard lines, from the session's own file
        import scorecard as _sc
        _parts["scorecard"] = _sc.pr_text(data.get("transcript_path"))
    except Exception:
        pass
    _ok, _why = _pt.update(_n, _parts)
    log("notice-reminder", {"pr_text": _why, "number": _n})
    return _ok, _why


HOOKS = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
CHECKS_CMD = f'python3 "{HOOKS}/pr_checks.py" <number>'


# v3.3.5: after the checks are read, the summary and the report are made again with the result and the time so far
_cmd5 = str(inp.get("command") or "")
if (tool == "Bash" and re.search(r"\bgh\s+(pr\s+checks|run\s+watch)\b|pr_checks\.py", _cmd5)) or re.search(r"mcp__.*(check|status)", tool):
    try:
        from _common import STATE_DIR as _SD5
        _st5 = json.load(open(os.path.join(_SD5, "pr-summary.json"), encoding="utf-8"))
        def _flat(x):
            return " ".join(_flat(v) for v in x.values()) if isinstance(x, dict) else \
                " ".join(_flat(v) for v in x) if isinstance(x, list) else str(x)
        _res = _flat(data.get("tool_response") or "")
        _chk = ("failed" if re.search(r"\bfail(?:ed|ure|ing)?\b|\u2717|\bX\b", _res, re.I) else
                "pending" if re.search(r"checks: (pending|unknown)", _res) else
                "passed" if re.search(r"\bpass(?:ed)?\b|success|\u2713", _res, re.I) else "read")
        _fs5, _ = _write_report(_st5.get("url") or "", _chk)
        log("notice-reminder", {"summary_after_checks": _chk})
        # v3.3.7 (piece 4): the check delivers both: the report into the pull request text, the summary as its own
        # notice (no AI turn, no send-back, never after the closing lines)
        _ok5, _why5 = _deliver(_st5.get("url") or "")
        _out5 = {"systemMessage": open(_fs5, encoding="utf-8").read().strip()}
        if not _ok5 and not _st5.get("told_tool"):
            import pr_text as _pt5
            _st5["told_tool"] = True
            json.dump(_st5, open(os.path.join(_SD5, "pr-summary.json"), "w", encoding="utf-8"))
            _out5["hookSpecificOutput"] = {"hookEventName": "PostToolUse", "additionalContext": (
                f"[report] The check could not write the pull request text ({_why5}). Write the parts of the file "
                f"{_pt5.saved_path()} into the pull request text with the GitHub tool, as they are. One step; no reply.")}
        print(json.dumps(_out5))
    except (OSError, ValueError, ImportError):
        pass
    sys.exit(0)

ready = False
if tool == "Bash":
    cmd = str(inp.get("command") or "")
    ready = bool(re.search(r"(^|[;&|\n]\s*)gh\s+pr\s+create\b", cmd) or
                 re.search(r"(^|[;&|\n]\s*)gh\s+pr\s+ready\b(?![^;&|\n]*--undo)", cmd) or
                 # v3.3.7: the REST way (works in a cloud session too)
                 (re.search(r"(^|[;&|\n]\s*)gh\s+api\b[^;&|\n]*-X\s+POST\b[^;&|\n]*repos/[^\s/]+/[^\s/]+/pulls\b(?!/)", cmd)
                  and not re.search(r"draft=true", cmd)))
elif re.match(r"^mcp__.*create_pull_request$", tool):
    ready = inp.get("draft") is not True
elif re.match(r"^mcp__.*update_pull_request$", tool):
    ready = inp.get("draft") is False
# v3.3.0: the 9 PM reminder comes at the next step after 9 PM Edmonton time, not only at a new message from me
# (12 Oct: one turn ran from 14:03 to 22:54 without a message, so the reminder never came)
try:
    import os as _os
    from _common import edmonton_hour, STATE_DIR as _SD
    from datetime import datetime as _d
    _ev = _d.now().strftime("%Y-%m-%d")
    _np = _os.path.join(_SD, "evening-reminder.json")
    try:
        _done = json.load(open(_np, encoding="utf-8")).get("day")
    except (OSError, ValueError):
        _done = None
    if edmonton_hour() >= int(cfg.get("evening_hour", 21)) and _done != _ev and not ready:
        _os.makedirs(_SD, exist_ok=True)
        json.dump({"day": _ev}, open(_np, "w", encoding="utf-8"))
        log("notice-reminder", {"evening": True})
        add_context("PostToolUse", "[evening] It is after 9 PM in Edmonton. In your next final answer, add one sentence "
                    "to the 'I need from you' line: \"Before you sleep, type 'night check'.\"")
except Exception:
    pass
if not ready:
    sys.exit(0)
log("notice-reminder", {"tool": tool})
try:
    from _common import live_proof
    live_proof("notice-reminder", {"tool": tool})
except ImportError:
    pass
# v3.2.17: the notice names everything that waits (11-12 Oct: "ready to merge" while 10 and 6 questions also waited)
# v3.3.3 (owner, 15 Oct): the summary report and the time and tokens by task and by model, measured here (a hook may
# read the session file; the session itself may not in a cloud session). The chat summary stays short, with one link.
_rep = ""
try:   # v3.3.5: the summary in the Weekly-Planner shape (bold lines) and the report in the checkpoint shape
    _um = re.search(r"https://github\.com/[^\s\"'\\]+/pull/\d+", json.dumps(data.get("tool_response") or ""))
    _url = _um.group(0) if _um else ""
    _fs, _fr = _write_report(_url)
    _ok, _why = _deliver(_url)
    _n = re.search(r"/pull/(\d+)", _url)
    _cc = CHECKS_CMD.replace("<number>", _n.group(1) if _n else "<number>")
    # v3.3.7 (piece 4): the check writes the report and the scorecard into the pull request text and shows the
    # summary as its own notice after the checks are read. The session pastes nothing.
    _rep = ("\n[report] " + ("The check wrote the report into the pull request text. " if _ok else
            f"The check could not write the pull request text ({_why}): write the parts of the file "
            f"{__import__('pr_text').saved_path()} into it with the GitHub tool, as they are. ") +
            f"1. Wait once for the checks, in the foreground: {_cc} (Bash timeout 600000; in a cloud session the "
            "GitHub tool's check status works too). The check then writes the report again and shows the summary as "
            "its own notice. 2. Your own part of the pull request text — '## Quick read' (What changed from the plan; "
            "Decisions during the work; Suggestions, each with a recommendation, naming any setup rule that was the "
            "bottleneck), '## Evidence', '## Regression table' — goes above the report part; keep every <!-- hz-… --> "
            "part as it is. 3. Your final answer: the browser pictures first, if you took any, then the closing lines. "
            "Do not paste the summary.")
except Exception:
    pass
add_context("PostToolUse", "[notice] A pull request is now ready for review. Right before your final answer, send me "
            "one notice with the PushNotification tool (load it with ToolSearch) that names everything in your 'I need "
            "from you' line, for example '<app>: 6 questions + merge #<number> waiting' or '<app>: merge #<number> "
            "waiting'. Do not mention the notice in the answer. If the tool is not in this session, skip it." + _rep)
