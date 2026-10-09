#!/usr/bin/env python3
"""Compare this repository's stub (files Claude Code reads before any hook runs) with what the current central
version expects. Returns one plain-language line for the session-start facts."""
import json, os


def _reader_disk(project_dir):
    def read(rel):
        try:
            return open(os.path.join(project_dir, rel), encoding="utf-8").read()
        except OSError:
            return None
    return read


def _reader_main(project_dir):
    """v3.2.1: the same files as they are on origin/main (last fetch). A work branch made before the setup merge
    has the old files, though the repository's main already has the new ones (real case: Weekly-Planner, 8 Oct)."""
    import subprocess

    def read(rel):
        try:
            r = subprocess.run(["git", "show", "origin/main:" + rel.replace("\\", "/")], cwd=project_dir,
                               capture_output=True, text=True, encoding="utf-8", timeout=10)
            return r.stdout if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None
    return read


def stub_status(cfg, project_dir):
    missing = _missing(cfg, project_dir, _reader_disk(project_dir))
    want = (cfg.get("stub_expect") or {}).get("version", "?")
    if missing and not _missing(cfg, project_dir, _reader_main(project_dir)):
        import subprocess as _sp7
        try:
            _br = _sp7.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir, capture_output=True, text=True,
                           encoding="utf-8", timeout=5).stdout.strip()
        except (OSError, _sp7.SubprocessError):
            _br = ""
        _gone = [os.path.basename(f)[:-3] for f in (cfg.get("stub_expect") or {}).get("files", {})
                 if f.startswith(".claude/agents/") and not os.path.isfile(os.path.join(project_dir, f))]
        if _br in ("main", "master"):   # v3.2.7: this PC's main is behind GitHub (Figure-Skate 8 Oct: no planner here)
            return (f"current on GitHub main (v{want}), but this PC's main is behind"
                    + (" — helpers missing here: " + ", ".join(_gone) if _gone else "")
                    + ". In your first reply's 'I need from you' line, ask me to click Pull origin in GitHub Desktop and "
                    "start a new session. Until then call no missing helper; plans are written in the main session")
        return (f"current on main (v{want}); this branch was made before the setup merge and gets it when main is "
                "merged in — nothing to do")
    if not missing:
        return f"current (matches v{want})"
    return ("OUTDATED — this repository has an older setup. Missing: " + "; ".join(missing) +
            ". Features that need it do not work here yet. Fix: run Step B from the hz-claude-config README in this "
            "repository, in default permission mode (not auto). Then merge its pull request.")


def _missing(cfg, project_dir, read):
    exp = cfg.get("stub_expect") or {}
    missing = []
    for path, name in (exp.get("files") or {}).items():
        if read(path) is None:
            missing.append(name)
    for path, pair in (exp.get("file_text") or {}).items():
        pairs = pair if pair and isinstance(pair[0], (list, tuple)) else [pair]   # v3.2.1: several needles per file
        text = read(path) or ""
        for needle, name in pairs:
            if needle not in text:
                missing.append(name)
    try:
        s = json.loads(read(".claude/settings.json") or "")
    except ValueError:
        s = None
    if s is None:
        missing.append("settings file")
    else:
        for key, (want, name) in (exp.get("settings") or {}).items():
            if s.get(key) != want:
                missing.append(name)
        for key, name in (exp.get("settings_absent") or {}).items():
            if key in s:
                missing.append(name)
        hooks = s.get("hooks") or {}
        for event, name in (exp.get("events") or {}).items():
            cmds = " ".join(h.get("command", "") for g in hooks.get(event, []) for h in g.get("hooks", []))
            if "dispatch.py" not in cmds:
                missing.append(name)
        for event, pair in (exp.get("event_matchers") or {}).items():
            needle, name = pair
            matchers = " ".join(g.get("matcher", "") for g in hooks.get(event.strip(), []))
            if needle not in matchers:
                missing.append(name)
        allow = (s.get("permissions") or {}).get("allow") or []
        for rule, name in (exp.get("allow") or {}).items():
            if rule not in allow:
                missing.append(name)
    pointer = (read("CLAUDE.md") or "").lower()
    for needle, name in (exp.get("pointer_text") or {}).items():
        if needle.lower() not in pointer:
            missing.append(name)
    return missing

