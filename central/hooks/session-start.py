#!/usr/bin/env python3
"""SessionStart hook (run by the repo's .claude/hz-loader.py): inject the central rules, the version, branch,
where the worker instructions and skills are, per-repo file status, and hotspot alerts."""
import json, os, subprocess
from _common import (log, read_hook_input, load_config, add_context, PROJECT_DIR, RULES_PATH, SKILLS_DIR, PLAN_TEMPLATE,
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
    if "were updated on disk just now" in setup_note:
        try:
            import json as _json
            os.makedirs(os.path.join(PROJECT_DIR, ".claude", "state"), exist_ok=True)
            with open(os.path.join(PROJECT_DIR, ".claude", "state", "setup-pending.json"), "w", encoding="utf-8") as f:
                _json.dump({"branch": "hz-setup-update-" + str((cfg.get("stub_expect") or {}).get("version", "latest"))}, f)
        except OSError:
            pass
if os.path.exists(os.path.join(PROJECT_DIR, "tools", "build_manifest.py")) and cfg.get("update_notice"):
    facts.append("[update] " + cfg["update_notice"] + " Put this in the 'I need from you' line of your first reply.")
facts.append(f"Note: routing guard mode: {cfg.get('routing_guard_mode', 'observe')}")
facts += [f"[hotspot] {a}" for a in hotspot_alerts(cfg)]
comp = completion_summary(cfg)
if comp["total"] and comp["open"]:
    facts.append("[completion] " + comp["display"] + "\n— this branch's ledger rows; read the deliverable ledger before "
                 "claiming anything is done, and state these lines in your first reply.")
try:
    from _common import edmonton_time
    facts.append(f"Times for me are in Edmonton time: it is now {edmonton_time()}. Convert any UTC time "
                 "(MDT = UTC-6 from the second Sunday of March, MST = UTC-7 from the first Sunday of November); a "
                 "finished answer that shows a UTC time is sent back.")
except Exception:
    pass
facts.append("The 📌 Result line starts with where the work stands (Ready to merge / Waiting on your decision / Still "
             "being worked on). While I'm still discussing or deciding, make no code changes, files or pull requests; "
             "when you think I'm ready, ask me first and build only after my yes.")
facts.append("Pushing the work branch (never main) to GitHub is always fine without asking — merging stays mine. "
             "While a design is still being shaped, the plan version does not move: keep agreed points in a '## Design "
             "decisions' section of the working record ('- [agreed] <point> — search: <phrase>'), answer with short "
             "change notes, and when it seems settled ask me first, then write one new plan version with every agreed "
             "point. The Rev number is the plan version.")
facts.append("Find all, fix all, check once: when tests, checks or a review find problems, first run the whole test suite or check and list every problem; then fix them together in one pass (or hand the whole list to one worker); then run everything again once. Never find one, fix one, re-run, find the next — each round re-reads everything. Fix one by one only when one fix clearly changes the cause of the others, and say so.")
facts.append("Plans: write the first version in this shape, so the plan check passes it the first time "
             "(squares only on Rev labels; no 'Changes in this version' block in a first version):\n" + PLAN_TEMPLATE)
facts.append("The version line is shown to me in the notice after your reply: do not write a 'Rules v…' line. "
             "Every final answer ends with a "
             "quote block of three lines in everyday words, after a line with just ---, and nothing after it:\n"
             "---\n"
             "> 📌 **Result:** <status only: what works now or what I get, no requests>\n"
             "> 👉 **I need from you:** <one action, one short line, or nothing>\n"
             "> ➡️ **Next:** <what happens after>\n"
             "Above the --- line, in this order: the technical detail, the Completion lines if required, the "
             "validation line, then a '❓ Decisions' list (one line each with your recommendation). A change from what I "
             "approved (plan, prototype, design: a colour, a size, a layout, a feature) is a question in that list, "
             "never news in the details; no colour codes or sizes in the closing lines. If the stub is "
             "outdated, say so in the 'I need from you' line. No running commentary between tool calls and no progress "
             "reports: dispatch workers in the foreground and wait; if asked for status, one line '⏳ Working on: …'. "
             "Present every Plan vN in plan mode (plan file + Approve); the plan file is written into plans/ in this "
             "repository — commit the approved one with the work and delete drafts that were not approved. Rules, "
             "hooks, worker instructions and skills come from "
             "hz-claude-config through .claude/hz-loader.py; never copy them into this repository.")
parts.append("\n".join(facts))
# v3.1.23: no systemMessage here — the desktop app does not show session-start notices; stats.py shows the
# version line in the Stop notice instead.
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(parts)}}))
