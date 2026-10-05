"""Shared helpers for the .claude/hooks scripts. No third-party imports."""
import json
import os
import re
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

DEFAULT_CONFIG = {
    "routing_guard_mode": "observe",          # observe | enforce | off
    "record_file": "WORKING_RECORD.md",
    "features_file": "FEATURES.md",
    "governance_files": ["CLAUDE.md", "WORKING_RECORD.md", "FEATURES.md", "ARCHITECTURE.md", ".claude/", "docs/", "plans/"],
    "regression_table_pattern": r"(?is)regression\s*table|\|\s*(kept|added|removed|missing)\s*\|",
    # the only interim reply: one status line, and only when asked while a worker still runs
    "progress_line_pattern": r"^\s*⏳\s*Working on:\s*\S.*$",
    "need_line_max_words": 30,
    "validation_line_pattern": r"(?m)Confidence:\s*(High|Medium|Low)\s*·\s*Status:\s*(Proposed|Checked|Validated(\s*—\s*\S.*)?|Uncertain)\s*$",
    "design_triggers": ["redesign", "architecture", "data model", "schema", "migration", "sync layer", "firestore rules", "shared state", "regression", "keeps breaking", "again", "still broken", "refactor"],
    # planner suggestion (plan-gate): strong signals that a plan needs Fable rather than the Opus default
    "fable_planner_signals": ["root cause", "why does", "why is", "investigate", "across all", "every repo", "all repos", "all apps",
                              "migrate everything", "whole codebase", "multi-day", "end to end", "end-to-end"],
    "fable_planner_min_triggers": 2,
    # completion guard (Stop): auto-fix rounds per turn before a final report may stand with open ledger items
    "auto_fix_max_rounds": 1,
    "pause_phrases": ["stop here", "pause here", "that's enough for now", "that is enough for now", "leave the rest", "stop for now"],
    "completion_line_pattern": r"Completion:\s*(?:Build\s+)?(\d+)\s+of\s+(\d+)",
    # completion guard: compare the ledger with this ref (read only, never fetched); rows unchanged against it
    # belong to earlier rounds and are neither counted nor listed
    "ledger_base_ref": "origin/main",
    "completion_open_shown": 5,
    # switchboard (dispatch.py): which check scripts run for which hook event; "tools" = regex on tool_name
    "dispatch": {},
    # quote-block top of every final answer (validation-line.py) and first-reply version line.
    # Each entry is "<icon> <label>"; the check ignores the quote marker, bold and the invisible
    # variation selector in the arrow, but an answer whose labels have no icon is sent back.
    "report_top_labels": ["📌 Result:", "👉 I need from you:", "➡️ Next:"],
    # what a current stub looks like (session-start.py); names are shown to the user in plain words
    "stub_expect": {
        "version": "3.1.28",
        "files": {".claude/agents/sonnet-worker.md": "Sonnet worker",
                  ".claude/agents/reviewer.md": "reviewer on call (v3.1.28)",
                  ".claude/agents/explore.md": "explorer on Sonnet (v3.1.28)"},
        "settings": {"plansDirectory": ["./plans", "plan files saved in the repository"]},
        # keys the stub must NOT set, so the account's own default applies
        "settings_absent": {"model": "account default model (the stub must not set a session model)",
                            "advisorModel": "advisor off (the stub must not switch on the Fable advisor)"},
        # text each stub file must contain
        "file_text": {".claude/agents/opus-worker.md": ["model: claude-opus-5-5", "Opus helper pinned to Opus 5.5"],
                      ".claude/hz-loader.py": ["incomplete on GitHub", "loader that reports an incomplete rules repository"],
                      ".claude/agents/sonnet-worker.md": ["model: claude-sonnet-5-5", "Sonnet worker pinned to Sonnet 5.5"],
                      ".claude/agents/reviewer.md": ["tools: Read, Grep, Glob", "reviewer that only reads"],
                      ".claude/agents/explore.md": ["model: claude-sonnet-5-5", "explorer pinned to Sonnet 5.5"]},
        "events": {"UserPromptSubmit": "prompt checks", "PreToolUse": "safety checks before commands and edits",
                   "Stop": "report checks (completion, top lines)",
},
        # which tools an event's matcher must cover ("<needle in the matcher>", "<plain name>")
        "event_matchers": {"PreToolUse": ["mcp__", "GitHub tool check before a pull request"],
                           "PreToolUse ": ["ExitPlanMode", "plan check before approval"],
                           "PreToolUse  ": ["Read|Glob|Grep", "worker step count on reads (v3.1.26)"]},
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
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return {}


def run_text(args, timeout=10):
    """subprocess.run for text output, always decoded as UTF-8 (never the system default)."""
    return subprocess.run(args, cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8",
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
    """Records from the last real user prompt (not a tool_result) to the end."""
    start = 0
    for i, rec in enumerate(records):
        if rec.get("type") != "user":
            continue
        blocks = _content_blocks(rec)
        if any(b.get("type") == "tool_result" for b in blocks):
            continue
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


def block(reason):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def add_context(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))
    sys.exit(0)


def deny_tool(reason):
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
    path = os.path.join(PROJECT_DIR, cfg["record_file"])
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
    """The working record as it is in the checkout; None when it cannot be read."""
    try:
        return open(os.path.join(PROJECT_DIR, cfg["record_file"]), encoding="utf-8").read()
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
        out.append({"name": name, "state": state,
                    "complete": any(w in low for w in COMPLETE_WORDS) and not any(w in low for w in ("incomplete", "not complete")),
                    "waiting": any(w in low for w in WAITING_WORDS) and not for_approval,
                    "queued": any(w in low for w in QUEUED_WORDS) or for_approval,
                    "plan": (PLAN_ROW.match(name).group("plan").strip() if PLAN_ROW.match(name) else None),
                    "blocked": (any(w in low for w in BLOCKED_WORDS) and not any(w in low for w in WAITING_WORDS)
                                and not for_approval),
                    "superseded": "superseded" in low and not any(w in low for w in COMPLETE_WORDS if w != "✅"),
                    # v3.1.24: a Check stage (confirming the work: merges, live check, device check) — labelled
                    # "(Check)" in its name, or a stage waiting on the user
                    "check": bool(CHECK_TAG.search(name)) or (any(w in low for w in WAITING_WORDS) and not for_approval),
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
            display += ("\nBuild is done; the rest is checking. If a check finds a problem, tell this session or "
                        "start a new one with the restart line from the record: it becomes a new Build row.")
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


def handoff_text(cfg, comp, after_build=False):
    """The hand-off the session does itself in one reply, so the user never has to ask for it."""
    branch = current_branch()
    rec = cfg["record_file"]
    return ("do the hand-off yourself in this reply; the user must not have to ask for it: "
            f"1) update '## Where we are' in {rec} (the plan name exactly as in the ledger, the newest Plan vN and its plan "
            "file path, the next stage, the restart line itself, what the next session must know — a few lines that point to plan files, "
            "commits and pull requests by path or number instead of copying them, with no keys or passwords), then "
            "commit and push "
            f"{rec} to {branch}; "
            "2) show the Completion lines: every row of the plan that is not complete — open, blocked, queued, "
            f"waiting, Build and Check — so done plus listed adds up ({comp.get('line', '')}); "
            "3) above the --- line, give this restart line in a code block, exactly: "
            f"`{restart_line(comp, branch) if not after_build else restart_after_build(comp, branch)}` — and in the "
            "'I need from you' line ask the user only for the next action that is theirs (a merge, a check), or "
            "nothing. Do not ask the user to open a new session: this session carries on; the restart line is kept "
            "for picking the work up later, if this session is ever closed.")


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
PLAN_TEMPLATE = """# Plan vN — <short plan name>

| Summary |
|---|
| What changes for you: what you will see or what will be different, in everyday words |
| What changed from the last version and why (first version: "First version") |
| What I need to do |

Changes in this version (from the second version on; the Rev number is the plan version — Plan v2 marks its changes
"🟩 Rev 2", Plan v9 marks "🟦 Rev 9"; squares cycle 🟦 1 · 🟩 2 · 🟧 3 · 🟪 4, then repeat; earlier changes are unmarked):
```diff
+ 🟩 Rev 2 — <line added or changed>
- 🟩 Rev 2 — <line removed>
```

<the plan itself, in everyday words, at most about 2 pages (6,000 characters); a changed section starts with its label, e.g. "🟩 Rev 2 — …">

Stages to finish
<n> stages: <x> build steps by Claude, then <y> checks (<what they are>)
1. <stage> · Claude · Build
2. <stage> · You · Check

Technical details: <file names, line numbers, commits, code, and any longer detail — only here>"""
