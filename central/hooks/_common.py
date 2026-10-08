"""Shared helpers for the .claude/hooks scripts. No third-party imports."""
import glob
import json
import os
import re
import time
import subprocess
import sys

# Hook scripts run from the loader's cache (~/.cache/hz-rules/<version>/hooks); per-repo files
# (FEATURES.md, WORKING_RECORD.md, .claude/state) live in the project.
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
CENTRAL_ROOT = os.path.dirname(HOOK_DIR)
STATE_DIR = os.path.join(PROJECT_DIR, ".claude", "state")
CONFIG_PATH = os.path.join(HOOK_DIR, "config.json")
RULES_PATH = os.path.join(CENTRAL_ROOT, "rules", "CLAUDE-rules.md")
SEED_DIR = os.path.join(CENTRAL_ROOT, "seed")
SKILLS_DIR = os.path.join(CENTRAL_ROOT, "skills")
WORKER_PATH = os.path.join(CENTRAL_ROOT, "agents", "opus-worker-instructions.md")


def central_version():
    """Version from the first line of MANIFEST.txt ('version: X.Y.Z')."""
    try:
        with open(os.path.join(CENTRAL_ROOT, "MANIFEST.txt"), encoding="utf-8") as f:
            first = f.readline().strip()
        return first.split(":", 1)[1].strip() if first.lower().startswith("version:") else "unknown"
    except OSError:
        return "unknown"

import formats as _F   # v3.2.0: every format the owner sees comes from formats.py

DEFAULT_CONFIG = {
    "routing_guard_mode": "observe",          # observe | enforce | off
    "record_file": "WORKING_RECORD.md",
    "features_file": "FEATURES.md",
    "governance_files": ["CLAUDE.md", "WORKING_RECORD.md", "FEATURES.md", "ARCHITECTURE.md", ".claude/", "docs/", "plans/"],
    "regression_table_pattern": r"(?is)regression\s*table|\|\s*(kept|added|removed|missing)\s*\|",
    # the only interim reply: one status line, and only when asked while a worker still runs
    "progress_line_pattern": _F.WORKING_PATTERN,
    "need_line_max_words": _F.NEED_LINE_MAX_WORDS,
    # v3.1.29: a short note may follow any status ("Checked — PR checked", "Checked. Not sure which prompt"); group 2
    # is the status word alone, so every check reads it the same way
    "validation_line_pattern": _F.VALIDATION_PATTERN,
    "design_triggers": ["redesign", "architecture", "data model", "schema", "migration", "sync layer", "firestore rules", "shared state", "regression", "keeps breaking", "again", "still broken", "refactor"],
    # planner suggestion (plan-gate): strong signals that a plan needs Fable rather than the Opus default
    "fable_planner_signals": ["root cause", "why does", "why is", "investigate", "across all", "every repo", "all repos", "all apps",
                              "migrate everything", "whole codebase", "multi-day", "end to end", "end-to-end"],
    "fable_planner_min_triggers": 2,
    # completion guard (Stop): auto-fix rounds per turn before a final report may stand with open ledger items
    "auto_fix_max_rounds": 1,
    "pause_phrases": ["stop here", "pause here", "that's enough for now", "that is enough for now", "leave the rest", "stop for now"],
    "completion_line_pattern": _F.COMPLETION_PATTERN,
    # completion guard: compare the ledger with this ref (read only, never fetched); rows unchanged against it
    # belong to earlier rounds and are neither counted nor listed
    "ledger_base_ref": "origin/main",
    "completion_open_shown": 5,
    # switchboard (dispatch.py): which check scripts run for which hook event; "tools" = regex on tool_name
    "dispatch": {},
    # quote-block top of every final answer (validation-line.py) and first-reply version line.
    # Each entry is "<icon> <label>"; the check ignores the quote marker, bold and the invisible
    # variation selector in the arrow, but an answer whose labels have no icon is sent back.
    "report_top_labels": _F.CLOSING_LABELS,
    # what a current stub looks like (session-start.py); names are shown to the user in plain words
    "stub_expect": {
        "version": "3.2.5",
        "files": {".claude/agents/sonnet-worker.md": "Sonnet worker",
                  ".claude/agents/planner.md": "planner on the first-choice model (v3.1.30)",
                  ".claude/agents/planner-opus.md": "planner fallback on Opus (v3.1.30)",
                  ".claude/agents/reviewer.md": "reviewer on call (v3.1.28)",
                  ".claude/agents/explore.md": "explorer on Sonnet (v3.1.28)"},
        "settings": {"plansDirectory": ["./plans", "plan files saved in the repository"]},
        # keys the stub must NOT set, so the account's own default applies
        "settings_absent": {"model": "account default model (the stub must not set a session model)",
                            "advisorModel": "advisor off (the stub must not switch on the Fable advisor)"},
        # text each stub file must contain
        "file_text": {".claude/agents/opus-worker.md": [["model: claude-opus-5-5", "Opus helper pinned to Opus 5.5"], ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]],
                      ".claude/hz-loader.py": ["incomplete on GitHub", "loader that reports an incomplete rules repository"],
                      ".claude/agents/sonnet-worker.md": [["model: claude-sonnet-5-5", "Sonnet worker pinned to Sonnet 5.5"], ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]],
                      ".claude/agents/reviewer.md": [["tools: Read, Grep, Glob", "reviewer that only reads"],
                                                     ["effort: high", "reviewer at high effort (v3.2.1)"],
                                                     ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]],
                      ".claude/agents/explore.md": [["model: claude-sonnet-5-5", "explorer pinned to Sonnet 5.5"], ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]],
                      ".claude/agents/planner.md": [["model: claude-fable-5-1", "planner pinned to Fable 5.1"], ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]],
                      ".claude/agents/planner-opus.md": [["model: claude-opus-5-5", "planner fallback pinned to Opus 5.5"], ["use the Read tool (never a shell command)", "helper reads its instructions with the Read tool (v3.2.5)"]]},
        "events": {"UserPromptSubmit": "prompt checks", "PreToolUse": "safety checks before commands and edits",
                   "Stop": "report checks (completion, top lines)",
                   "PostToolUse": "notice after a pull request opens (v3.1.31)",
},
        # which tools an event's matcher must cover ("<needle in the matcher>", "<plain name>")
        "event_matchers": {"PreToolUse": ["mcp__", "GitHub tool check before a pull request"],
                           "PreToolUse ": ["ExitPlanMode", "plan check before approval"],
                           "PreToolUse  ": ["Read|Glob|Grep", "worker step count on reads (v3.1.26)"],
                           "PreToolUse   ": ["SubagentHandback", "worker hand-back check (v3.2.0)"]},
        "allow": {"Bash(git commit:*)": "commit permission", "Bash(gh pr ready:*)": "ready-PR permission",
                  "Read(~/.cache/hz-rules/**)": "reading the central rules without a prompt (v3.1.26)"},
        "pointer_text": {"hooks inactive": "multi-repo fallback in CLAUDE.md"},
    },
    "update_notice": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def read_hook_input():
    """Hook input is UTF-8 JSON; read bytes so a non-UTF-8 system default (e.g. gbk on Chinese Windows)
    cannot garble or drop it."""
    global _TRANSCRIPT
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return {}
    if isinstance(d, dict):
        _TRANSCRIPT = str(d.get("transcript_path") or "")   # v3.2.5: the work folder is found from the session's own edits
    return d


def run_text(args, timeout=10, cwd=None):
    """subprocess.run for text output, always decoded as UTF-8 (never the system default).
    v3.2.5: git commands run in the work folder (where the session edits the record), not only the start folder."""
    return subprocess.run(args, cwd=cwd or work_dir(), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def log(name, payload):
    """Append a JSON line to .claude/state/<name>.jsonl (best effort)."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, f"{name}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---- Prompt number -------------------------------------------------------------------------------
# Rounds are counted per user prompt, not per transcript turn: Stop-hook feedback is written into the
# transcript as another user record, so a turn-derived key would reset the count on every block.
# Only the UserPromptSubmit hook bumps this number; every other hook reads it.
PROMPT_STATE_PATH = os.path.join(STATE_DIR, "prompt-number.json")


def _prompt_state():
    try:
        with open(PROMPT_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def bump_prompt_number(session_id):
    """Count this user prompt; restarts at 1 in a new session. Returns the new number."""
    st = _prompt_state()
    n = int(st.get("n", 0)) + 1 if st.get("session") == (session_id or "") else 1
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(PROMPT_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"session": session_id or "", "n": n}, f)
    except OSError:
        pass
    return n


def prompt_number(session_id):
    """The current prompt's number, or 0 when it is unknown (no UserPromptSubmit hook has run here)."""
    st = _prompt_state()
    if st.get("session") == (session_id or "") and int(st.get("n", 0)) > 0:
        return int(st["n"])
    return 0


def read_transcript(path):
    """Return list of parsed JSONL records; tolerant of bad lines."""
    path = os.path.expanduser(path or "")
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return records


def _content_blocks(rec):
    msg = rec.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def real_prompts(records):
    """Indices of real user prompts (not tool results)."""
    out = []
    for i, rec in enumerate(records):
        if rec.get("type") == "user" and not any(b.get("type") == "tool_result" for b in _content_blocks(rec)):
            out.append(i)
    return out


def first_text_of_turn(turn):
    """First assistant text block in a turn (what the user sees first)."""
    for rec in turn:
        if rec.get("type") != "assistant":
            continue
        for b in _content_blocks(rec):
            if b.get("type") == "text" and b.get("text", "").strip():
                return b["text"]
    return ""


def plain_lines(text):
    """Non-empty lines with markdown decoration removed (bold, headings, quotes, bullets)."""
    out = []
    for l in (text or "").splitlines():
        s = l.replace("*", "").replace("__", "").strip().lstrip("#>-• ").strip()
        if s:
            out.append(s)
    return out


def last_turn(records):
    """Records from the last real user prompt (not a tool_result, not a worker notice) to the end."""
    start = 0
    for i, rec in enumerate(records):
        if rec.get("type") != "user":
            continue
        blocks = _content_blocks(rec)
        if any(b.get("type") == "tool_result" for b in blocks):
            continue
        if any(is_notice_text(b.get("text")) for b in blocks):
            continue   # a worker's notice or a helper's hand-back (v3.2.5) continues the same turn
        start = i
    return records[start:]


def last_assistant_text(records):
    """Text of the final assistant message (all text blocks joined)."""
    for rec in reversed(records):
        if rec.get("type") != "assistant":
            continue
        texts = [b.get("text", "") for b in _content_blocks(rec) if b.get("type") == "text"]
        if texts:
            return "\n".join(texts).rstrip()
    return ""


def tool_uses(records, names=None):
    out = []
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        for b in _content_blocks(rec):
            if b.get("type") == "tool_use" and (names is None or b.get("name") in names):
                out.append(b)
    return out


def is_governance_path(path, cfg):
    p = (path or "").replace("\\", "/")
    rel = p.replace(PROJECT_DIR.replace("\\", "/") + "/", "")
    for g in cfg["governance_files"]:
        if g.endswith("/"):
            if rel.startswith(g) or ("/" + g) in ("/" + rel):
                return True
        elif rel == g or rel.endswith("/" + g):
            return True
    return False


def _msg_log(kind, text):
    """Test aid (v3.2.0): with HZ_MSG_LOG set, every message a check sends is copied there for the word check."""
    path = os.environ.get("HZ_MSG_LOG")
    if path and text:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"kind": kind, "script": os.path.basename(sys.argv[0]), "text": text},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass


def block(reason, kind=None):
    """kind "work" (v3.1.31): the work must continue (open items, setup first, a draft pull request, a destructive
    step) — a real send-back. Anything else from a Stop check is a format, wording or record problem: the switchboard
    saves it as a fix for the next step instead of sending the answer back (a send-back shows the answer twice)."""
    _msg_log("block", reason)
    out = {"decision": "block", "reason": reason}
    if kind:
        out["hz_kind"] = kind
    print(json.dumps(out))
    sys.exit(0)


def save_fixes(session_id, reasons):
    """v3.1.31: format, wording and record problems from a finished answer, kept for the next step."""
    path = os.path.join(STATE_DIR, "pending-fixes.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    mine = data.get(str(session_id or ""), []) + [r for r in reasons if r]
    data[str(session_id or "")] = mine[-8:]
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def take_fixes(session_id):
    """v3.1.31: the saved fixes for this session, removed once handed to the next step."""
    path = os.path.join(STATE_DIR, "pending-fixes.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    mine = data.pop(str(session_id or ""), [])
    for other in list(data):            # an earlier session's leftovers (it ended before its next step) come along
        mine = data.pop(other, []) + mine
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass
    return mine


def add_context(event, text):
    _msg_log("context:" + event, text)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))
    sys.exit(0)


def deny_tool(reason):
    _msg_log("deny", reason)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def count_bullets(text):
    return len(re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+\S", text or ""))


# ---- Hotspot counter (WORKING_RECORD.md) --------------------------------------------------------
# Thresholds from CLAUDE.md > Design Mode > Hotspot counter. Columns are found by header keywords,
# so older records without the newer columns still parse (missing columns count as 0).
HOTSPOT_THRESHOLDS = {"fix round": 3, "recurrence": 2, "regression": 1, "workaround": 3}
FIX_WORDS = ("fix", "bug", "broken", "not working", "doesn't work", "does not work", "error", "regression",
             "again", "still", "crash", "wrong")


def _int(cell):
    m = re.search(r"\d+", cell or "")
    return int(m.group(0)) if m else 0


def hotspot_alerts(cfg):
    """Return one alert string per area that has reached a redesign threshold and is not yet reviewed."""
    path = os.path.join(work_dir(), cfg["record_file"])
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"#+\s*hotspot", l, re.I))
    except StopIteration:
        return []
    rows = []
    for l in lines[start + 1:]:
        if l.startswith("#"):
            break
        if l.strip().startswith("|"):
            body = l.strip()
            body = body[1:] if body.startswith("|") else body
            body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", body)])  # a cell may contain an escaped \|
    if len(rows) < 2:
        return []
    header = [h.lower() for h in rows[0]]

    def col(key):
        return next((i for i, h in enumerate(header) if key in h), None)

    reviewed_i = col("reviewed")
    alerts = []
    for r in rows[1:]:
        if all(set(c) <= set("-: ") for c in r):
            continue  # separator row
        area = r[0] if r else ""
        if not area:
            continue
        if len(r) != len(header):
            alerts.append(f"Hotspot row '{area}' has {len(r)} cells but the header has {len(header)}, so it cannot be "
                          "read reliably. Fix the row (an unescaped | inside a cell is the usual cause); until then "
                          "treat this area as not reviewed.")
            continue
        hits = []
        for key, limit in HOTSPOT_THRESHOLDS.items():
            i = col(key)
            if i is not None and i < len(r) and _int(r[i]) >= limit:
                hits.append(f"{key}s {_int(r[i])} (limit {limit})")
        reviewed = r[reviewed_i] if reviewed_i is not None and reviewed_i < len(r) else ""
        reviewed = re.sub(r"^[^A-Za-z0-9]+", "", reviewed).lower()  # tolerate **yes**, _yes_, ✅ yes
        if hits and not reviewed.startswith("yes"):
            alerts.append(f"Area '{area}' has hit the redesign threshold ({'; '.join(hits)}). "
                          "No patch until the rewrite-vs-repair comparison is presented and the row is marked reviewed.")
    return alerts


def worker_dispatched(records):
    """True if the session has dispatched a subagent at any point (background workers may still be running)."""
    return bool(tool_uses(records, {"Agent", "Task"}))


BUILD_WORKERS = ("opus-worker", "sonnet-worker")
_PR_CREATE = re.compile(r"(^|[;&|\n]\s*)gh\s+pr\s+create\b")
_PR_UNDO = re.compile(r"(^|[;&|\n]\s*)gh\s+pr\s+ready\b[^;&|\n]*--undo")
_PR_READY = re.compile(r"(^|[;&|\n]\s*)gh\s+pr\s+ready\b(?![^;&|\n]*--undo)")


def pr_timeline(records):
    """v3.1.30: the main session's pull-request and worker events in order, for the "pull request last" and "back to
    draft" checks. Each event: (kind, detail) with kind in worker, reviewer, pr_create, pr_draft, pr_ready.
    Also returns the ids of workers or reviewers started but not yet finished (still running)."""
    events, started, finished = [], {}, set()
    for rec in records:
        if rec.get("isSidechain"):
            continue
        raw = json.dumps(rec, ensure_ascii=False) if "task-notification" in str(rec)[:200000] else ""
        if raw:   # v3.1.30: Claude Code runs workers in the background and reports their end in a task notification
            for tid, status in re.findall(r"<tool-use-id>([^<]+)</tool-use-id>.*?<status>(\w+)</status>", raw, re.S):
                if status.lower() in ("completed", "failed", "killed", "stopped", "error", "cancelled"):
                    finished.add(tid)
        for b in _content_blocks(rec):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_result":
                res = b.get("content")
                res = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
                if "Async agent launched" not in res[:300]:   # a background start is not an end
                    finished.add(b.get("tool_use_id"))
                continue
            if b.get("type") != "tool_use":
                continue
            name, inp = b.get("name") or "", b.get("input") or {}
            if name in ("Agent", "Task"):
                st = str(inp.get("subagent_type") or "")
                if st in BUILD_WORKERS:
                    events.append(("worker", st)); started[b.get("id")] = st
                elif st == "reviewer":
                    events.append(("reviewer", st)); started[b.get("id")] = st
            elif name == "Bash":
                cmd = str(inp.get("command") or "")
                if _PR_CREATE.search(cmd):
                    events.append(("pr_create", cmd[:80]))
                if _PR_UNDO.search(cmd):
                    events.append(("pr_draft", cmd[:80]))
                elif _PR_READY.search(cmd):
                    events.append(("pr_ready", cmd[:80]))
            elif re.match(r"^mcp__.*create_pull_request$", name):
                events.append(("pr_create", name))
            elif re.match(r"^mcp__.*update_pull_request$", name) and "draft" in inp:
                events.append(("pr_draft" if inp.get("draft") is True else "pr_ready", name))
    running = [st for i, st in started.items() if i not in finished]
    return events, running


def pr_is_open_ready(events):
    """True when the session opened a pull request and has not switched it back to draft since (last PR event is a
    create or ready). A hand-over may still pass with a 'PR: #n merged/closed/back to draft' line."""
    last = [k for k, _ in events if k in ("pr_create", "pr_draft", "pr_ready")]
    return bool(last) and last[-1] in ("pr_create", "pr_ready")


def pr_branch_state(session_id, branch=None, state=None):
    """v3.1.30: which branches of this session have an open pull request, and whether it is "ready" or "draft".
    git-guard writes it when a pull request is opened, switched back to draft or marked ready; worker-guard and
    pr-ready-guard read it. Keyed by branch, so a merged pull request on an old branch never blocks the next stage."""
    path = os.path.join(STATE_DIR, "pr-branches.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    mine = data.get(str(session_id or ""), {})
    if branch is not None and state is not None:
        mine[branch] = state
        data = {str(session_id or ""): mine}          # keep only this session
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass
    return mine


def is_progress_report(text, records, cfg):
    """The one allowed interim reply: a single status line ("⏳ Working on: …") while a dispatched worker runs.
    Multi-part progress reports are retired."""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return (len(lines) == 1 and bool(re.search(cfg["progress_line_pattern"], lines[0], re.M))
            and worker_dispatched(records))


def use_round(name, session_id, cap):
    """Per-prompt round counter for a Stop check (its own file). Returns (used_before, allowed) and records a use
    when allowed. Keyed on the prompt number from the UserPromptSubmit hook, so Stop feedback cannot reset it.
    None when the prompt number is unknown (caller falls back to stop_hook_active)."""
    n = prompt_number(session_id)
    if not n:
        return None
    key = f"{session_id or ''}:{n}"
    path = os.path.join(STATE_DIR, f"{name}-rounds.json")
    try:
        rounds = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        rounds = {}
    used = int(rounds.get(key, 0))
    if used >= cap:
        return used, False
    if len(rounds) > 50:
        rounds = {}
    rounds[key] = used + 1
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rounds, f)
    except OSError:
        pass
    return used, True


# ---- Deliverable ledger (WORKING_RECORD.md) ------------------------------------------------------
def record_text(cfg):
    """The working record as it is in the work folder (v3.2.5); None when it cannot be read."""
    try:
        return open(os.path.join(work_dir(), cfg["record_file"]), encoding="utf-8").read()
    except OSError:
        return None


def base_record_text(cfg):
    """The working record as it is on the base ref (default origin/main), read only — never fetched.
    None when the ref or the file is not there; callers then fall back to showing everything."""
    ref = cfg.get("ledger_base_ref") or "origin/main"
    try:
        r = run_text(["git", "show", f"{ref}:{cfg['record_file']}"], timeout=5)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    return r.stdout if r.returncode == 0 else None


def _record_table(cfg, heading_regex, text=None):
    """Rows of the first table under the heading matching heading_regex; [] if absent."""
    if text is None:
        text = record_text(cfg)
    if text is None:
        return []
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"#+\s*" + heading_regex, l, re.I))
    except StopIteration:
        return []
    rows = []
    for l in lines[start + 1:]:
        if l.startswith("#"):
            break
        if l.strip().startswith("|"):
            body = l.strip()[1:]
            body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
            rows.append([c.strip() for c in re.split(r"(?<!\\)\|", body)])
    return rows


COMPLETE_WORDS = ("complete", "done", "✅")
WAITING_WORDS = ("waiting on you", "waiting for you", "your step")
QUEUED_WORDS = ("queued",)
CHECK_TAG = re.compile(r"\((?:check|checking)\)", re.I)
PLAN_ROW = re.compile(r"^(?P<plan>.+?)\s*·\s*Stage\s+(?P<k>\d+[a-z]?)\s+of\s+(?P<m>\d+)\b", re.I)
BLOCKED_WORDS = ("blocked", "cannot", "won't fix", "wont fix", "dropped", "superseded", "deferred")


# v3.2.2: the State cell starts with the state; words in the note after it do not count
LEAD_STATES = (("complete", "complete"), ("done", "complete"), ("✅", "complete"), ("partial", "partial"),
               ("not started", "not started"), ("in progress", "in progress"), ("open", "open"),
               ("queued", "queued"), ("waiting on you", "waiting"), ("waiting for you", "waiting"),
               ("your step", "waiting"), ("blocked", "blocked"), ("superseded", "superseded"),
               ("dropped", "blocked"), ("deferred", "blocked"), ("won't fix", "blocked"),
               ("wont fix", "blocked"))


def row_lead_state(state):
    """The state named at the start of a State cell, or None when the cell does not start with a known state."""
    low = re.sub(r"^[\s*_`]+", "", state or "").lower()
    for word, kind in LEAD_STATES:
        if low.startswith(word) and (len(low) == len(word) or not low[len(word)].isalnum()):
            return kind
    return None


def deliverable_ledger(cfg, text=None):
    """List of {name, state, blocked, complete, evidence, row} from the deliverable ledger; template rows skipped."""
    rows = _record_table(cfg, r"deliverable", text)
    if len(rows) < 2:
        return []
    header = [h.lower() for h in rows[0]]
    si = next((i for i, h in enumerate(header) if "state" in h or "status" in h), 1)
    ei = next((i for i, h in enumerate(header) if "evidence" in h), None)
    out = []
    for r in rows[1:]:
        if not r or all(set(c) <= set("-: ") for c in r):
            continue
        name = r[0]
        if not name or "/" in (r[si] if si < len(r) else "") and "COMPLETE / " in (r[si] if si < len(r) else ""):
            continue  # empty or the seed's placeholder row
        state = (r[si] if si < len(r) else "").strip()
        low = state.lower()
        # v3.1.27: a stage that only waits for the user's approval of the plan is queued — not blocked, not a check
        for_approval = bool(re.search(r"\bapprov", low)) and not any(w in low for w in COMPLETE_WORDS)
        lead = row_lead_state(state)
        if lead:
            # v3.2.2: the first word of the State cell decides. A note after it ("QUEUED — after Stage 37 (only if
            # needed; else SUPERSEDED)") no longer changes the state: 3.2.1 dropped that row from the Build count.
            # a stage that only waits for the plan approval stays queued, whatever its first word (v3.1.27)
            for_approval = for_approval and lead != "complete"
            waiting = not for_approval and (lead == "waiting" or (lead in ("partial", "open", "not started",
                                                                          "in progress", "blocked")
                                                                  and any(w in low for w in WAITING_WORDS)))
            flags = {"complete": lead == "complete", "waiting": waiting,
                     "queued": lead == "queued" or for_approval,
                     "blocked": lead in ("blocked", "superseded") and not waiting and not for_approval,
                     "superseded": lead == "superseded"}
        else:
            flags = {"complete": any(w in low for w in COMPLETE_WORDS)
                     and not any(w in low for w in ("incomplete", "not complete")),
                     "waiting": any(w in low for w in WAITING_WORDS) and not for_approval,
                     "queued": any(w in low for w in QUEUED_WORDS) or for_approval,
                     "blocked": (any(w in low for w in BLOCKED_WORDS) and not any(w in low for w in WAITING_WORDS)
                                 and not for_approval),
                     "superseded": "superseded" in low and not any(w in low for w in COMPLETE_WORDS if w != "✅")}
        out.append({"name": name, "state": state,
                    "complete": flags["complete"],
                    "waiting": flags["waiting"],
                    "queued": flags["queued"],
                    "plan": (PLAN_ROW.match(name).group("plan").strip() if PLAN_ROW.match(name) else None),
                    "blocked": flags["blocked"],
                    "superseded": flags["superseded"],
                    # v3.1.24: a Check stage (confirming the work: merges, live check, device check) — labelled
                    # "(Check)" in its name, or a stage waiting on the user
                    "check": bool(CHECK_TAG.search(name)) or flags["waiting"],
                    "evidence": (r[ei] if ei is not None and ei < len(r) else "").strip(),
                    "row": " | ".join(c.strip() for c in r)})
    return out


def completion_summary(cfg):
    """{total, complete, blocked, open, waiting, queued, no_evidence, pct, line, display, scoped, plan}.

    Counted by PLAN when the ledger has plan stage rows ("<plan name> · Stage k of M — …"): every stage of the
    current plan counts, on whatever branch it was done, so a close-out branch shows the same number as the
    plan. The current plan is the one whose rows this branch added or changed, otherwise the last plan in the
    record. Without plan rows, only rows added or changed on this branch count (earlier rounds never block).
    When the base ref cannot be read, scoped is False and the guard does not block on open items."""
    all_items = deliverable_ledger(cfg)
    base = base_record_text(cfg)
    scoped = base is not None
    changed = all_items
    if scoped:
        base_rows = {}
        for i in deliverable_ledger(cfg, base):
            base_rows.setdefault(i["name"], set()).add(i["row"])
        changed = [i for i in all_items if i["row"] not in base_rows.get(i["name"], set())]
    plans = [i["plan"] for i in all_items if i.get("plan")]
    plan = None
    if plans:
        touched = [i["plan"] for i in changed if i.get("plan")]
        plan = touched[-1] if touched else plans[-1]
        items = [i for i in all_items if i.get("plan") == plan]
        scoped = True
    else:
        items = changed
    items = [i for i in items if not i.get("superseded")]   # v3.1.24: dropped by an approval, so not counted
    checks = [i for i in items if i.get("check")]
    if plan and checks:   # v3.1.24: Build (the work) and Check (confirming it) are counted apart
        build = [i for i in items if not i.get("check")]
    else:
        checks, build = [], items
    total = len(build)
    done = [i for i in build if i["complete"]]
    blocked = [i for i in build if i["blocked"] and not i["complete"]]
    waiting = [i["name"] for i in build if i.get("waiting") and not i["complete"]]
    queued = [i["name"] for i in build if i.get("queued") and not i["complete"]]
    open_ = [i["name"] for i in build if not i["complete"] and not i["blocked"] and not i.get("waiting")
             and not i.get("queued")]
    no_ev = [i["name"] for i in done if not i["evidence"]]
    pct = round(100 * len(done) / total) if total else 0
    check_open = [i["name"] for i in checks if not i["complete"]]
    if checks:
        line = (f"Completion: Build {len(done)} of {total} done ({pct}%) · Check {len(checks) - len(check_open)} "
                f"of {len(checks)}")
    else:
        line = f"Completion: {len(done)} of {total} done ({pct}%)"
        if waiting:
            line += f" · Waiting on you: {len(waiting)}"
        if queued:
            line += f" · Queued: {len(queued)}"
    if plan:
        line = f"{line} — {plan}"
    display = completion_display(cfg, line, open_, waiting, [i["name"] for i in blocked], queued)
    if checks:
        states = {i["name"]: i for i in checks}
        display += "\nCheck:\n" + "\n".join(
            f"- {n}" + (" (waiting on you)" if states[n].get("waiting") else " (queued)" if states[n].get("queued")
                        else " (blocked)" if states[n]["blocked"] else "") for n in check_open)
        if not open_ and not blocked and not waiting and not queued and check_open:
            display += ("\nBuild is done; the rest is checking. If a check finds a problem, tell this session. It "
                        "becomes a new Build row.")
    return {"total": total, "complete": len(done), "blocked": len(blocked), "open": open_, "no_evidence": no_ev,
            "waiting": waiting, "queued": queued, "pct": pct, "line": line, "plan": plan, "display": display,
            "scoped": scoped, "check_open": check_open, "check_total": len(checks),
            "build_done": total > 0 and len(done) == total,
            "untagged_checks": [i["name"] for i in checks if not CHECK_TAG.search(i["name"])],
            "not_done": [i["name"] for i in build + checks if not i["complete"]]}


def completion_display(cfg, line, open_names, waiting=(), blocked=(), queued=()):
    """The Completion line, then every item that is not complete, one per line, names only: open items (at most a
    few, then "+N more"), then blocked, queued and waiting ones with their state — so done plus the listed items
    always adds up to the total (v3.1.24: blocked and queued items used to be counted but not shown)."""
    shown = int(cfg.get("completion_open_shown", 5))
    out = [line] + [f"- {n}" for n in open_names[:shown]]
    if len(open_names) > shown:
        out.append(f"+{len(open_names) - shown} more open in the record")
    out += [f"- {n} (blocked)" for n in blocked]
    out += [f"- {n} (queued)" for n in queued]
    out += [f"- Waiting on you: {n}" for n in waiting]
    return "\n".join(out)


# ---- Plan files and the hand-off to a fresh session (v3.1.24) -----------------------------------------------
PLAN_NUMBER = re.compile(r"\bPlan v(\d+)\b")


def newest_plan_version():
    """Highest 'Plan vN' named in the plan files in plans/ (the stub's plansDirectory), or None without plan files."""
    best = None
    folder = os.path.join(PROJECT_DIR, "plans")
    try:
        names = [n for n in os.listdir(folder) if n.lower().endswith(".md")]
    except OSError:
        return None
    for n in names:
        try:
            with open(os.path.join(folder, n), encoding="utf-8", errors="replace") as f:
                text = f.read(200000)
        except OSError:
            continue
        for v in PLAN_NUMBER.findall(text + " " + n.replace("-plan-v", " Plan v")):
            best = max(best or 0, int(v))
    return best


def current_branch():
    """Branch of the work folder (v3.2.5): where the session edits the record, which can be a worktree."""
    try:
        return run_text(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def next_stage(comp):
    """The first item still to do: open, then queued, then waiting, then blocked."""
    name = None
    for key in ("open", "queued", "waiting", "check_open"):
        if comp.get(key):
            name = comp[key][0]
            break
    name = name or (comp.get("not_done") or ["the next stage"])[0]
    m = PLAN_ROW.match(name)
    return name[m.start("k") - len("Stage "):].strip() if m and name[:m.start("k")].rstrip().lower().endswith("stage") else name


def restart_line(comp, branch=None):
    plan = comp.get("plan") or "the current work"
    return f"Continue {plan} on branch {branch or current_branch()}; next: {next_stage(comp)}."


def handoff_text(cfg, comp, after_build=False, lessons=False):
    """The hand-off the session does itself in one reply, so the user never has to ask for it."""
    branch = current_branch()
    rec = cfg["record_file"]
    return ("do the hand-off yourself in this reply. I must not have to ask for it.\n"
            f"1) Update '## Where we are' in {rec}. Write the plan name as in the ledger, the newest Plan vN and its "
            "plan file, the next stage, and the restart line. Point to plan files, commits and pull requests; do not "
            f"copy them. Write no keys or passwords. Then commit and push {rec} to {branch}.\n"
            "2) Show the Completion lines. List every row of the plan that is not complete: open, blocked, queued, "
            f"waiting, Build and Check. Done plus listed must add up ({comp.get('line', '')}).\n"
            "3) Above the --- line, give this restart line in a code block, exactly: "
            f"`{restart_line(comp, branch) if not after_build else restart_after_build(comp, branch)}`\n"
            "In the 'I need from you' line, ask only for my next action (a merge, a check), or nothing. Do not ask me "
            "to open a new session. This session carries on. The restart line is only for later, if the session "
            "closes." + (LESSONS_TEXT.format(rec=rec, plan=comp.get("plan") or "the plan") if lessons else ""))


# v3.2.0: plan versus actual. When the build of a plan is done, the session writes what caused rework, so the next
# plan is better (the summary shows each stage's time against its size).
LESSONS_TEXT = ("\n4) The build of this plan is done. Add '## Lessons — {plan}' to {rec} with 3 lines. Name what "
                "caused rework, which stages ran over their size and why, and which rule or plan habit to change. Put each "
                "proposed change to hz-claude-config in the '❓ Decisions' list, with your recommendation.")


def restart_after_build(comp, branch=None):
    """The restart line for the moment Build reaches 100%: next is the first check."""
    first = (comp.get("check_open") or [None])[0]
    return restart_line(dict(comp, open=[], queued=[], waiting=[], check_open=[first] if first else []), branch)


# ---- Session statistics (switchboard counts send-backs and refusals; the end-of-task summary reads them) --------
STATS_PATH = os.path.join(STATE_DIR, "session-stats.json")


def bump_stat(session_id, key, by=1):
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    s = st.setdefault(session_id or "", {})
    s[key] = int(s.get(key, 0)) + by
    if len(st) > 30:
        st = {session_id or "": s}
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except OSError:
        pass


def read_stats(session_id):
    try:
        with open(STATS_PATH, encoding="utf-8") as f:
            return json.load(f).get(session_id or "", {})
    except (OSError, ValueError):
        return {}


# ---- Edmonton time (v3.1.25) ----------------------------------------------------------------------------------
def edmonton_hour(now_utc=None):
    """v3.2.0: the hour (0–23) in Edmonton, for the evening reminder."""
    from datetime import datetime, timezone
    t = edmonton_time(now_utc or datetime.now(timezone.utc))
    h, rest = t.split(", ")[1].split(":")
    h = int(h) % 12
    return h + (12 if "PM" in rest else 0)


def edmonton_time(now_utc=None):
    """'Oct 4, 6:02 PM MDT' — Mountain Time worked out here (no tz database: Windows Python often lacks one).
    Daylight time (MDT, UTC-6) runs from the second Sunday of March, 2 AM local, to the first Sunday of November,
    2 AM local; otherwise MST (UTC-7)."""
    from datetime import datetime, timedelta, timezone

    def nth_sunday(year, month, n):
        d = datetime(year, month, 1, tzinfo=timezone.utc)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    now = now_utc or datetime.now(timezone.utc)
    start = nth_sunday(now.year, 3, 2) + timedelta(hours=9)   # 2 AM MST = 09:00 UTC
    end = nth_sunday(now.year, 11, 1) + timedelta(hours=8)    # 2 AM MDT = 08:00 UTC
    dst = start <= now < end
    local = now + timedelta(hours=-6 if dst else -7)
    hour = local.hour % 12 or 12
    return f"{local.strftime('%b')} {local.day}, {hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'} {'MDT' if dst else 'MST'}"


# ---- The plan shape that passes the plan check the first time (v3.1.26) --------------------------------------
PLAN_TEMPLATE = _F.PLAN_TEMPLATE   # v3.2.0: the plan shape lives in formats.py


# v3.2.0: the plan store. The plan check saves the plan it shows, per plan name, and makes the change view itself.
# State: {"last": <name shown last>, "plans": {"<name>": {"version", "round", "text", "approved", "file"}}}
PLAN_STORE_PATH = os.path.join(STATE_DIR, "plan-store.json")


def plan_store_load():
    try:
        d = json.load(open(PLAN_STORE_PATH, encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("plans"), dict):
            return d
    except (OSError, ValueError):
        pass
    return {"last": None, "plans": {}}


def plan_store_save(d):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(d, open(PLAN_STORE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError:
        pass


def plan_version_of(text):
    m = re.search(r"\bPlan v(\d+)\b", text or "")
    return int(m.group(1)) if m else None


def plan_name_of(text):
    """The short plan name from the title '# Plan vN — <name> — <status>', in lower case."""
    m = re.search(r"(?m)^#*\s*Plan v\d+\s*[—–-]\s*(.+?)\s*$", text or "")
    if not m:
        return ""
    name = re.split(r"\s+[—–]\s+", m.group(1))[0]
    return re.sub(r"\s+", " ", name).strip().lower()


def plan_norm(text):
    """For comparing: the title's approval words and spacing are not a change."""
    t = re.sub(r"(?i)\b(awaiting approval|approved)\b", " ", text or "")
    return re.sub(r"\s+", " ", t).strip()


def last_plan_approved(records):
    """True if the newest ExitPlanMode with a result was approved, False if it was rejected, None if none has a result."""
    ids = [b.get("id") for b in tool_uses(records, ("ExitPlanMode",))]
    results = {}
    for rec in records:
        if rec.get("type") != "user":
            continue
        for b in _content_blocks(rec):
            if b.get("type") == "tool_result" and b.get("tool_use_id"):
                c = b.get("content")
                if isinstance(c, list):
                    c = " ".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
                results[b["tool_use_id"]] = (bool(b.get("is_error")), str(c or ""))
    for i in reversed(ids):
        if i in results:
            err, txt = results[i]
            # real texts (Oct 2026): "User has approved your plan. …" / "The user doesn't want to proceed with this tool use."
            ok = bool(re.search(r"(?i)has approved your plan", txt)) or not (
                err or re.search(r"(?i)reject|doesn't want to proceed|did not approve|not approved|hook error", txt))
            live_proof("plan-approval", {"approved": ok, "result_text": txt[:160]})
            return ok
    return None


def plan_mark_approved(store, records):
    """Mark the plan shown last as approved when its ExitPlanMode result says so."""
    last = store.get("last")
    if last and last in store["plans"] and not store["plans"][last].get("approved") and last_plan_approved(records):
        store["plans"][last]["approved"] = True
        plan_store_save(store)
    return store


def live_proof(check, detail):
    """v3.2.0: each check writes one line when it runs in a real session, so live proof needs no test by the owner."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        import datetime as _dt
        with open(os.path.join(STATE_DIR, "live-proof.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _dt.datetime.now().isoformat(timespec="seconds"), "check": check,
                                "version": central_version(), **(detail or {})}, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass


# ---- Test runs (stats.py and worker-budget.py) ----
TEST_CMD = re.compile(r"\b(npm\s+(run\s+)?test|npx\s+(playwright|jest|vitest)|playwright|pytest|jest|vitest|unittest|"
                      r"smoke|replay-hooks|node\s+\S*tests?[/\\]|run[-_]?tests?)\b|screenshot|capture", re.I)
# v3.1.26: shell commands that only read count as planning; git and gh get their own group
READ_CMD = re.compile(r"^(cat|head|tail|sed\s+-n|grep|rg|find|ls|dir|wc|type|more|less|tree|stat|file|diff|"
                      r"Get-Content|Select-String|Get-ChildItem|git\s+(log|show|diff|status|blame|grep|ls-files))\b", re.I)
GIT_CMD = re.compile(r"^(git|gh)\b", re.I)


RUNNER = re.compile(r"^(node|npm|npx|pnpm|yarn|python3?|py|pytest|bash|sh|playwright|jest|vitest|\./\S+|\S+\.(sh|cmd|bat))\b", re.I)


def is_test_run(cmd):
    """v3.1.28: a command counts as a test run only when one of its parts starts a program (node, npm, python, a
    script …) that runs something test-like. Reading a test file or log (cat, grep, tail, ls, sed …), waiting for a
    log line, or naming a test in a message is not a test run — the Weekly-Planner Sunday v15 session showed 730
    'test runs', about two thirds of them reads of test files and logs."""
    cmd = str(cmd or "")
    for part in re.split(r"&&|\|\||;|\||\n", cmd):
        part = part.strip().lstrip("( ")
        part = re.sub(r"^(do\s+|then\s+)", "", part)
        for _ in range(3):   # v3.2.0: "time", "timeout 590" and VAR=value before the program
            part = re.sub(r"^([A-Za-z_][A-Za-z0-9_]*=(\"[^\"]*\"|'[^']*'|\S+)\s+)+", "", part)   # v3.2.1: quoted values
            part = re.sub(r"^(time\s+|timeout\s+\d+[smh]?\s+)", "", part)
        if not RUNNER.match(part) or re.match(r"^node\s+--check\b", part):
            continue
        if TEST_CMD.search(part) or ("<<" in part and TEST_CMD.search(cmd)):   # a script written inline
            return True
    return False


# ---- Test speed (v3.2.1) -------------------------------------------------------------------------------------------
# Weekly-Planner consistency pass Stage 3: "timeout 1800 npm test" ran in the background for 30 minutes and was stopped
# (exit=124). 3.2.0 measured only foreground runs, so the split-suite stage was never asked for.
SUBSET_MARKERS = [r"SMOKE_ONLY=", r"--grep\b", r"\s-g\s", r"--shard\b", r"\.(spec|test)\.[jt]s\b", r"--testNamePattern",
                  r"\s-t\s", r"::"]
TEST_SPEED_PATH = os.path.join(STATE_DIR, "test-speed.json")


def is_full_test_run(cmd, cfg=None):
    """A test run with no subset marker: the whole suite."""
    markers = (cfg or {}).get("test_subset_markers") or SUBSET_MARKERS
    return is_test_run(cmd) and not any(re.search(p, str(cmd or "")) for p in markers)


def test_speed_load():
    try:
        return json.load(open(TEST_SPEED_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def test_split_done(cfg):
    """The suite counts as split when FEATURES.md says 'Test speed: full run <n> min' with n within the limit."""
    try:
        feat = open(os.path.join(PROJECT_DIR, cfg["features_file"]), encoding="utf-8").read()
    except (OSError, KeyError):
        return False
    m = re.search(r"(?im)^\s*-?\s*Test speed:\s*full run\s*([\d.]+)\s*min", feat)
    return bool(m) and float(m.group(1)) <= float(cfg.get("full_test_max_minutes", 5))


def test_speed_note(cfg, minutes, cmd, stopped=False):
    """Record a full run's time. Returns the one-time instruction to add the split stage, or ""."""
    st = test_speed_load()
    limit = float(cfg.get("full_test_max_minutes", 5))
    if minutes > float(st.get("slowest_full_minutes") or 0):
        st["slowest_full_minutes"], st["command"] = round(minutes, 1), str(cmd)[:200]
    if stopped:
        st["stopped_by_limit"] = True
    msg = ""
    if (minutes > limit or stopped) and not st.get("told") and not test_split_done(cfg):
        st["told"] = True
        how = (f"was stopped by the time limit after {round(minutes)} minutes (exit 124), so it gave no result"
               if stopped else f"took {round(minutes, 1)} minutes")
        msg = (f"[test speed] The full test run {how}. The aim is {int(limit)} minutes or less. Do not run the full "
               "suite locally again until it is split; use the fast loop, and run the full suite on GitHub. Show the "
               "next Rev of the plan with a stage before the other build stages. That stage first measures where the "
               "time goes: the tests, or the setup before them (install, download, start). It fixes the slow part: a "
               "slow setup runs once and the jobs reuse it; slow tests are split into parts that run side by side, "
               "each under the aim (v3.2.2: Weekly-Planner, 14 of 20 minutes were a browser install). When it is done, add 'Test speed: full run <n> min in <k> parts' to "
               "FEATURES.md ## References.")
        try:
            sp = os.path.join(STATE_DIR, "stop-signals.json")
            sig = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else []
            sig.append({"agent": "tests", "reason": "the full test suite " + how, "told": True})
            json.dump(sig[-20:], open(sp, "w", encoding="utf-8"))
        except (OSError, ValueError):
            pass
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st, open(TEST_SPEED_PATH, "w", encoding="utf-8"))
    return msg


# v3.2.5: a command is "in the background" in two ways. Started with run_in_background, the result says "Command running
# in background with ID: X". Started in the foreground, Claude Code moves it after its time limit (120 s) and says "Command
# did not complete within its 120s timeout and was moved to the background (ID: X)". Only the first was known: in the
# Weekly-Planner Stage 7 session a Sonnet worker's command was moved, ran for 47 minutes, and its helper handed back
# without any refusal.
BG_START_RE = re.compile(r"(?:running in background with ID:|moved to the background \(ID:)\s*([A-Za-z0-9_-]+)")


def background_test_results(records):
    """Finished background test runs in a transcript: [(task id, command, minutes, exit code or None)].
    Start: the tool result 'Command running in background with ID: X'; end: the notice with <task-id>X</task-id>."""
    from datetime import datetime as _d

    def _t(r):
        try:
            return _d.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None
    cmds, started, out = {}, {}, []
    for r in records:
        c = (r.get("message") or {}).get("content")
        if r.get("type") == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                    cmds[b.get("id")] = str((b.get("input") or {}).get("command") or "")   # v3.2.5: also commands moved later
        if r.get("type") == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in cmds:
                    m = BG_START_RE.search(json.dumps(b.get("content")))
                    if m:
                        started[m.group(1)] = (cmds[b["tool_use_id"]], _t(r))
        # v3.2.1: the finish notice can be a queue-operation, an attachment or a user message (real 2.1.293 files)
        text = json.dumps(r, ensure_ascii=False).replace("\\n", "\n") if r.get("type") != "assistant" else ""
        if "<task-notification>" in text:
            for m in re.finditer(r"<task-id>([A-Za-z0-9_-]+)</task-id>", text):
                tid = m.group(1)
                if tid in started:
                    cmd, t0 = started.pop(tid)
                    after = text[m.end():m.end() + 1500]
                    ex = re.search(r"exit code (\d+)", after)
                    code = int(ex.group(1)) if ex else None
                    # real case: "...; echo exit=$?" ends with code 0 while the test itself got 124 — read the output
                    of = re.search(r"<output-file>([^<]+)</output-file>", after)
                    try:
                        tail = open(of.group(1).replace("\\\\", "\\"), encoding="utf-8",
                                    errors="replace").read()[-4000:] if of else ""
                    except OSError:
                        tail = ""
                    if re.search(r"\bexit=124\b", tail):
                        code = 124
                    t1 = _t(r)
                    mins = ((t1 - t0) / 60) if t0 and t1 else 0
                    lim = re.search(r"\btimeout\s+(\d+)", cmd)
                    if code in (None, 0) and lim and mins >= int(lim.group(1)) / 60 - 0.5:
                        code = 124      # it ran the whole time limit: the limit stopped it
                    out.append((tid, cmd, mins, code))
    return out


def background_test_note(cfg, records):
    """Measure finished background full test runs once each; returns the split-stage instruction or ""."""
    st = test_speed_load()
    seen = set(st.get("seen_background") or [])
    msg = ""
    for tid, cmd, mins, code in background_test_results(records):
        if tid in seen or not is_full_test_run(cmd, cfg):
            continue
        seen.add(tid)
        st = test_speed_load()
        st["seen_background"] = sorted(seen)[-50:]
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(st, open(TEST_SPEED_PATH, "w", encoding="utf-8"))
        m = test_speed_note(cfg, mins, cmd, stopped=(code == 124))
        try:
            live_proof("test-speed", {"background_full_run_minutes": round(mins, 1), "exit": code})
        except Exception:
            pass
        msg = msg or m
    return msg


def slow_suite_blocks(cfg):
    """True while the full suite is known to be too slow and is not split yet."""
    st = test_speed_load()
    slow = float(st.get("slowest_full_minutes") or 0) > float(cfg.get("full_test_max_minutes", 5)) or \
        st.get("stopped_by_limit")
    return bool(slow) and not test_split_done(cfg)


# ---- Workers still running (v3.2.1) --------------------------------------------------------------------------------
# Real Claude Code 2.1.293 (read from the program and from session 1573ab09): a background worker's start returns
# "Async agent launched successfully … agentId: <id>"; its finish arrives as <task-notification> with
# <task-id><agentId></task-id> and usually <tool-use-id>, written as a "queue-operation" record, an "attachment"
# (queued_command) or a user message. 3.2.0 looked only at user messages, so finished workers stayed "running".
def open_workers(records, kinds, transcript_path=None, max_minutes=150, exclude_id=None):
    from datetime import datetime as _d, timezone as _tz

    def _t(r):
        try:
            return _d.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None
    started = {}
    for rec in records:
        if rec.get("isSidechain"):
            continue
        c = (rec.get("message") or {}).get("content")
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task") and \
                        str((b.get("input") or {}).get("subagent_type") or "") in kinds:
                    started[b.get("id")] = {"t": _t(rec), "agent": None}
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in started:
                    txt = json.dumps(b.get("content"), ensure_ascii=False)
                    m = re.search(r"agentId:\s*([A-Za-z0-9_-]+)", txt)
                    if m and re.search(r"(?i)launched", txt[:400]):
                        started[b["tool_use_id"]]["agent"] = m.group(1)
                    else:
                        started.pop(b["tool_use_id"], None)    # refused, or finished in the foreground
        raw = json.dumps(rec, ensure_ascii=False) if "<task-notification>" in json.dumps(rec, ensure_ascii=False) else ""
        if raw:
            for note in re.findall(r"<task-notification>(.*?)</task-notification>", raw.replace("\\n", "\n"), re.S):
                status = re.search(r"<status>([a-z]+)</status>", note)
                if status and status.group(1) == "blocked":
                    continue
                tu = re.findall(r"<tool-use-id>([^<]+)</tool-use-id>", note)
                task = re.findall(r"<task-id>([^<]+)</task-id>", note)
                for k in list(started):
                    a = started[k]["agent"] or ""
                    if k in tu or any(a and (t.startswith(a) or a.startswith(t)) for t in task):
                        started.pop(k, None)
    # the call being checked is not "another worker" (3.2.0 counted it: the first start of a session was refused as
    # "Another worker is running"). Without its id, every start in the newest assistant record is left out.
    if exclude_id:
        started.pop(exclude_id, None)
    else:
        last = next((r for r in reversed(records) if r.get("type") == "assistant" and not r.get("isSidechain")), None)
        for b in ((last or {}).get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                started.pop(b.get("id"), None)
    # a worker whose own record shows its hand-back, or that started longer ago than any worker may run, is done
    now = time.time()
    folder = (transcript_path or "")[:-len(".jsonl")] if str(transcript_path or "").endswith(".jsonl") else ""
    for k in list(started):
        a, t0 = started[k]["agent"], started[k]["t"]
        if t0 and now - t0 > max_minutes * 60:
            started.pop(k, None)
            continue
        if a and folder:
            for f in glob.glob(os.path.join(folder, "subagents", f"agent-{a}*.jsonl")):
                try:
                    if "SubagentHandback" in open(f, encoding="utf-8", errors="replace").read()[-200000:]:
                        started.pop(k, None)
                except OSError:
                    pass
    return started

# ---- Report timing (v3.2.2) ----------------------------------------------------------------------------------------
# Weekly-Planner 2026-10-08, and real Claude Code 2.1.293 in tools/real-harness (scenario_early_report.sh): the session
# wrote its full report while the reviewer and a GitHub run still went in the background. Each finish notice then
# started a new turn, and the session wrote a second full report. You saw the decisions and closing lines twice.
def open_background_runs(records):
    """Background shell commands of the main session that have no finish notice yet: {task id: command}."""
    cmds, started = {}, {}
    for r in records:
        if r.get("isSidechain"):
            continue
        c = (r.get("message") or {}).get("content")
        if r.get("type") == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                    cmds[b.get("id")] = str((b.get("input") or {}).get("command") or "")   # v3.2.5: also commands moved later
        if r.get("type") == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in cmds:
                    m = BG_START_RE.search(json.dumps(b.get("content")))
                    if m:
                        started[m.group(1)] = cmds[b["tool_use_id"]]
        if r.get("type") != "assistant" and started:
            raw = json.dumps(r, ensure_ascii=False)
            if "task-notification" in raw:
                for tid in re.findall(r"<task-id>([A-Za-z0-9_-]+)</task-id>", raw.replace("\\n", "\n")):
                    started.pop(tid, None)
    return started


def still_running(records, transcript_path=None):
    """Names of the main session's helpers and background commands that still run (empty list: none)."""
    kinds = set()
    for b in tool_uses(records, {"Agent", "Task"}):
        kinds.add(str((b.get("input") or {}).get("subagent_type") or ""))
    out = []
    if kinds:
        for k, v in open_workers(records, sorted(kinds), transcript_path, exclude_id="-").items():
            out.append("helper " + str(v.get("agent") or k)[:12])
    for tid, cmd in open_background_runs(records).items():
        out.append("command " + cmd.strip().split("\n")[0][:40])
    return out


WAIT_TEXT = ("[report timing] Still running in the background: {what}. End this turn with one line only: '{line}'. "
             "Write no report and no closing lines yet. When the last one has finished, write one full report.")
REPORT_TEXT = ("[report timing] Every helper and background command has finished. Write the one full report now, "
               "with the closing lines. Do not repeat an earlier report: give only what is new.")


# ---- Newer rules on GitHub (v3.2.2) --------------------------------------------------------------------------------
# A session keeps the rules it started with. The Weekly-Planner session of 2026-10-08 started on 3.2.0 and still ran
# it after 3.2.1 was merged, so a fixed problem (the false "build is done" message) went on. The real Claude Code
# (tools/real-harness, 2.1.293) runs the session-start check again when a session is resumed, so reopening loads the
# new rules and keeps the chat.
def _vkey(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", v or ""))


def newer_rules_on_github(timeout=3, max_age_s=1200):
    """The version on GitHub when it is newer than the one this session runs, else "". Checked at most every 20 min."""
    now_v = central_version()
    latest = os.environ.get("HZ_LATEST_VERSION", "")
    if not latest:
        path = os.path.join(STATE_DIR, "rules-latest.json")
        try:
            c = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            c = {}
        if c.get("v") and time.time() - float(c.get("t") or 0) < max_age_s:
            latest = c["v"]
        else:
            try:
                import urllib.request
                base = os.environ.get("HZ_BASE_URL") or \
                    "https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main"
                with urllib.request.urlopen(base + "/central/MANIFEST.txt", timeout=timeout) as r:
                    first = r.readline().decode("utf-8", "replace").strip()
                latest = first.split(":", 1)[1].strip() if first.lower().startswith("version:") else ""
            except Exception:
                latest = c.get("v") or ""
            try:
                os.makedirs(STATE_DIR, exist_ok=True)
                json.dump({"t": time.time(), "v": latest}, open(path, "w", encoding="utf-8"))
            except OSError:
                pass
    return latest if latest and now_v != "unknown" and _vkey(latest) > _vkey(now_v) else ""


# ---- Setup update branches (v3.2.4) --------------------------------------------------------------------------------
# Weekly-Planner 2026-10-08: the branch hz-setup-update-3.2.1 existed on GitHub with no commit of its own (same commit
# as main) and no pull request. Session start only looked for the branch NAME, so it said "already waiting in a pull
# request" and asked for a merge that did not exist; the setup never arrived. The version line also said "waiting" for
# any old hz-setup-update-* branch. A setup branch now counts as waiting only when it holds a change that main lacks.
SETUP_PATHS = (".claude/agents", ".claude/settings.json", ".claude/hz-loader.py", "CLAUDE.md")


def _g(project_dir, args, timeout=10):
    import subprocess
    try:
        return subprocess.run(["git", *args], cwd=project_dir, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def setup_branch_state(project_dir, branch, fetch=True):
    """'none' (no such branch), 'settled' (it holds nothing main lacks: empty or already merged), 'pending' (it holds
    setup changes main lacks: a pull request can be merged), 'unpushed' (v3.2.5: those changes exist only on this PC), or
    'unknown' (GitHub could not be read: treated as waiting)."""
    remote = _g(project_dir, ["ls-remote", "--heads", "origin", branch], timeout=8)
    remote_ok = bool(remote and remote.returncode == 0)
    has_remote = remote_ok and bool(remote.stdout.strip())
    local = _g(project_dir, ["rev-parse", "--verify", "-q", f"refs/heads/{branch}"], timeout=5)
    has_local = bool(local and local.returncode == 0 and local.stdout.strip())
    if not has_remote and not has_local:
        return "none"
    if has_remote and fetch:
        f = _g(project_dir, ["fetch", "-q", "origin", branch], timeout=25)
        if not f or f.returncode != 0:
            return "unknown"
        _g(project_dir, ["fetch", "-q", "origin", "main"], timeout=25)    # best effort; a repository may use master
    tips = []
    if has_remote:
        tips.append(f"refs/remotes/origin/{branch}")
    if has_local:
        tips.append(f"refs/heads/{branch}")
    main = None
    for m in ("refs/remotes/origin/main", "refs/remotes/origin/master", "refs/heads/main", "refs/heads/master"):
        r = _g(project_dir, ["rev-parse", "--verify", "-q", m], timeout=5)
        if r and r.returncode == 0:
            main = m
            break
    if not main:
        return "unknown"
    pend = {}
    for tip in tips:
        ahead = _g(project_dir, ["rev-list", "--count", f"{main}..{tip}"], timeout=8)
        if not ahead or ahead.returncode != 0:
            return "unknown"
        if int((ahead.stdout.strip() or "0")) == 0:
            continue                                    # nothing of its own: empty, or already merged
        # pending = the branch itself changes setup files (against its fork point) AND main does not have that change yet.
        # A branch whose only change is elsewhere, or one merged by squash (main already has its content), is settled.
        mb = _g(project_dir, ["merge-base", main, tip], timeout=8)
        base = (mb.stdout.strip() if mb and mb.returncode == 0 else "")
        if not base:
            return "unknown"
        own = _g(project_dir, ["diff", "--quiet", base, tip, "--", *SETUP_PATHS], timeout=10)
        same = _g(project_dir, ["diff", "--quiet", main, tip, "--", *SETUP_PATHS], timeout=10)
        if own is None or same is None:
            return "unknown"
        if own.returncode == 1 and same.returncode == 1:
            pend[tip] = True
    if pend.get(f"refs/remotes/origin/{branch}"):
        return "pending"
    if pend.get(f"refs/heads/{branch}"):
        return "unpushed"      # v3.2.5: the update is committed on this PC only: no pull request exists
    return "settled"


def setup_update_target(project_dir, version, fetch=True):
    """('waiting', branch) when a real setup pull request waits, ('unpushed', branch) when the update is committed but not
    pushed, else ('new', branch): the first unused branch name.
    A settled branch is never reused and never deleted: the next name is hz-setup-update-<version>-2, -3, ..."""
    base = f"hz-setup-update-{version}"
    for n in range(1, 10):
        name = base if n == 1 else f"{base}-{n}"
        st = setup_branch_state(project_dir, name, fetch=fetch)
        if st in ("pending", "unknown"):
            return "waiting", name
        if st == "unpushed":
            return "unpushed", name
        if st == "none":
            return "new", name
    return "waiting", f"{base}-9"


# ---- Complex-work words in a hand-over (v3.2.5) -------------------------------------------------------------------
# The Weekly-Planner Stage 7 session had 2 hand-overs refused for "architecture" and "sync": the file names
# ARCHITECTURE.md and AUDIT-SYNC.md and the screen name "Sister Sync". Both went to Opus. A word counts only when it
# stands alone in the text, in lower case (a name or a file name does not count), outside file names and backticks.
_FILE_LIKE = re.compile(r"`[^`]*`|\S*[/\\]\S*|\b[\w.-]+\.(?:md|js|css|html|json|txt|py|sh|ya?ml|tsx?|jsx|png|jpe?g)\b")


def complex_hits(text, words):
    stripped = _FILE_LIKE.sub(" ", str(text or ""))
    hits = []
    for w in words:
        tail = r"(?![A-Za-z])" if len(w) <= 5 else ""      # short words ("sync") must stand alone; stems ("diagnos") may not
        for m in re.finditer(r"(?<![A-Za-z0-9])" + re.escape(w) + tail, stripped, re.I):
            tok = stripped[m.start():m.start() + len(w)]
            if len(tok) > 1 and tok.isupper():
                continue                                  # ALL CAPS is a name or a file name
            if tok[:1].isupper():                         # Capitalised after a Capitalised word is a name ("Sister Sync")
                prev = re.search(r"([A-Za-z][\w-]*)\s+$", stripped[:m.start()])
                if prev and prev.group(1)[:1].isupper():
                    continue
            hits.append(w)
            break
    return hits


# ---- Notices that are not requests (v3.2.5) -----------------------------------------------------------------------
# Claude Code 2.1.293 delivers a helper's final report as a user message: "Another Claude session sent a message:
# <agent-message from="<id>"> [Subagent hand-back] …" (7 of 7 helpers in the Weekly-Planner Stage 7 session, 6 of 6 in
# Stage 3). The prompt checks took each one for a request: a false "Full Plan vN is required … Do not edit files before
# approval" (14 records in two sessions), router hints, a new turn, and "waiting for you" time. Version 3.1.30 had fixed
# this only for <task-notification>.
_NOTICE_RE = re.compile(r"^\s*(?:<task-notification>|Another Claude session sent a message:\s*<agent-message\b)")


def is_notice_text(text):
    return bool(_NOTICE_RE.match(str(text or "")))


def is_notice_record(rec):
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, str):
        return is_notice_text(c)
    return isinstance(c, list) and any(isinstance(b, dict) and is_notice_text(b.get("text")) for b in c)


def notice_agent_id(text):
    """The helper id named by a hand-back message, or ''."""
    m = re.search(r'<agent-message\s+from=\\?"([A-Za-z0-9_-]+)', str(text or ""))
    return m.group(1) if m else ""


# ---- The work folder (v3.2.5) -----------------------------------------------------------------------------------
# Weekly-Planner Stage 7: the session started in the main folder (all 340 records show that folder and branch main) and
# did its work in worktrees, reaching them with "cd <folder> &&" inside each command. The checks read the record and the
# branch of the main folder, which holds the closed plan "Money fit and logic": a false "Build 7 of 7" and three demands
# for a restart line of the wrong plan on the wrong branch. The hook's own "cwd" cannot help (it stays the main folder),
# so the work folder is the folder where the session itself edits or reads the record, newest first.
_TRANSCRIPT = ""
_WD = None


def _win_path(p):
    p = str(p or "").strip().strip('"')
    if os.name == "nt":
        m = re.match(r"^/([A-Za-z])/(.*)$", p)
        if m:
            p = m.group(1).upper() + ":/" + m.group(2)
    return p


def _git_common(d):
    try:
        r = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=d, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=5)
        out = r.stdout.strip()
        return os.path.normcase(os.path.realpath(os.path.join(d, out))) if r.returncode == 0 and out else ""
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""


def _record_dirs(path, rec_name):
    """Folders where the main session edited or read the record, in the order of the session."""
    out = []
    try:
        data = open(path, "rb").read().decode("utf-8", "replace")
    except OSError:
        return out
    for line in data.splitlines():
        if rec_name not in line or '"tool_use"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        c = (r.get("message") or {}).get("content")
        for b in c if isinstance(c, list) else []:
            if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                continue
            inp = b.get("input") or {}
            fp = str(inp.get("file_path") or "")
            if b.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit") and fp.replace("\\", "/").endswith(rec_name):
                out.append(os.path.dirname(_win_path(fp)))
            elif b.get("name") == "Bash":
                cmd = str(inp.get("command") or "")
                if rec_name not in cmd:
                    continue
                m = re.search(r'cd\s+"?([^"&;|\n]+?)"?\s*(?:&&|;|\n)', cmd)
                if m:
                    out.append(_win_path(m.group(1)))
                else:
                    m = re.search(r'([A-Za-z]:[/\\][^\s"\']*?|/[^\s"\']*?)[/\\]' + re.escape(rec_name), cmd)
                    if m:
                        out.append(_win_path(m.group(1)))
    return out


def work_dir():
    """The folder whose record and branch the checks use: the newest folder of this repository where the session worked
    on a record that holds plan stage rows; else the start folder."""
    global _WD
    if _WD is not None:
        return _WD
    _WD = PROJECT_DIR
    forced = os.environ.get("HZ_WORK_DIR")
    if forced and os.path.isdir(forced):
        _WD = forced
        return _WD
    if not _TRANSCRIPT or not os.path.isfile(_TRANSCRIPT):
        return _WD
    rec_name = DEFAULT_CONFIG.get("record_file", "WORKING_RECORD.md")
    try:
        rec_name = load_config().get("record_file", rec_name)
    except Exception:
        pass
    home = _git_common(PROJECT_DIR)
    seen = set()
    for d in reversed(_record_dirs(_TRANSCRIPT, rec_name)):
        key = os.path.normcase(os.path.abspath(d))
        if key in seen:
            continue
        seen.add(key)
        rp = os.path.join(d, rec_name)
        if not os.path.isfile(rp):
            continue
        try:
            has_plan = bool(re.search(r"(?m)^\|[^|\n]*·\s*Stage\s+\d+[a-z]?\s+of\s+\d+", open(rp, encoding="utf-8", errors="replace").read()))
        except OSError:
            continue
        if has_plan and (not home or _git_common(d) == home):
            _WD = d
            break
    return _WD


def repo_roots():
    """The start folder and every worktree of the same repository: edits there are edits of this project."""
    roots = [PROJECT_DIR]
    try:
        r = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=PROJECT_DIR, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=5)
        for l in r.stdout.splitlines():
            if l.startswith("worktree "):
                roots.append(l[len("worktree "):].strip())
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return [os.path.normcase(os.path.abspath(x)) for x in roots]


def in_repo(p):
    full = os.path.normcase(os.path.abspath(os.path.join(PROJECT_DIR, str(p or ""))))
    return any(full == r or full.startswith(r + os.sep) for r in repo_roots())


# ---- A refusal by the safety check (v3.2.6) ---------------------------------------------------------------------
# Weekly-Planner 2026-10-08: the auto-mode safety check refused to commit the helper files ("Self-Modification"). The
# end-of-reply setup check then sent the session back twice, and each send-back became a full reply: 3 replies with the
# same decisions. Claude Code writes a refused tool call as a user record with `toolDenialKind` "automode-blocked",
# "automode-unavailable" or "automode-parsing-error" (read from the program). A send-back cannot help then.
def refused_by_safety_check(turn):
    for rec in turn or []:
        if str(rec.get("toolDenialKind") or "").startswith("automode"):
            return True
        c = (rec.get("message") or {}).get("content")
        if rec.get("type") == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    t = json.dumps(b.get("content"), ensure_ascii=False)
                    if len(t) < 700 and ("[Self-Modification]" in t or "denied by the auto mode classifier" in t.lower()):
                        return True
    return False
