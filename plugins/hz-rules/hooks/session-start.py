#!/usr/bin/env python3
"""SessionStart hook: inject the central rules (unless already loaded as ~/.claude/CLAUDE.md), the version,
branch, per-repo file status, and hotspot alerts."""
import os, subprocess, sys
from _common import (read_hook_input, load_config, add_context, PROJECT_DIR, RULES_PATH, RULES_MARKER,
                     hotspot_alerts, plugin_version)

read_hook_input()
cfg = load_config()
version = plugin_version()

def native_rules_loaded():
    try:
        with open(os.path.join(os.path.expanduser("~"), ".claude", "CLAUDE.md"), encoding="utf-8") as f:
            return RULES_MARKER in f.read()
    except OSError:
        return False

try:
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_DIR,
                            capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
except (OSError, subprocess.SubprocessError):
    branch = "unknown"

parts = []
if native_rules_loaded():
    source = "loaded as ~/.claude/CLAUDE.md"
else:
    try:
        parts.append(open(RULES_PATH, encoding="utf-8").read())
        source = "injected by the hz-rules session-start hook"
    except OSError:
        source = "MISSING — rules file not found in the plugin"

facts = [f"[session-start] Rules v{version} loaded ({source}) · branch: {branch}"]
missing = [p for p in (cfg["features_file"], cfg["record_file"]) if not os.path.exists(os.path.join(PROJECT_DIR, p))]
facts.append("Missing per-repo files: " + (", ".join(missing) if missing else "none"))
try:
    if "<app or plan name>" in open(os.path.join(PROJECT_DIR, cfg["features_file"]), encoding="utf-8").read():
        facts.append(f"Note: {cfg['features_file']} is the unfilled template — fill it before the first implementation turn")
except OSError:
    pass
facts.append(f"Note: routing guard mode: {cfg.get('routing_guard_mode', 'observe')}")
facts += [f"[hotspot] {a}" for a in hotspot_alerts(cfg)]
facts.append("State the rules version and branch in your first reply. Rules, hooks, agent and skills are installed "
             "centrally from hz-claude-config; never copy them into this repository.")
parts.append("\n".join(facts))
add_context("SessionStart", "\n\n".join(parts))
