#!/usr/bin/env python3
"""SessionStart hook (run by the repo's .claude/hz-loader.py): inject the central rules, the version, branch,
where the worker instructions and skills are, per-repo file status, and hotspot alerts."""
import json, os, re, subprocess
from _common import (log, read_hook_input, load_config, add_context, PROJECT_DIR, STATE_DIR, RULES_PATH, SKILLS_DIR, 
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
# v3.1.29: Claude Code saves hook text over 10,000 characters to a file and shows only a 2,000-character preview, so
# the rules (about 25,000) are no longer sent here. The short facts are sent, and the session reads the rules file
# itself before any other tool (rules-first-guard.py).
loaded = os.path.exists(RULES_PATH)
try:   # v3.2.7: clear only this session's mark; another session in the same folder keeps its own
    import json as _j7
    from _common import sess_del
    _sid7 = (data.get("session_id") if isinstance(data, dict) else "") if "data" in globals() else ""
    if not _sid7:
        _sid7 = str(_j7.loads(os.environ.get("HZ_HOOK_INPUT", "{}") or "{}").get("session_id") or "")
    sess_del("rules-read.json", _sid7)
except Exception:
    pass

note = os.environ.get("HZ_LOADER_NOTE", "")
facts = [f"[session-start] Rules v{version} loaded · branch: {branch}" + (f" · {note}" if note else "")
         if loaded else "[session-start] Central rules NOT loaded (rules file missing in cache). Stop and report."]
_agents = os.path.dirname(WORKER_PATH)
# v3.2.0: role files. Each helper reads its own file; the main session only names the path in the hand-over.
_FULL = bool(os.environ.get("HZ_FULL_RULES"))
# v3.3.4 (P2): default first lists only the reviewer. The main session builds (16 Oct: the local run handed the whole
# build to a worker that read the code again: 16 min and 3.5 M tokens; the cloud run built in the main session).
if not _FULL:
    facts.append("Role file for the one review pass (name it in the hand-over; the reviewer reads it): "
                 f"{os.path.join(_agents, 'reviewer-instructions.md')}. You build in this session. A helper builds only "
                 "parts that run side by side on separate files, named in the plan.")
else:
  facts.append("Role files. Name the path in each hand-over. The helper reads it, not you.\n"
             f"- workers: {WORKER_PATH}\n"
             f"- planner: {os.path.join(_agents, 'planner-instructions.md')}\n"
             f"- explorer: {os.path.join(_agents, 'explorer-instructions.md')}\n"
             f"- reviewer: {os.path.join(_agents, 'reviewer-instructions.md')}\n"
             f"- compare (when screens or figures change): {os.path.join(_agents, 'compare-instructions.md')}\n"
             f"- feature list conversion (once per app, when I ask): {os.path.join(_agents, 'conversion-instructions.md')}")
facts.append(f"Skills: {SKILLS_DIR}. When a skill is named, read its SKILL.md there.")
# v3.2.0: the test rule of this repository — a test map, and a full run of 5 minutes or less
try:
    _feat = open(os.path.join(PROJECT_DIR, cfg["features_file"]), encoding="utf-8").read()
except (OSError, KeyError):
    _feat = ""
try:
    _ts = json.load(open(os.path.join(STATE_DIR, "test-speed.json"), encoding="utf-8"))
except (OSError, ValueError):
    _ts = {}
_lim = float(cfg.get("full_test_max_minutes", 5))
_split = re.search(r"(?im)^\s*-?\s*Test speed:\s*full run\s*([\d.]+)\s*min", _feat)
if _FULL and _feat and not re.search(r"(?im)^\s*-?\s*Tests:\s*\S", _feat):   # v3.3.4 (P8): default first asks nothing
    facts.append("[test rule] FEATURES.md has no test map yet. In the next build stage, add 'Tests: <area or files> → "
                 "<tests it needs>' lines under ## References, so a fix runs only its tests.")
# v3.2.0: references first — an app with screens but no picture references cannot be checked against them
import glob as _glob
_has_screens = bool(_glob.glob(os.path.join(PROJECT_DIR, "*.html")) or _glob.glob(os.path.join(PROJECT_DIR, "*", "*.html")))
_refs = _glob.glob(os.path.join(PROJECT_DIR, cfg.get("reference_dir", "tests/reference"), "*.png"))
if _FULL and _has_screens and not _refs:
    facts.append("[references] This app has screens but no picture references yet "
                 f"({cfg.get('reference_dir', 'tests/reference')}). Before any stage that changes a screen, add a stage "
                 "that makes them, as the compare instructions say. Then every screen change is checked against them.")
if (float(_ts.get("latest_full_minutes", _ts.get("slowest_full_minutes")) or 0) > _lim or _ts.get("stopped_by_limit")) and not (_split and float(_split.group(1)) <= _lim):
    facts.append(f"[test rule] A full test run here took {_ts.get('slowest_full_minutes')} minutes"
                 + (" and was stopped by the time limit" if _ts.get("stopped_by_limit") else "") + f"; the aim is "
                 f"{int(_lim)} or less. No full local runs until the suite is split (fast loop here, full suite on "
                 "GitHub). If the plan has no stage yet to split it, add it as the next Rev, before other build stages.")
missing = [p for p in (cfg["features_file"], cfg["record_file"]) if not os.path.exists(os.path.join(PROJECT_DIR, p))]
if _FULL:   # v3.3.4 (P8): 16 Oct, the local run filled both (+97 lines), the cloud run asked about them instead
    facts.append("Missing files in this repository: " + (", ".join(missing) if missing else "none"))
    try:
        if "<app or plan name>" in open(os.path.join(PROJECT_DIR, cfg["features_file"]), encoding="utf-8").read():
            facts.append(f"Note: {cfg['features_file']} is still the template. Fill it before the first build step.")
    except OSError:
        pass
# v3.3.4 (P10): plan files stay out of git without a commit (Claude Code's cloud end check sent the 16 Oct run back
# for the untracked plan file). A plan that spans sessions is still committed with git add -f.
try:
    _gd = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=PROJECT_DIR, capture_output=True, text=True,
                         timeout=10).stdout.strip()
    if _gd:
        _ex = os.path.join(PROJECT_DIR if not os.path.isabs(_gd) else "", _gd, "info", "exclude")
        os.makedirs(os.path.dirname(_ex), exist_ok=True)
        _cur = open(_ex, encoding="utf-8").read() if os.path.exists(_ex) else ""
        # v3.3.6 (G5): scratch files of browser checks and their pictures live in .claude/state/checks/; run #15 was
        # sent back once by Claude Code's cloud end check for files left in the folder
        _add = [x for x in ("plans/", ".claude/state/") if not re.search(r"(?m)^/?" + re.escape(x) + r"\s*$", _cur)]
        if _add:
            with open(_ex, "a", encoding="utf-8") as _h:
                _h.write(("" if _cur.endswith("\n") or not _cur else "\n") + "\n".join(_add) + "\n")
        os.makedirs(os.path.join(PROJECT_DIR, ".claude", "state", "checks"), exist_ok=True)
except (OSError, subprocess.SubprocessError):
    pass
# v3.3.6 (B1): an automatic setup update that was stopped can leave a locked worktree record in Temp whose folder is
# gone (Weekly-Planner, 16 Oct: hz-setup-9f0foxji). Unlock and prune such records; nothing on disk is touched.
try:
    _wl = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=PROJECT_DIR, capture_output=True, text=True,
                         timeout=10).stdout
    _pr = False
    for _blk in _wl.split("\n\n"):
        _wp = re.search(r"(?m)^worktree (.+)$", _blk)
        if _wp and "hz-setup-" in _wp.group(1) and not os.path.exists(_wp.group(1)):
            subprocess.run(["git", "worktree", "unlock", _wp.group(1)], cwd=PROJECT_DIR, capture_output=True, timeout=10)
            _pr = True
    if _pr:
        subprocess.run(["git", "worktree", "prune"], cwd=PROJECT_DIR, capture_output=True, timeout=10)
except (OSError, subprocess.SubprocessError):
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
    import re as _re8
    _m8 = _re8.search(r"gh pr (?:create --base main --head|edit) (hz-setup-update-[\w.-]+)", setup_note)
    if _m8:   # v3.2.8: the end-of-reply check sees that the session opened or linked the setup pull request
        try:
            import json as _j8
            os.makedirs(os.path.join(PROJECT_DIR, ".claude", "state"), exist_ok=True)
            _j8.dump({"branch": _m8.group(1), "session": str(data.get("session_id") or "")},
                     open(os.path.join(PROJECT_DIR, ".claude", "state", "setup-pr.json"), "w", encoding="utf-8"))
        except OSError:
            pass
    if "were updated on disk just now" in setup_note:
        try:
            import json as _json
            os.makedirs(os.path.join(PROJECT_DIR, ".claude", "state"), exist_ok=True)
            with open(os.path.join(PROJECT_DIR, ".claude", "state", "setup-pending.json"), "w", encoding="utf-8") as f:
                import re as _re5
                _bm = _re5.search(r"git switch -c (hz-setup-update-[\w.-]+)", setup_note)   # v3.2.4: the name may end in -2
                _json.dump({"branch": _bm.group(1) if _bm else "hz-setup-update-" +
                            str((cfg.get("stub_expect") or {}).get("version", "latest"))}, f)
        except OSError:
            pass
if os.path.exists(os.path.join(PROJECT_DIR, "tools", "build_manifest.py")) and cfg.get("update_notice"):
    facts.append("[update] " + cfg["update_notice"] + " Say this in one sentence in your first reply. Put it in the 'I need from you' line only if it asks me to do something.")
facts.append(f"Note: routing guard mode: {cfg.get('routing_guard_mode', 'observe')}")
facts += [f"[hotspot] {a}" for a in hotspot_alerts(cfg)]
comp = completion_summary(cfg)
if comp["total"] and comp["open"]:
    facts.append("[completion] " + comp["display"] + "\nThese are the rows of this branch. Read the deliverable ledger "
                 "before you say anything is done. Show these lines in your first reply.")
try:
    from _common import edmonton_time
    facts.append(f"Times for me are in Edmonton time. It is now {edmonton_time()}. Change any UTC time: MDT is UTC-6 "
                 "from the second Sunday of March, MST is UTC-7 from the first Sunday of November. A finished answer "
                 "with a UTC time gets a saved fix.")
except Exception:
    pass
# v3.2.0: short rules for this session in ASD-STE100-lite. The formats come from formats.py only.
facts.append("While I discuss or decide, make no code changes, files or pull requests. When you think I am ready, "
             "ask me first. Build only after my yes.")
facts.append("You can push the work branch (never main) without asking. Merging is mine.")
facts.append("While we shape a design, keep each agreed point in '## Design decisions' of the working record "
             "('- [agreed] <point> — search: <phrase>'). Answer with short change notes. When it seems settled, ask "
             "me. Then write one plan with every agreed point.")
facts.append("Find all, fix all, check once. Run the whole check and list every problem. Fix them together. Then run "
             "everything one time.")
facts.append(f"End the status line of every reply with ' · Rules v{version}' (Confidence: … · Status: … · Rules "
             f"v{version}). It is where I see the rules version. If the setup is old, say so in the 'I need from you' line.")
facts.append("A change from what I approved (plan, prototype, design) is a question in the '❓ Decisions' list. Add "
             "a link to a page that shows prototype and build side by side.")
facts.append("Show every Plan vN in plan mode. Commit the approved plan file only for work that spans sessions; a "
             "one-pull-request job keeps its plan in the pull request text (v3.3.3).")
facts.append("Rules, checks, helper files and skills come from hz-claude-config through .claude/hz-loader.py. Never "
             "copy them into this repository.")
from formats import session_formats
facts.append(session_formats())
if loaded:
    facts.append(f"FIRST, before any other tool or reply: read the working rules with the Read tool: {RULES_PATH}. "
                 "They are not in this message. Other tools wait until you read them.")
text = "\n".join(facts)
LIMIT = int(cfg.get("session_start_max_chars", 9500))
if len(text) > LIMIT:   # never let Claude Code cut this text: move the rest into a file read together with the rules
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        extra = os.path.join(STATE_DIR, "session-facts.md")
        with open(extra, "w", encoding="utf-8") as f:
            f.write(text)
        head = text[:LIMIT - 400].rsplit("\n", 1)[0]
        text = (head + f"\n… the rest of these session facts is in {extra} — read it with the rules, first."
                + (f"\nFIRST, before any other tool or reply: read the full working rules with the Read tool: "
                   f"{RULES_PATH}" if loaded else ""))
    except OSError:
        pass
    log("session-start", {"facts_chars": len("\n".join(facts)), "moved_to_file": True})
parts.append(text)
# v3.1.23: no systemMessage here — the desktop app does not show session-start notices; stats.py shows the
# version line in the Stop notice instead.
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(parts)}}))
