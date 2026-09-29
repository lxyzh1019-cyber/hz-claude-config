#!/usr/bin/env python3
"""Compare this repository's stub (files Claude Code reads before any hook runs) with what the current central
version expects. Returns one plain-language line for the session-start facts."""
import json, os


def stub_status(cfg, project_dir):
    exp = cfg.get("stub_expect") or {}
    missing = []
    for path, name in (exp.get("files") or {}).items():
        if not os.path.exists(os.path.join(project_dir, path)):
            missing.append(name)
    try:
        s = json.load(open(os.path.join(project_dir, ".claude", "settings.json"), encoding="utf-8"))
    except (OSError, ValueError):
        s = None
    if s is None:
        missing.append("settings file")
    else:
        for key, (want, name) in (exp.get("settings") or {}).items():
            if s.get(key) != want:
                missing.append(name)
        hooks = s.get("hooks") or {}
        for event, name in (exp.get("events") or {}).items():
            cmds = " ".join(h.get("command", "") for g in hooks.get(event, []) for h in g.get("hooks", []))
            if "dispatch.py" not in cmds:
                missing.append(name)
        allow = (s.get("permissions") or {}).get("allow") or []
        for rule, name in (exp.get("allow") or {}).items():
            if rule not in allow:
                missing.append(name)
    try:
        pointer = open(os.path.join(project_dir, "CLAUDE.md"), encoding="utf-8").read().lower()
    except OSError:
        pointer = ""
    for needle, name in (exp.get("pointer_text") or {}).items():
        if needle.lower() not in pointer:
            missing.append(name)
    want = exp.get("version", "?")
    if not missing:
        return f"current (matches v{want})"
    return ("OUTDATED — this repository still has an older stub; missing: " + ", ".join(missing) +
            f". Features that need it do not work here yet. Fix: run Step B from the hz-claude-config README in this "
            "repository, in default permission mode (not auto), and merge its pull request.")
