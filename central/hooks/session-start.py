#!/usr/bin/env python3
"""SessionStart hook (run by the repo's .claude/hz-loader.py): inject the central rules, the version, branch,
where the worker instructions and skills are, per-repo file status, and hotspot alerts."""
import os, subprocess
from _common import (log, read_hook_input, load_config, add_context, PROJECT_DIR, RULES_PATH, SKILLS_DIR,
                     WORKER_PATH, hotspot_alerts, central_version, completion_summary)
from stubcheck import stub_status

data = read_hook_input()
cfg = load_config()
version = central_version()
try:
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_DIR,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5).stdout.strip() or "unknown"
except (OSError, subprocess.SubprocessError, UnicodeError):
    branch = "unknown"

parts = []
try:
    parts.append(open(RULES_PATH, encoding="utf-8").read())
    loaded = True
except OSError:
    loaded = False

note = os.environ.get("HZ_LOADER_NOTE", "")
facts = [f"[session-start] Rules v{version} loaded · branch: {branch}" + (f" · {note}" if note else "")
         if loaded else "[session-start] Central rules NOT loaded (rules file missing in cache). Stop and report."]
facts.append(f"Worker instructions: {WORKER_PATH} — include this path in every opus-worker or sonnet-worker delegation.")
facts.append(f"Central skills folder: {SKILLS_DIR} — when a skill is named, read its SKILL.md there.")
missing = [p for p in (cfg["features_file"], cfg["record_file"]) if not os.path.exists(os.path.join(PROJECT_DIR, p))]
facts.append("Missing per-repo files: " + (", ".join(missing) if missing else "none"))
try:
    if "<app or plan name>" in open(os.path.join(PROJECT_DIR, cfg["features_file"]), encoding="utf-8").read():
        facts.append(f"Note: {cfg['features_file']} is the unfilled template — fill it before the first implementation turn")
except OSError:
    pass
stub = stub_status(cfg, PROJECT_DIR)
setup_note = None
if stub.startswith("OUTDATED"):
    try:
        from stubupdate import update as _setup_update
        new_line, setup_note = _setup_update(cfg, PROJECT_DIR)
        if new_line:
            stub = new_line
    except Exception as e:  # never let the self-update break session start
        log("session-start", {"setup_update_error": repr(e)})
facts.append("[stub] " + stub)
if setup_note:
    facts.append(setup_note)
if os.path.exists(os.path.join(PROJECT_DIR, "tools", "build_manifest.py")) and cfg.get("update_notice"):
    facts.append("[update] " + cfg["update_notice"] + " Put this in the 'I need from you' line of your first reply.")
facts.append(f"Note: routing guard mode: {cfg.get('routing_guard_mode', 'observe')}")
facts += [f"[hotspot] {a}" for a in hotspot_alerts(cfg)]
comp = completion_summary(cfg)
if comp["total"] and comp["open"]:
    facts.append("[completion] " + comp["display"] + "\n— this branch's ledger rows; read the deliverable ledger before "
                 "claiming anything is done, and state these lines in your first reply.")
facts.append(f"Your first reply's very first line: 'Rules v{version} · {branch}'. Every final answer then opens with a "
             "quote block of three lines in everyday words, followed by a line with just ---:\n"
             "> 📌 **Result:** <status only: what works now or what I get, no requests>\n"
             "> 👉 **I need from you:** <one action, one short line, or nothing>\n"
             "> ➡️ **Next:** <what happens after>\n"
             "---\n"
             "Decisions go in a '❓ Decisions' list right under the --- line; technical detail below that. If the stub is "
             "outdated, say so in the 'I need from you' line. No running commentary between tool calls and no progress "
             "reports: dispatch workers in the foreground and wait; if asked for status, one line '⏳ Working on: …'. "
             "Present every Plan vN in plan mode (plan file + Approve); after approval copy it into plans/. Rules, hooks, worker instructions and skills come from "
             "hz-claude-config through .claude/hz-loader.py; never copy them into this repository.")
parts.append("\n".join(facts))
add_context("SessionStart", "\n\n".join(parts))
