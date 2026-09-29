"""Shared helpers for the .claude/hooks scripts. No third-party imports."""
import json
import os
import re
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
    "progress_line_pattern": r"Progress:\s*\d+\s+of\s+\d+\s+done\s*·\s*Running:\s*\S.*$",
    "validation_line_pattern": r"Confidence:\s*(High|Medium|Low)\s*·\s*Status:\s*(Proposed|Checked|Validated(\s*—\s*\S.*)?|Uncertain)\s*$",
    "design_triggers": ["redesign", "architecture", "data model", "schema", "migration", "sync layer", "firestore rules", "shared state", "regression", "keeps breaking", "again", "still broken", "refactor"],
    # planner suggestion (plan-gate): strong signals that a plan needs Fable rather than the Opus default
    "fable_planner_signals": ["root cause", "why does", "why is", "investigate", "across all", "every repo", "all repos", "all apps",
                              "migrate everything", "whole codebase", "multi-day", "end to end", "end-to-end"],
    "fable_planner_min_triggers": 2,
    # completion guard (Stop): auto-fix rounds per turn before a final report may stand with open ledger items
    "auto_fix_max_rounds": 3,
    "pause_phrases": ["stop here", "pause here", "that's enough for now", "that is enough for now", "leave the rest", "stop for now"],
    "completion_line_pattern": r"Completion:\s*(\d+)\s+of\s+(\d+)",
    # switchboard (dispatch.py): which check scripts run for which hook event; "tools" = regex on tool_name
    "dispatch": {},
    # plain top of every final answer (validation-line.py) and first-reply version line
    "report_top_labels": ["Result:", "I need from you:", "Next:"],
    # what a current stub looks like (session-start.py); names are shown to the user in plain words
    "stub_expect": {
        "version": "3.1.13",
        "files": {".claude/agents/sonnet-worker.md": "Sonnet worker"},
        "settings": {"model": ["opus", "Opus session model"], "advisorModel": ["fable", "Fable advisor"]},
        "events": {"UserPromptSubmit": "prompt checks", "PreToolUse": "safety checks before commands and edits",
                   "PostToolUse": "checks after commands and edits", "Stop": "report checks (completion, top lines)",
                   "SubagentStop": "worker report checks"},
        "allow": {"Bash(git commit:*)": "commit permission", "Bash(gh pr ready:*)": "ready-PR permission"},
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
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def log(name, payload):
    """Append a JSON line to .claude/state/<name>.jsonl (best effort)."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, f"{name}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


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
    """An interim report while workers run: ends with the Progress line, and a worker was actually dispatched."""
    return bool(re.search(cfg["progress_line_pattern"], text or "")) and worker_dispatched(records)


# ---- Deliverable ledger (WORKING_RECORD.md) ------------------------------------------------------
def _record_table(cfg, heading_regex):
    """Rows of the first table under the heading matching heading_regex; [] if absent."""
    path = os.path.join(PROJECT_DIR, cfg["record_file"])
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
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
BLOCKED_WORDS = ("blocked", "cannot", "won't fix", "wont fix", "dropped", "superseded", "deferred")


def deliverable_ledger(cfg):
    """List of {name, state, blocked, complete, evidence} from the deliverable ledger; template rows skipped."""
    rows = _record_table(cfg, r"deliverable")
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
        out.append({"name": name, "state": state,
                    "complete": any(w in low for w in COMPLETE_WORDS) and not any(w in low for w in ("incomplete", "not complete")),
                    "blocked": any(w in low for w in BLOCKED_WORDS),
                    "evidence": (r[ei] if ei is not None and ei < len(r) else "").strip()})
    return out


def completion_summary(cfg):
    """{total, complete, blocked, open (names), no_evidence (names), pct, line}; total 0 when no ledger."""
    items = deliverable_ledger(cfg)
    total = len(items)
    done = [i for i in items if i["complete"]]
    blocked = [i for i in items if i["blocked"] and not i["complete"]]
    open_ = [i["name"] for i in items if not i["complete"] and not i["blocked"]]
    no_ev = [i["name"] for i in done if not i["evidence"]]
    pct = round(100 * len(done) / total) if total else 0
    line = f"Completion: {len(done)} of {total} done ({pct}%)"
    if blocked:
        line += " · Blocked: " + ", ".join(i["name"] for i in blocked)
    if open_:
        line += " · Open: " + ", ".join(open_)
    return {"total": total, "complete": len(done), "blocked": len(blocked), "open": open_, "no_evidence": no_ev,
            "pct": pct, "line": line}
