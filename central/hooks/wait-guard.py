#!/usr/bin/env python3
"""PreToolUse on Bash (v3.1.30), main session and workers alike:
1. No waiting commands: no sleep over 5 seconds, no loops that wait (while/until with sleep), no tail -f, no watch.
   Claude Code tells the session when a worker or a background command finishes. In the Weekly-Planner PR 118 session
   the main session started two "Wait for the PR 4 fix-pass worker" commands.
2. A command run in the background starts with a time limit of at most 30 minutes (timeout 1800 ...): in the same
   session a background script was still "running" after 11 h 49 m."""
import json, os, re, sys
from _common import read_hook_input, load_config, deny_tool, log, STATE_DIR

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
cmd = str(inp.get("command") or "")
limit = int(cfg.get("background_max_seconds", 1800))
max_sleep = float(cfg.get("max_sleep_seconds", 30))   # v3.3.0: short sleeps cost less than a refused step
UNIT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def seconds(tok):
    tok = (tok or "").rstrip(";&|)")   # v3.3.0: "sleep 5;" was read as no number and refused (17 refusals, 11-12 Oct)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", tok)
    return float(m.group(1)) * UNIT[m.group(2)] if m else None


body = re.sub(r"<<-?\s*'?(\w+)'?.*?^\s*\1\s*$", "", cmd, flags=re.S | re.M)   # ignore here-document text
problems = []
for m in re.finditer(r"(?:^|[;&|(\n]\s*|\bdo\s+|\bthen\s+)sleep\s+(\S+)", body):
    s = seconds(m.group(1))
    if s is None or s > max_sleep:
        problems.append(f"sleep {m.group(1)}")
if re.search(r"\b(while|until)\b[^\n]*?;\s*do\b[\s\S]*?\bsleep\b", body) or \
   re.search(r"\b(while|until)\b[\s\S]*?\bdo\b[\s\S]*?\bsleep\b[\s\S]*?\bdone\b", body):
    problems.append("a loop that waits")
if re.search(r"(?:^|[;&|\n]\s*)tail\s+(-\S*\s+)*-[fF]\b", body) or re.search(r"\btail\s+--follow\b", body):
    problems.append("tail -f")
if re.search(r"(?:^|[;&|\n]\s*)watch\s", body):
    problems.append("watch")
# v3.2.0: do not wait for GitHub in the foreground. In the Weekly-Planner consistency pass the main session sat in
# "gh run watch" 8 times (30 minutes). Start the watch in the background and go on with the next stage.
_gh_wait = re.search(r"(?:^|[;&|\n]\s*)(?:timeout\s+\S+\s+)?gh\s+(run\s+watch|pr\s+checks\b[^\n]*--watch)", body) or \
    re.search(r"\b(while|until)\b[\s\S]*?\bdo\b[\s\S]*?\bgh\s+run\b[\s\S]*?\bdone\b", body)   # real: "timeout 1200 gh run watch", "while [ -z $id ]; do id=$(gh run list …)"
# v3.2.12: a worker waits for its own GitHub run in the foreground (runs take under 5 minutes; the Bash limit is 10).
# The main session then gets one wake-up per worker, not one per GitHub run (Weekly-Planner 10 Oct: 3 extra wake-ups).
_is_worker = bool(data.get("agent_id"))
# v3.2.14: with workers in the foreground the main session has nothing else to do while a run goes, so it waits in the
# foreground too (one turn, no wake-up). A background watch by the main session is refused once per prompt.
# Weekly-Planner 10 Oct: 4 background watches by the main session, 4 wake-ups.
_fg_mode = not os.environ.get("HZ_BACKGROUND_WORKERS")
# v3.3.0 (owner, 13 Oct): a worker does not wait for GitHub. It pushes and hands back; the lead starts the next stage and
# reads the result before the merge stop. 12 Oct: workers waited 157 min for 32 GitHub runs.
if _gh_wait and _is_worker and not os.environ.get("HZ_WORKER_GH_WAIT"):
    log("wait-guard", {"refused": "worker waits for GitHub"})
    deny_tool("Do not wait for GitHub. Your push is done: hand back now with the run id. The lead reads the result "
              "before the merge stop.")
if _fg_mode and _gh_wait and not _is_worker and inp.get("run_in_background"):
    from _common import prompt_number as _pn
    _wf = os.path.join(STATE_DIR, "gh-bg-refused.json")
    try:
        _wr = json.load(open(_wf, encoding="utf-8"))
    except (OSError, ValueError):
        _wr = []
    _wk = f"{data.get('session_id')}:{_pn(data.get('session_id'))}"
    if _wk not in _wr:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump((_wr + [_wk])[-50:], open(_wf, "w", encoding="utf-8"))
        log("wait-guard", {"refused": "github wait in the background"})
        deny_tool("Wait for this GitHub run in the foreground: 'timeout 600 gh run watch <id> --exit-status' with the Bash "
                  "timeout 600000. A background watch wakes this session again later.")
if not inp.get("run_in_background") and _gh_wait and not _is_worker and not _fg_mode:
    log("wait-guard", {"refused": "github wait in the foreground"})
    try:
        from _common import live_proof
        live_proof("github-wait", {"refused": True})
    except ImportError:
        pass
    deny_tool("Do not wait for GitHub in the main session. Give the wait to the worker that pushed: it runs "
              "'timeout 600 gh run watch <id> --exit-status' in the foreground and reports the result. If no worker "
              "runs, start the watch in the background (run_in_background, 'timeout 1800 ') and go on.")
# v3.2.1: while the full suite is known to be too slow and is not split yet, no full local run
try:
    from _common import is_full_test_run, slow_suite_blocks, test_speed_load
    if is_full_test_run(cmd, cfg) and slow_suite_blocks(cfg) and _is_worker:
        # v3.3.0: the worker's hand-over names its fast test ('Test:'); the full run becomes that command in place.
        # 12 Oct: 18 refused full runs, each one a wasted step; GitHub runs the full suite.
        try:
            from _common import read_transcript as _rt
            _ho = ""
            for _r in _rt(data.get("transcript_path")):
                if _r.get("type") == "user":
                    _c = (_r.get("message") or {}).get("content")
                    _ho = _c if isinstance(_c, str) else " ".join(str(b.get("text") or "") for b in (_c or []) if isinstance(b, dict))
                    break
            _tl = re.search(r"(?im)^\s*\**Test:\**\s*`?([^`\n]+?)`?\s*$", _ho)
            if _tl and _tl.group(1).strip() not in cmd and not re.fullmatch(r"\s*npm\s+(run\s+)?test\s*", _tl.group(1)):
                _cd = re.match(r"\s*(cd\s+(?:\"[^\"]+\"|'[^']+'|\S+)\s*(?:&&|;)\s*)", cmd)
                _new = (_cd.group(1) if _cd else "") + _tl.group(1).strip()
                log("wait-guard", {"full run replaced": _new[:120]})
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                  "updatedInput": dict(inp, command=_new),
                                  "additionalContext": "[test] The full suite runs on GitHub. Your fast test command "
                                                       "from the hand-over ran instead."}}))
                sys.exit(0)
        except SystemExit:
            raise
        except Exception:
            pass
    if is_full_test_run(cmd, cfg) and slow_suite_blocks(cfg):
        _st = test_speed_load()
        log("wait-guard", {"refused": "full local test run, suite too slow"})
        deny_tool(f"The full test suite here is too slow ({_st.get('slowest_full_minutes')} min"
                  + (", stopped by the time limit" if _st.get("stopped_by_limit") else "") + "). Do not run it locally "
                  "until it is split. Use the fast loop (the tests the test map names), and run the full suite on "
                  "GitHub. The fast test command is the 'Test:' line of your hand-over.")
except ImportError:
    pass
if problems:
    log("wait-guard", {"refused": problems[:3]})
    deny_tool("No waiting commands (" + ", ".join(sorted(set(problems))[:3]) + "). Claude Code tells you when a worker "
              "or a background command finishes: end the step and continue when that notice comes. Run tests and "
              "scripts in the foreground and let them finish.")
if inp.get("run_in_background"):
    # the limit may follow a cd or settings: "cd app && SMOKE=... timeout 1800 npm test" (real runs start with cd)
    m = re.search(r"(?:^|&&|;|\n|\s)timeout\s+(?:-\S+\s+)*(\S+)\s+\S", body)
    s = seconds(m.group(1)) if m else None
    if s is None or s > limit:
        log("wait-guard", {"refused": "background without limit"})
        deny_tool(f"A background command needs a time limit of at most {limit // 60} minutes: start it with "
                  f"'timeout {limit} ' (for example: cd <folder> && timeout {limit} npm test). A background script ran 11 h 49 m "
                  "in one session.")
sys.exit(0)
