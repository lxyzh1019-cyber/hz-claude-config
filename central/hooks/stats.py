#!/usr/bin/env python3
"""Stop hook that never blocks. It speaks to me through Claude Code's systemMessage (no AI turn, no cost) — the
one notice my app is proven to show ("Stop says: …"):
- the version line `Rules v<version> · <branch> · setup <state>`, on the session's first reply and with every
  summary (the session-start notice is not shown in the desktop app, so the version moved here in v3.1.23);
- when a reply is a finished answer (Status Checked or Validated), a short session summary: tokens and time by
  model (main session and helpers), how much of the tokens was re-reading, hand-overs, refusals and send-backs.
Helper (subagent) records are read from the main transcript (sidechain records), from the session's subagents
folder, or — when neither exists — from the totals Claude Code attaches to each finished hand-over.
Every run logs what it showed, or why it showed nothing, to .claude/state/stats.jsonl."""
import glob, json, os, re, subprocess, sys
from datetime import datetime
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, read_stats, log,
                     central_version, PROJECT_DIR, STATE_DIR)

data = read_hook_input()
cfg = load_config()
tp = data.get("transcript_path") or ""
sid = data.get("session_id") or ""
records = read_transcript(tp)
text = last_assistant_text(records)
m = re.search(cfg["validation_line_pattern"], text or "")
final = bool(m) and m.group(2).split()[0] in ("Checked", "Validated")


def version_line(first=False):
    try:
        from _common import work_dir   # v3.2.5: the branch of the folder where the session works
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=work_dir(), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError, UnicodeError):
        branch = "unknown"
    try:
        from stubcheck import stub_status
        stub = stub_status(cfg, PROJECT_DIR)
    except Exception:
        stub = ""
    if os.path.exists(os.path.join(STATE_DIR, "setup-pending.json")):
        stub = "waiting"   # rewritten on disk at session start; the setup pull request is not merged yet
    elif stub.startswith("OUTDATED"):
        try:   # v3.2.4: waiting only when a setup branch of this version holds changes main lacks (not any old branch)
            from _common import setup_update_target
            kind_, _name = setup_update_target(PROJECT_DIR, str((cfg.get("stub_expect") or {}).get("version", "latest")))
            stub = "waiting" if kind_ == "waiting" else "unpushed" if kind_ == "unpushed" else stub
        except Exception:
            pass
    word = ("current on main (this branch is older)" if stub.startswith("current on main") else
            "current" if stub.startswith("current") else "waiting for your merge" if stub.startswith("waiting")
            else "not pushed yet" if stub.startswith(("unpushed", "committed on this PC"))
            else "needs attention" if stub else "unknown")
    line = f"Rules v{central_version()} · {branch} · setup {word}"
    try:   # v3.2.2: say so when GitHub has newer rules; reopening the session loads them and keeps the chat
        from _common import newer_rules_on_github
        _new = newer_rules_on_github()
        if _new:
            line += f" · v{_new} is on GitHub: start a new session to load it"
    except Exception:
        pass
    # v3.1.30: the main session runs on the main-session model; the planner helper plans on the first-choice model
    main = (cfg.get("main_session_model") or {}) if isinstance(cfg, dict) else {}
    used = ""
    for rec in reversed(records):
        if rec.get("type") == "assistant" and not rec.get("isSidechain") and (rec.get("message") or {}).get("model"):
            used = str(rec["message"]["model"])
            break
    if first and used and main.get("id") and main["id"] not in used and not used.startswith("<"):
        line += (f" · this session runs on {used}: type {main.get('switch')} ({main.get('name')} does the session's "
                 "work; the planner helper plans)")
    return line


shown_path = os.path.join(STATE_DIR, "version-shown.json")
try:
    shown = json.load(open(shown_path, encoding="utf-8"))
except (OSError, ValueError):
    shown = {}
FIRST = not shown.get(sid)   # v3.1.30: the model notice goes only into the session's first notice


def mark_shown():
    shown.clear() if len(shown) > 50 else None
    shown[sid] = True
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(shown, open(shown_path, "w", encoding="utf-8"))
    except OSError:
        pass


# v3.2.2: the summary comes once, with the one full report — not while a helper or background command still runs
# (real harness: 3.2.1 showed it after the early report and again after the finish notice)
try:
    from _common import still_running as _sr
    _left = _sr(records, tp) if final else []
except Exception:
    _left = []
if final and _left:
    log("stats", {"shown": "nothing", "why": "still running: " + ", ".join(_left[:3])})
    sys.exit(0)
if not final:
    if sid and not shown.get(sid):
        mark_shown()
        log("stats", {"shown": "version only", "why": "first reply, not a finished answer"})
        print(json.dumps({"systemMessage": version_line(first=True)}))
    else:
        log("stats", {"shown": "nothing", "why": "not a finished answer (Status Checked or Validated)"})
    sys.exit(0)


def label(model):
    s = (model or "").lower()
    for k in ("fable", "opus", "sonnet", "haiku"):
        if k in s:
            return k.capitalize()
    return model or "other"


def ts(rec):
    try:
        return datetime.fromisoformat(str(rec.get("timestamp", "")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def is_prompt(rec):
    if rec.get("type") != "user":
        return False
    from _common import is_notice_record   # v3.2.5: a helper's hand-back message is not a prompt
    if is_notice_record(rec):
        return False
    c = (rec.get("message") or {}).get("content")
    return isinstance(c, str) or (isinstance(c, list) and not any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c))


tokens, seconds, seen = {}, {}, set()
NAMES = {"validation-line": "format", "completion-guard": "completion", "handoff-guard": "hand-off",
         "record-guard": "record", "setup-guard": "setup", "qc-guard": "QC"}
test_runs = [0]   # v3.1.26: full or partial test runs, main session and helpers
activity = {}   # v3.1.25: tokens by what the step was doing (an estimate, one group per step)
from _common import RUNNER, TEST_CMD, READ_CMD, GIT_CMD, is_test_run   # v3.2.0: shared with the worker check


EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PLAN_TOOLS = {"Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "ExitPlanMode", "EnterPlanMode", "TodoWrite"}
CODE_HELPERS = {"opus-worker", "sonnet-worker"}
PLAN_HELPERS = {"explore", "plan", "planner", "planner-opus"}


# v3.1.28: more read-only shell commands (cut, awk, sed without -i, sort …) count as reading; setting a variable,
# cd and loop keywords are skipped; waiting commands get their own group
READ_MORE = re.compile(r"^(cut|awk|sort|uniq|nl|tr|sed(?!.*\s-i)|echo|printf|jq|basename|dirname|realpath|test|\[|"
                       r"Select-Object|Measure-Object|Format-\w+|Out-String)\b", re.I)
SKIP_PART = re.compile(r"^(cd\s|export\s|set\s|do$|done$|then$|fi$|else$|esac$|\}$|\{$|"
                       r"[A-Za-z_][A-Za-z0-9_]*=(\"[^\"]*\"|'[^']*'|\S*)\s*$)", re.I)
WAIT_CMD = re.compile(r"^(sleep|timeout|wait|until|while\b.*\bsleep|tail\s+(-\S+\s+)*-f|Start-Sleep)\b", re.I)
WAIT_TOOLS = {"Monitor", "BashOutput", "TaskOutput", "ReadNotifications"}   # v3.1.31: 14 steps, 4.8 M in the money session


def shell_parts(cmd):
    """Split a shell command into its programs; drop cd, variable settings and loop keywords. Quoted text and
    inline scripts are blanked first, so their lines are not taken for commands."""
    c = re.sub(r"<<-?\s*'?(\w+)'?.*?^\s*\1\s*$", "<<SCRIPT", str(cmd or ""), flags=re.S | re.M)
    c = re.sub(r'"(?:\\.|[^"\\])*"|\'[^\']*\'', "Q", c, flags=re.S)
    out = []
    for p in re.split(r"&&|\|\||;|\||\n", c):
        p = re.sub(r"^(do|then|else)\s+", "", p.strip())
        p = re.sub(r"^for\s+\S+\s+in\s+.*$", "", p)
        p = re.sub(r"^(timeout\s+\S+\s+|[A-Za-z_][A-Za-z0-9_]*=\S+\s+)+", "", p)
        if p and not SKIP_PART.match(p):
            out.append(p)
    return out


INLINE_SCRIPT = re.compile(r"^(python3?|py|node)\s+(-c|-e|-)\b|<<SCRIPT", re.I)
WRITES = re.compile(r"\bopen\([^)]*['\"][wa]b?['\"]|\.write\(|writeFile|write_text|appendFile|>\s*\S", re.I)
CHANGE_CMD = re.compile(r"^(sed\s+(-\S+\s+)*-i|mkdir|cp|mv|touch|rm|tee|Set-Content|Out-File)\b", re.I)


_read = READ_CMD
READ_CMD = type("R", (), {"match": staticmethod(lambda p: _read.match(p) or READ_MORE.match(p))})


def activity_of(rec, content):
    """testing > coding > planning > other: the first that applies to the step's tools."""
    uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
    names = {b.get("name") for b in uses}
    if any(b.get("name") == "Bash" and is_test_run((b.get("input") or {}).get("command")) for b in uses):
        return "testing"
    helpers = {str((b.get("input") or {}).get("subagent_type") or "").lower() for b in uses
               if b.get("name") in ("Agent", "Task")}
    cmds = [str((b.get("input") or {}).get("command") or "") for b in uses if b.get("name") == "Bash"]
    parts = [p for c in cmds for p in shell_parts(c)]
    # v3.1.28: shell commands that change files, and inline scripts that write files, are coding
    if names & EDIT_TOOLS or helpers & CODE_HELPERS or any(CHANGE_CMD.match(p) for p in parts) or any(
            INLINE_SCRIPT.search(p) for p in parts) and any(WRITES.search(c) for c in cmds):
        return "coding"
    if parts and all(INLINE_SCRIPT.search(p) or READ_CMD.match(p) for p in parts):
        return "reading"             # v3.2.11: an inline script that only reads and prints
    # v3.1.28: a step that only waits (sleep, a loop until a log line appears, following a log) is 'waiting'
    if names & WAIT_TOOLS or (parts and any(WAIT_CMD.match(p) for p in parts)
                              and all(WAIT_CMD.match(p) or READ_CMD.match(p) for p in parts)):
        return "waiting"
    # v3.2.11: 'planning' is plan mode and the planner; reading files and searching is 'reading'. 10 Oct: 'planning 41%'
    # was mostly workers reading code, which looked like Opus planning.
    if names & {"ExitPlanMode", "EnterPlanMode", "TodoWrite"} or helpers & PLAN_HELPERS or rec.get("permissionMode") == "plan":
        return "planning"
    if names & PLAN_TOOLS or (parts and all(READ_CMD.match(p) for p in parts)):
        return "reading"
    if parts and all(GIT_CMD.match(p) or READ_CMD.match(p) for p in parts):
        return "git & pull requests"
    if not uses:
        return "talking"
    return "other"


reread = [0]   # tokens that re-read context already sent before (cache reads)
act_reread = {}   # v3.2.11: the re-read part of each type (owner, 10 Oct: separate planning, reading and re-reading)
CAP = 60 * 60


by_source = {"main": 0, "helpers": 0}
helper_steps = {"tool": 0, "one": 0}   # v3.1.28: worker steps that used a tool, and those with only one tool call


act_secs = {}   # v3.2.0: time by type


file_tokens = {}   # v3.2.0: tokens per helper file, for the role line
file_secs = {}     # v3.2.0: time per helper role, from each helper file's first to last record
file_model_secs = {}   # v3.2.0: the same time, by each helper file's model
helper_files = []      # v3.2.0: (hand-over id, records) for the parallel-group line
extra_helper_recs = [] # v3.2.0: helper records without a hand-over id, for the config-cost line


def add_file(recs, source="main", key=None):
    last_t, last_model, waiting_on_helper, last_act = None, None, False, "other"
    # v3.1.26: Claude Code writes one step as several records (thinking, text, tool call) with the same message id;
    # classify the step on all of its blocks, not on the first record
    blocks_by_id = {}
    for r in recs:
        if r.get("type") == "assistant":
            m = r.get("message") or {}
            if isinstance(m.get("content"), list) and m.get("id"):
                blocks_by_id.setdefault(m["id"], []).extend(m["content"])
    for rec in recs:
        t = ts(rec)
        if rec.get("type") == "assistant":
            msg = rec.get("message") or {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            helper_call = any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")
                              for b in content)
            if str(msg.get("model") or "") == "<synthetic>":   # v3.2.0: Claude Code's own notes (usage limit)
                continue
            mid = msg.get("id") or id(rec)
            lab = label(msg.get("model"))
            u = msg.get("usage") or {}
            if mid not in seen and u:
                seen.add(mid)
                tokens[lab] = tokens.get(lab, 0) + sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                reread[0] += int(u.get("cache_read_input_tokens") or 0)
                by_source[source] += sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                if key:
                    file_tokens[key] = file_tokens.get(key, 0) + sum(int(u.get(k) or 0) for k in (
                        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                act = activity_of(rec, blocks_by_id.get(msg.get("id"), content))
                if source == "helpers":
                    n_calls = sum(1 for b in blocks_by_id.get(msg.get("id"), content)
                                  if isinstance(b, dict) and b.get("type") == "tool_use")
                    if n_calls:
                        helper_steps["tool"] += 1
                        helper_steps["one"] += n_calls == 1
                test_runs[0] += sum(1 for b in blocks_by_id.get(msg.get("id"), content)
                                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash"
                                    and is_test_run((b.get("input") or {}).get("command")))
                activity[act] = activity.get(act, 0) + sum(int(u.get(k) or 0) for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                act_reread[act] = act_reread.get(act, 0) + int(u.get("cache_read_input_tokens") or 0)
            _act_now = activity_of(rec, blocks_by_id.get(msg.get("id"), content))
            if t is not None and last_t is not None:
                seconds[lab] = seconds.get(lab, 0) + min(max(t - last_t, 0), CAP)
                if t - last_t <= int(cfg.get("away_minutes", 60)) * 60:     # v3.2.5: away time belongs to no type
                    act_secs[_act_now] = act_secs.get(_act_now, 0) + min(max(t - last_t, 0), CAP)
            last_model, waiting_on_helper, last_act = lab, helper_call, _act_now
        elif t is not None and last_t is not None and last_model and not is_prompt(rec) and not waiting_on_helper:
            seconds[last_model] = seconds.get(last_model, 0) + min(max(t - last_t, 0), CAP)   # tool time
            _c = (rec.get("message") or {}).get("content")
            _tr = isinstance(_c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in _c)
            _k = last_act if _tr else "waiting"   # v3.2.0: only a tool's own run counts for its type; other gaps wait
            if t - last_t <= int(cfg.get("away_minutes", 60)) * 60:       # v3.2.5: away time belongs to no type
                act_secs[_k] = act_secs.get(_k, 0) + min(max(t - last_t, 0), CAP)
        elif rec.get("type") == "user":
            waiting_on_helper = False   # the helper's own records carry that time
        if t is not None:
            last_t = t


main = [r for r in records if not r.get("isSidechain")]
side = [r for r in records if r.get("isSidechain")]
add_file(main)
helper_found = bool(side)
if side:
    add_file(side, "helpers")
done_files = set()   # v3.1.26: the two search patterns can name the same folder; count each helper file once
_file_tokens = {}   # v3.2.11: (kind, stage) -> tokens, read from each helper's own file
for pattern in (os.path.splitext(tp)[0] + "/subagents/*.jsonl", os.path.join(os.path.dirname(tp), sid, "subagents", "*.jsonl"),
                os.path.splitext(tp)[0] + "/subagents/workflows/*/agent-*.jsonl"):
    for f in sorted(glob.glob(pattern)):
        key = os.path.normcase(os.path.realpath(f))
        if key in done_files:
            continue
        done_files.add(key)
        helper_found = True
        try:   # v3.2.0: the helper's role from its meta file
            _kind = str(json.load(open(f[:-len(".jsonl")] + ".meta.json", encoding="utf-8")).get("agentType") or "helper")
        except (OSError, ValueError):
            _kind = "helper"
        _recs = read_transcript(f)
        add_file(_recs, "helpers", _kind)
        _seen_ids, _ftot, _fstage = set(), 0, ""
        for _r in _recs:
            _m = _r.get("message") or {}
            if _r.get("type") == "user" and not _fstage:
                _sm = re.search(r"(?mi)^\s*Task:\s*(.+?)\s*$", json.dumps(_m.get("content"), ensure_ascii=False)
                                .replace("\\n", "\n"))
                _fstage = _sm.group(1)[:60] if _sm else "-"
            if _r.get("type") == "assistant" and _m.get("usage") and _m.get("id") not in _seen_ids:
                _seen_ids.add(_m.get("id"))
                _ftot += sum(int(_m["usage"].get(k) or 0) for k in ("input_tokens", "output_tokens",
                                                                    "cache_creation_input_tokens", "cache_read_input_tokens"))
        _file_tokens[(_kind, _fstage)] = _file_tokens.get((_kind, _fstage), 0) + _ftot
        try:
            _tuid = str(json.load(open(f[:-len(".jsonl")] + ".meta.json", encoding="utf-8")).get("toolUseId") or "")
        except (OSError, ValueError):
            _tuid = ""
        if _tuid:
            helper_files.append((_tuid, _recs))
        else:
            extra_helper_recs.append(_recs)
        _tt = [ts(r) for r in _recs if ts(r) is not None]
        if _tt:
            file_secs[_kind] = file_secs.get(_kind, 0) + (max(_tt) - min(_tt))
            _fm = next((label((r.get("message") or {}).get("model")) for r in _recs if r.get("type") == "assistant"
                        and str((r.get("message") or {}).get("model") or "") not in ("", "<synthetic>")), "other")
            file_model_secs[_fm] = file_model_secs.get(_fm, 0) + (max(_tt) - min(_tt))

# hand-overs, from the main transcript
handovers, escalated, results = {}, 0, {}
uses = {}
for rec in main:
    for b in ((rec.get("message") or {}).get("content") or []) if isinstance((rec.get("message") or {}).get("content"), list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
            inp = b.get("input") or {}
            st = str(inp.get("subagent_type") or "helper")
            handovers[st] = handovers.get(st, 0) + 1
            uses[b.get("id")] = st
            if re.search(r"Escalated from sonnet-worker:", str(inp.get("prompt") or ""), re.I):
                escalated += 1
    tur = rec.get("toolUseResult")
    if isinstance(tur, dict) and not helper_found:
        tid = next((b.get("tool_use_id") for b in ((rec.get("message") or {}).get("content") or [])
                    if isinstance(b, dict) and b.get("type") == "tool_result"), None)
        st = uses.get(tid)
        if st:
            lab = {"opus-worker": "Opus", "sonnet-worker": "Sonnet"}.get(st, st)
            tot = tur.get("totalTokens") or sum(int((tur.get("usage") or {}).get(k) or 0) for k in (
                "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            tokens[lab] = tokens.get(lab, 0) + int(tot or 0)
            by_source["helpers"] += int(tot or 0)
            act = ("coding" if st in CODE_HELPERS else "planning" if st.lower() in PLAN_HELPERS else "other")
            activity[act] = activity.get(act, 0) + int(tot or 0)
            reread[0] += int((tur.get("usage") or {}).get("cache_read_input_tokens") or 0)
            if tur.get("totalDurationMs"):
                seconds[lab] = seconds.get(lab, 0) + int(tur["totalDurationMs"]) / 1000

# v3.2.0: tokens by helper and by stage. The main session's steps count for the stage it handed out last (before the
# first hand-over: "planning"); each helper's total comes from the hand-over result Claude Code attaches.
by_helper, by_stage, stage_of = {}, {}, {}
_cur, _seen_main = "planning", set()
for rec in main:
    msg = rec.get("message") or {}
    content = msg.get("content") if isinstance(msg.get("content"), list) else []
    if rec.get("type") == "assistant":
        u = msg.get("usage") or {}
        mid = msg.get("id") or id(rec)
        if u and mid not in _seen_main:
            _seen_main.add(mid)
            n = sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens"))
            by_stage.setdefault(_cur, {"main": 0, "helpers": 0})["main"] += n
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                inp = b.get("input") or {}
                stype = str(inp.get("subagent_type") or "helper")
                m_ = re.search(r"(?mi)^\s*Task:\s*(.+?)\s*$", str(inp.get("prompt") or ""))
                stage = (m_.group(1)[:60] if m_ else ("planning" if stype in PLAN_HELPERS or stype == "planner"
                                                       else str(inp.get("description") or stype)[:60]))
                stage_of[b.get("id")] = (stage, stype)
                if m_:
                    _cur = stage
    tur = rec.get("toolUseResult")
    if isinstance(tur, dict):
        tid = next((b.get("tool_use_id") for b in content if isinstance(b, dict) and b.get("type") == "tool_result"),
                   None)
        if tid in stage_of:
            stage, stype = stage_of[tid]
            tot = int(tur.get("totalTokens") or sum(int((tur.get("usage") or {}).get(k) or 0) for k in (
                "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or 0)
            by_helper[stype] = by_helper.get(stype, 0) + tot
            by_stage.setdefault(stage, {"main": 0, "helpers": 0})["helpers"] += tot
# v3.2.11: background helpers return no totals with their start ("async launched"), so every helper showed 0 tokens
# (Weekly-Planner 10 Oct: opus-worker 0 of 26.5 M). Their own files give the numbers.
if not any(by_helper.values()) and _file_tokens:
    for (_k, _st), _n in _file_tokens.items():
        by_helper[_k] = by_helper.get(_k, 0) + _n
        if _st and _st != "-":
            by_stage.setdefault(_st, {"main": 0, "helpers": 0})["helpers"] += _n
# v3.2.0: session time. Usage-limit stops ("You've hit your session limit") are counted apart; the shares are of the
# time without them.
def _ts(r):
    try:
        return datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _owner_prompt(r):
    c = (r.get("message") or {}).get("content")
    return r.get("type") == "user" and isinstance(c, str) and not c.lstrip().startswith(("<", "Another Claude session"))


AWAY_SECONDS = int(cfg.get("away_minutes", 60)) * 60


def session_time(recs):
    tl = [r for r in recs if _ts(r) is not None]
    if len(tl) < 2:
        return None
    wall = _ts(tl[-1]) - _ts(tl[0])
    limit, stops, you, workers, gh, tests, away, away_n = 0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0
    last_a, in_stop = None, None
    uses = {}
    for r in tl:
        t_ = _ts(r)
        m = r.get("message") or {}
        c = m.get("content")
        if r.get("type") == "assistant":
            if "hit your session limit" in json.dumps(c or "", ensure_ascii=False):
                in_stop, stops = t_, stops + 1
            last_a = t_
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    uses[b.get("id")] = (t_, b)
        _cs = (r.get("message") or {}).get("content")
        _raw = json.dumps(r, ensure_ascii=False) if r.get("type") in ("user", "attachment", "queue-operation") else ""
        if "<task-notification>" in _raw and r.get("operation") != "remove" \
                and last_a is not None and in_stop is None:
            workers += max(t_ - last_a, 0)     # v3.2.0: the main session idles until a background worker reports
            last_a = t_
        if _owner_prompt(r):
            if in_stop is not None:
                limit += t_ - in_stop
                in_stop = None
            elif last_a is not None:
                if t_ - last_a > AWAY_SECONDS:     # v3.2.0: sleep or out — shown apart, left out of the shares
                    away += t_ - last_a
                    away_n += 1
                else:
                    you += t_ - last_a
        for b in c if isinstance(c, list) else []:
            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                t0, u = uses[b["tool_use_id"]]
                d = max(t_ - t0, 0)
                n, cmd = u.get("name"), str((u.get("input") or {}).get("command") or "")
                if n in ("AskUserQuestion", "ExitPlanMode"):
                    if d > AWAY_SECONDS:
                        away += d
                        away_n += 1
                    else:
                        you += d
                elif n in ("Agent", "Task"):
                    workers += d
                elif n == "Bash" and re.search(r"\bgh\s+run\b", cmd):
                    gh += d
                elif n == "Bash" and is_test_run(cmd):
                    tests += d
    active = max(wall - limit - away, 1)
    other = max(active - you - workers - gh - tests, 0)
    return {"wall": wall, "limit": limit, "stops": stops, "active": active, "away": away, "away_n": away_n,
            "parts": [("short waits for you", you), ("workers", workers), ("GitHub waits", gh),
                      ("main session test runs", tests), ("main session other", other)]}


ROLE_NAME = {"opus-worker": "Opus worker", "sonnet-worker": "Sonnet worker", "Explore": "explorer", "explore": "explorer"}
main_secs, helper_secs, slowest = 0.0, {}, []
_tl = [r for r in main if _ts(r) is not None]
_uses = {}
for r in _tl:
    c = (r.get("message") or {}).get("content")
    for b in c if isinstance(c, list) else []:
        if isinstance(b, dict) and b.get("type") == "tool_use":
            _uses[b.get("id")] = (_ts(r), b)
        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in _uses:
            t0, u = _uses[b["tool_use_id"]]
            d = max(_ts(r) - t0, 0)
            if u.get("name") in ("Agent", "Task"):
                k = str((u.get("input") or {}).get("subagent_type") or "helper")
                helper_secs[k] = helper_secs.get(k, 0) + d
                _i = u.get("input") or {}
                _m = re.search(r"(?mi)^\s*Task:\s*(.+?)\s*$", str(_i.get("prompt") or ""))
                _d = str(_i.get("description") or (_m.group(1) if _m else "") or "")[:40]
                slowest.append((d, f"{ROLE_NAME.get(k, k)}" + (f" \"{_d}\"" if _d else "")))
            elif u.get("name") == "Bash":
                slowest.append((d, "main: " + str((u.get("input") or {}).get("description") or
                                                  (u.get("input") or {}).get("command") or "")[:40]))
slowest.sort(key=lambda x: -x[0])
_st0 = session_time(main)
if _st0:
    main_secs = _st0["parts"][2][1] + _st0["parts"][3][1] + _st0["parts"][4][1]
total = sum(tokens.values())
try:   # v3.1.24: the prompt hook reads this to ask for the hand-off once the session is long
    tp_ = os.path.join(STATE_DIR, "session-tokens.json")
    try:
        st_ = json.load(open(tp_, encoding="utf-8"))
    except (OSError, ValueError):
        st_ = {}
    st_ = {k: v for k, v in st_.items()} if len(st_) < 50 else {}
    st_[sid] = total
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st_, open(tp_, "w", encoding="utf-8"))
except OSError:
    pass
if not total:
    mark_shown()
    log("stats", {"shown": "version only", "why": "no token counts in the transcript"})
    print(json.dumps({"systemMessage": version_line(first=FIRST)}))
    sys.exit(0)


def big(n):
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{round(n / 1e3)} k"


def mins(sec):
    if sec < 120:     # v3.2.5: a short time shows in seconds ("0 min" hid it)
        return f"{int(round(sec))} s"
    m = int(round(sec / 60))
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def pct(v, of):
    return f"{round(100 * v / of)}%" if of and 100 * v / of >= 0.5 else "<1%"


# v3.1.25: messages written between tool steps (the rules ask for none); the last text of each request is the answer
between, cur_texts = 0, []
for rec in main + [{"type": "user", "message": {"role": "user", "content": "end"}}]:
    if is_prompt(rec):
        ids = [m for m, _ in cur_texts]
        last = ids[-1] if ids else None
        between += len({m for m in ids if m != last})
        cur_texts = []
    elif rec.get("type") == "assistant":
        msg = rec.get("message") or {}
        for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip():
                cur_texts.append((msg.get("id") or id(rec), b["text"]))
# v3.2.0: the session summary in lines — "Tokens and time", then "Session time", then one line of counts
order = sorted(tokens, key=lambda k: -tokens[k])
lines = [version_line(first=FIRST), "Session summary", "Tokens and time",
         f"  Tokens: {big(total)}" + (f" · re-read {pct(reread[0], total)} ({big(reread[0])})" if reread[0] else "")]
MODEL_OF = {"opus-worker": "Opus", "reviewer": "Opus", "planner-opus": "Opus", "sonnet-worker": "Sonnet",
            "Explore": "Sonnet", "explore": "Sonnet", "planner": "Fable"}
model_sec = {}
if file_secs:
    model_sec = dict(file_model_secs)
    _mm = label(next((((r.get("message") or {}).get("model")) for r in reversed(main) if r.get("type") == "assistant"
                      and str((r.get("message") or {}).get("model") or "") not in ("", "<synthetic>")), ""))
    model_sec[_mm] = model_sec.get(_mm, 0) + main_secs
else:
    model_sec = seconds
lines.append("  By model: " + " · ".join(f"{k} {pct(tokens[k], total)} ({big(tokens[k])}) {mins(model_sec.get(k, 0))}"
                                          for k in order))
ROLE = {"opus-worker": "Opus workers", "sonnet-worker": "Sonnet worker", "reviewer": "reviewer", "Explore": "explorer",
        "explore": "explorer", "planner": "planner", "planner-opus": "planner (fallback)"}
role_tok, role_sec = {"main session": by_source["main"]}, {"main session": main_secs}
for k, v in (file_tokens or by_helper).items():
    role_tok[ROLE.get(k, k)] = role_tok.get(ROLE.get(k, k), 0) + v
for k, v in (file_secs or helper_secs).items():
    role_sec[ROLE.get(k, k)] = role_sec.get(ROLE.get(k, k), 0) + v
if by_source["helpers"] and not by_helper and not file_tokens:
    role_tok["helpers"] = by_source["helpers"]
lines.append("  By role: " + " · ".join(f"{k} {pct(v, total)} ({big(v)})" + (f" {mins(role_sec[k])}" if role_sec.get(k) else "")
                                       for k, v in sorted(role_tok.items(), key=lambda x: -x[1]) if v))
act_total = sum(activity.values())
if act_total:
    ACT = ("planning", "reading", "coding", "testing", "waiting", "git & pull requests", "talking", "other")
    NAME = {"coding": "building", "git & pull requests": "git"}
    # v3.2.5: the type times share the session clock. Parallel helpers each add their own time (3 helpers = 3 times the
    # clock) and helper files carry waits; scale them to the worked time so that they add up (real Stage 3 session:
    # types 5 h 5 min against 3 h 48 min actual and 2 h 19 min worked). Testing always shows, also at 0.
    _sess = session_time(main)
    _worked = _sess["active"] if _sess else 0
    _sum = sum(act_secs.values())
    _scale = min(1.0, _worked / _sum) if _worked and _sum else 1.0
    lines.append("  By type: " + " · ".join(f"{NAME.get(k, k)} {pct(activity.get(k, 0), act_total)} ({big(activity.get(k, 0))}) "
                                           f"{mins(act_secs.get(k, 0) * _scale)}" for k in ACT
                                           if activity.get(k) or k == "testing"))
    _rr = sum(act_reread.values())
    if _rr:
        lines.append(f"  Re-read (the memory each step carries again): {pct(_rr, act_total)} ({big(_rr)}) — "
                     + " · ".join(f"{NAME.get(k, k)} {big(act_reread[k])}" for k in ACT if act_reread.get(k)))
st_ = session_time(main)
if st_:
    lines.append(f"Session time: {mins(st_['wall'])} actual · {mins(st_['active'])} worked"
                 + (f" · usage-limit stops {mins(st_['limit'])} ({st_['stops']})" if st_["stops"] else "")
                 + (f" · away {mins(st_['away'])} ({st_['away_n']}, waits over {AWAY_SECONDS // 60} min, left out)"
                    if st_["away"] else ""))
    _parts8 = [f"{k} {pct(v, st_['active'])} ({mins(v)})" for k, v in st_["parts"] if v >= 30]
    if _parts8:   # v3.2.8: no empty line in a short session
        lines.append("  " + " · ".join(_parts8))
# v3.2.0: parallel groups — tokens and time per 'Group:' named in the hand-overs
_grp_of = {}
for _r in main:
    for _b in ((_r.get("message") or {}).get("content") or []) if isinstance((_r.get("message") or {}).get("content"), list) else []:
        if isinstance(_b, dict) and _b.get("type") == "tool_use" and _b.get("name") in ("Agent", "Task"):
            _g = re.search(r"(?mi)^\s*\**Group:\**\s*(.+?)\s*$", str((_b.get("input") or {}).get("prompt") or ""))
            if _g:
                _grp_of[_b.get("id")] = _g.group(1)[:30]
group_tok, group_sec = {}, {}
for _tuid, _recs in helper_files:
    _g = _grp_of.get(_tuid)
    if not _g:
        continue
    _seen_g = set()
    for _r in _recs:
        _m = _r.get("message") or {}
        _u = _m.get("usage") if _r.get("type") == "assistant" else None
        if _u and _m.get("id") not in _seen_g:
            _seen_g.add(_m.get("id"))
            group_tok[_g] = group_tok.get(_g, 0) + sum(int(_u.get(k) or 0) for k in (
                "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    _tt = [ts(r) for r in _recs if ts(r) is not None]
    if _tt:
        group_sec[_g] = group_sec.get(_g, 0) + max(_tt) - min(_tt)
if _grp_of and group_tok:
    lines.append("  By parallel group: " + " · ".join(f"{g} {pct(v, total)} ({big(v)}) {mins(group_sec.get(g, 0))}"
                                                   for g, v in sorted(group_tok.items(), key=lambda x: -x[1])))
# v3.2.0: the config's own cost — helpers the rules require (planner, reviewer, explorer) and steps right after a
# check refused something, in time and tokens; the time share is of the time worked
REQ = {"planner", "planner-opus", "reviewer", "Explore", "explore"}
_ref_tok, _ref_sec = 0, 0.0
_deny = re.compile(r"(?i)hook (error|blocked)|blocked by [^\n]{0,40}hook|PreToolUse:\w+ hook")
for _recs in [main] + [r for _, r in helper_files] + extra_helper_recs:
    _bad = set()
    for _r in _recs:
        _c = (_r.get("message") or {}).get("content")
        if _r.get("type") == "user" and isinstance(_c, list):
            for _b in _c:
                if isinstance(_b, dict) and _b.get("type") == "tool_result" and _deny.search(json.dumps(_b.get("content"), ensure_ascii=False)[:400]):
                    _bad.add(_b.get("tool_use_id"))
    for _i, _r in enumerate(_recs):
        _c = (_r.get("message") or {}).get("content")
        if _r.get("type") == "user" and isinstance(_c, list) and any(isinstance(_b, dict) and _b.get("tool_use_id") in _bad for _b in _c):
            _n = next((x for x in _recs[_i + 1:] if x.get("type") == "assistant"), None)
            if _n:
                _u = (_n.get("message") or {}).get("usage") or {}
                _ref_tok += sum(int(_u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                                               "cache_read_input_tokens"))
                if ts(_n) is not None and ts(_r) is not None:
                    _ref_sec += max(ts(_n) - ts(_r), 0)
_req_tok = sum(v for k, v in (file_tokens or by_helper).items() if k in REQ)
_req_sec = sum(v for k, v in (file_secs or helper_secs).items() if k in REQ)
if _req_tok or _ref_tok:
    _worked = st_["active"] if st_ else 0
    lines.append(f"  Config cost: {mins(_req_sec + _ref_sec)}" + (f" ({pct(_req_sec + _ref_sec, _worked)} of time worked)" if _worked else "")
                 + f" · {big(_req_tok + _ref_tok)} ({pct(_req_tok + _ref_tok, total)} of tokens) — required helpers "
                 f"{mins(_req_sec)}, refused steps {mins(_ref_sec)}")
# v3.2.0: stages against their size (S about 15 min, M about 45, L about 90), from the hand-overs' Task and Size
_est = {"S": 15, "M": 45, "L": 90}
_stage = {}
_span_of = {}
for _tuid, _recs in helper_files:
    _tt = [ts(r) for r in _recs if ts(r) is not None]
    if _tt:
        _span_of[_tuid] = max(_tt) - min(_tt)
_u2 = {}
for _r in main:
    _c = (_r.get("message") or {}).get("content")
    for _b in _c if isinstance(_c, list) else []:
        if not isinstance(_b, dict):
            continue
        if _b.get("type") == "tool_use" and _b.get("name") in ("Agent", "Task"):
            _p = str((_b.get("input") or {}).get("prompt") or "")
            _t = re.search(r"(?mi)^\s*\**Task:\**\s*(.+?)\s*$", _p)
            _z = re.search(r"(?mi)^\s*\**Size:\**\s*([SML])\b", _p)
            if _t and _z:
                _u2[_b.get("id")] = (_t.group(1)[:40], _z.group(1).upper(), ts(_r))
        elif _b.get("type") == "tool_result" and _b.get("tool_use_id") in _u2:
            _name, _sz, _t0 = _u2[_b["tool_use_id"]]
            _d = _span_of.get(_b["tool_use_id"]) or (max(ts(_r) - _t0, 0) if ts(_r) and _t0 else 0)
            _e = _stage.setdefault(_name, [_sz, 0])
            _e[1] += _d
if _stage:
    _over = [(k, v) for k, v in _stage.items() if v[1] > _est[v[0]] * 60]
    lines.append(f"  Stages against size: {len(_stage) - len(_over)} of {len(_stage)} within"
                 + ("; over: " + " · ".join(f"{k} {mins(v[1])} (size {v[0]}, about {_est[v[0]]} min)" for k, v in _over[:4])
                    if _over else ""))
slowest = [x for x in slowest if x[0] >= 60]     # v3.2.1: steps under a minute are not "slow"
if slowest:
    lines.append("  Slowest steps: " + " · ".join(f"{w} {mins(s)}" for s, w in slowest[:3]))
names = {"opus-worker": "Opus", "sonnet-worker": "Sonnet"}
ho = " · ".join(f"{names.get(k, k)} {v}" for k, v in sorted(handovers.items())) or "none"
st = read_stats(sid)
sb = (" (" + " · ".join(f"{NAMES.get(k[9:], k[9:])} {v}" for k, v in sorted(st.items()) if k.startswith("sendback:") and v) + ")"
      if any(k.startswith("sendback:") and v for k, v in st.items()) else "")
lines.append(f"Counts: hand-overs {ho}" + (f" (escalated {escalated})" if escalated else "")
             + f" · test runs {test_runs[0]} · in-between messages {between}"
             + (f" · worker steps {helper_steps['tool']} (one tool per step {round(100 * helper_steps['one'] / helper_steps['tool'])}%)"
                if helper_steps["tool"] else "")
             + f" · refused: planner edits {st.get('refused:routing-guard', 0)}, hand-overs {st.get('refused:worker-guard', 0)},"
             f" plans {st.get('refused:plan-guard', 0)} · send-backs {st.get('sendbacks', 0)}{sb} · saved fixes {st.get('savedfixes', 0)}"
             f" · early reports {st.get('early_reports', 0)}")
if int(cfg.get("fresh_session_hint_tokens", 0)) and total >= int(cfg.get("fresh_session_hint_tokens", 0)):
    lines.append("This session is long: it carries on, hands stages to fresh workers, and keeps a restart line in the record in case you close it.")
mark_shown()
log("stats", {"shown": "summary", "tokens": total, "reread": reread[0], "activity": activity,
               "by_helper": by_helper, "by_stage": by_stage})
print(json.dumps({"systemMessage": "\n".join(lines)}))
