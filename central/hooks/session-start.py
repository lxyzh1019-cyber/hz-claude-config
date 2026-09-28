#!/usr/bin/env python3
"""SessionStart hook (run by the repo's .claude/hz-loader.py): inject the central rules, the version, branch,
where the worker instructions and skills are, per-repo file status, and hotspot alerts."""
import os, subprocess
from _common import (read_hook_input, load_config, add_context, PROJECT_DIR, RULES_PATH, SKILLS_DIR,
                     WORKER_PATH, hotspot_alerts, central_version, completion_summary)

data = read_hook_input()
cfg = load_config()
version = central_version()
try:
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_DIR,
                            capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
except (OSError, subprocess.SubprocessError):
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
facts.append(f"Note: routing guard mode: {cfg.get('routing_guard_mode', 'observe')}")
facts += [f"[hotspot] {a}" for a in hotspot_alerts(cfg)]
comp = completion_summary(cfg)
if comp["total"] and comp["open"]:
    facts.append("[completion] " + comp["line"] + " — read the deliverable ledger before claiming anything is done; "
                 "state this line in your first reply.")
facts.append("State the rules version and branch in your first reply. Rules, hooks, worker instructions and skills "
             "come from hz-claude-config through .claude/hz-loader.py; never copy them into this repository.")
parts.append("\n".join(facts))
add_context("SessionStart", "\n\n".join(parts))
