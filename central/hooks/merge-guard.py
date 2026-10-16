#!/usr/bin/env python3
"""Stop, v3.2.8: ask me to merge a pull request only after GitHub tested its last change.
Weekly-Planner 8 Oct: the tests on GitHub had failed since PR 1 (a hint cut off by about 3 pixels), and I was still asked
to merge. When the reply asks me to merge and the session pushed or opened a pull request this turn, it must have read
the checks after its last push (gh pr checks, gh run watch or gh run view). If it did not, or they failed and the reply
does not say so, one reminder. A setup pull request (hz-setup-update-*) is left out. No reminder after a refusal by the
safety check."""
import json, re, sys
from _common import (read_hook_input, read_transcript, last_turn, last_assistant_text, block, use_round,
                     refused_by_safety_check)

data = read_hook_input()
records = read_transcript(data.get("transcript_path"))
turn = last_turn(records)
text = last_assistant_text(records) or ""
m = re.search(r"I need from you:?\**:?(.*)", text)
if not m or not re.search(r"\bmerge\b", m.group(1), re.I):
    sys.exit(0)
# v3.3.6 (G2, G3, G4, G6 in one gate, owner 16 Oct: "find the root"). Their shared root: the last step depended on the
# session obeying a notice (run #15: no summary, and the merge request came before the checks were read). Now code
# decides: a merge request needs the summary file made after the checks, pasted as it is. One send-back at most.
try:
    import os as _o6
    from _common import STATE_DIR as _SD6
    _jf, _sf = _o6.path.join(_SD6, "pr-summary.json"), _o6.path.join(_SD6, "pr-summary.md")
    if _o6.path.exists(_jf) and _o6.path.exists(_sf) and not _o6.environ.get("HZ_FULL_RULES"):
        _st6 = json.load(open(_jf, encoding="utf-8"))
        _need6 = None
        if _st6.get("session") and _st6.get("session") != str(data.get("session_id") or ""):
            pass                                    # another session's pull request
        elif not _st6.get("checks"):
            _need6 = ("Before you ask me to merge, read the pull request's checks once (gh pr checks <number> --watch; in "
                      "a cloud session, the GitHub tool). The summary file " + _sf.replace("\\", "/") + " is then made "
                      "again with the result. Paste it as it is, after the browser pictures, above the closing lines.")
        elif f"**GitHub checks:** {_st6.get('checks')}" not in text:
            _need6 = ("Paste the summary file " + _sf.replace("\\", "/") + " as it is, after the browser pictures and "
                      "above the closing lines. Do not write your own summary.")
        if _need6:
            _r6 = use_round("merge-summary", data.get("session_id"), 1)
            if (_r6[1] if _r6 is not None else not data.get("stop_hook_active")):
                block(_need6, kind="work")
except SystemExit:
    raise
except Exception:
    pass
PUSH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b|\bgh\s+pr\s+create\b")
CHECKS = re.compile(r"\bgh\s+pr\s+checks\b|\bgh\s+run\s+(?:watch|view)\b")
last_push, checks, setup = None, [], False
checked_before = False   # v3.2.10: checks were read after an earlier push of this turn
results = {}
for r in turn:
    c = (r.get("message") or {}).get("content")
    for b in c if isinstance(c, list) else []:
        if not isinstance(b, dict):
            continue
        _nm = str(b.get("name") or "")
        if b.get("type") == "tool_use" and _nm.startswith("mcp__"):   # v3.3.4 (P11): the GitHub tool in the cloud
            if re.search(r"create_pull_request|push_files", _nm):
                checked_before = checked_before or bool(checks)
                last_push, checks, setup = b.get("id"), [], False
            elif re.search(r"check|status|workflow_run|job", _nm) and last_push:
                checks.append(b.get("id"))
        if b.get("type") == "tool_use" and b.get("name") == "Bash":
            cmd = str((b.get("input") or {}).get("command") or "")
            if PUSH.search(cmd):
                checked_before = checked_before or bool(checks)
                last_push, checks = b.get("id"), []
                setup = "hz-setup-update" in cmd
            elif CHECKS.search(cmd) and last_push:
                checks.append(b.get("id"))
        elif b.get("type") == "tool_result":
            results[b.get("tool_use_id")] = json.dumps(b.get("content"), ensure_ascii=False)
if not last_push or setup or refused_by_safety_check(turn):
    sys.exit(0)
# v3.2.17: checks read by a worker in this turn count too. Weekly-Planner 12 Oct: the worker read the green code run, the
# main session then pushed record notes only ([skip ci]), and this check sent the answer back, so it showed twice.
if not checks and not checked_before:
    try:
        import glob as _g, os as _o
        from datetime import datetime as _dt
        def _ts(r):
            return _dt.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
        _start = min((_ts(r) for r in turn if r.get("timestamp")), default=None)
        _tp = str(data.get("transcript_path") or "")
        _sub = _o.path.join(_o.path.splitext(_tp)[0], "subagents")
        for _f in _g.glob(_o.path.join(_sub, "*.jsonl")):
            if _start is None or _o.path.getmtime(_f) < _start:
                continue
            for _l in open(_f, encoding="utf-8", errors="replace"):
                if "gh " not in _l:
                    continue
                try:
                    _r = json.loads(_l)
                except ValueError:
                    continue
                if _r.get("timestamp") and _ts(_r) < _start:
                    continue
                for _b in (((_r.get("message") or {}).get("content")) or []):
                    if isinstance(_b, dict) and _b.get("type") == "tool_use" and CHECKS.search(
                            str((_b.get("input") or {}).get("command") or "")):
                        checked_before = True
    except Exception:
        pass
# v3.2.10: a last push that changed only notes (the record, docs, plans) needs no new wait when the checks of the code
# before it were read this turn. Weekly-Planner 9 Oct: 8 minutes waiting for a run on a record-only commit.
if not checks and checked_before:
    try:
        from _common import run_text, load_config
        _notes = tuple((load_config().get("notes_paths") or ["WORKING_RECORD.md", "FEATURES.md", "docs/", "plans/"]))
        _files = [f for f in run_text(["git", "show", "--name-only", "--format=", "HEAD"], timeout=10).stdout.splitlines()
                  if f.strip()]
        if _files and all(f.startswith(_notes) or f in _notes for f in _files):
            sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass
failed = any(re.search(r"\bfail(?:ed|ing|ure)?\b|\bX\s", results.get(i, ""), re.I) for i in checks)
# v3.3.0: remember the commit whose checks were read green; a later turn that pushed only notes after it passes
# (12 Oct 22:09: the newest commit held only the report; its code had been read green in the turn before)
try:
    import os as _o3
    from _common import run_text as _rt3, STATE_DIR as _SD3, load_config as _lc3
    _sf = _o3.path.join(_SD3, "checks-read.json")
    if (checks and not failed) or (not checks and checked_before):
        _head = _rt3(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
        if _head:
            _o3.makedirs(_SD3, exist_ok=True)
            json.dump({"sha": _head}, open(_sf, "w", encoding="utf-8"))
    elif not checks and not checked_before:
        _sha = json.load(open(_sf, encoding="utf-8")).get("sha")
        _nts = tuple(_lc3().get("notes_paths") or ["WORKING_RECORD.md", "FEATURES.md", "docs/", "plans/"])
        _fl = [f for f in _rt3(["git", "diff", "--name-only", f"{_sha}..HEAD"], timeout=10).stdout.splitlines() if f.strip()]
        _ok = _rt3(["git", "merge-base", "--is-ancestor", _sha, "HEAD"], timeout=10).returncode == 0
        if _sha and _ok and all(f.startswith(_nts) or f in _nts for f in _fl):
            sys.exit(0)
except SystemExit:
    raise
except Exception:
    pass
says_red = re.search(r"\b(red|fail(?:ed|ing|s)?)\b", text, re.I)
if checks and (not failed or says_red):
    sys.exit(0)
r = use_round("merge-checks", data.get("session_id"), 1)
if (r[1] if r is not None else not data.get("stop_hook_active")):
    block(("The checks of your last push failed. Fix them first, or say plainly in the reply that they are red and why "
           "I should merge anyway." if checks else
           "Before you ask me to merge, read the checks of your last push: gh pr checks <number> --watch (or gh run "
           "watch; in a cloud session, the GitHub tool's check status). Then report the result in one line."), kind="work")
