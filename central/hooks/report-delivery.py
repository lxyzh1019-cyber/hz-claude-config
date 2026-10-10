#!/usr/bin/env python3
"""Stop, v3.2.10: a report in docs/reports/ is done only when I get it.
Weekly-Planner 9 Oct: checkpoint report 1 was written at 12:35 MDT and committed, but no reply named it and the file
was never sent, so I never saw it. When a report file is new or changed since the last delivered one, the final reply
must name the file and carry its Quick read, and the file goes to me with SendUserFile. One reminder per prompt; the
file then counts as delivered, so a session that cannot comply never loops. The first run in a repository only
records the reports that already exist."""
import json, os, re, sys, glob
from _common import (read_hook_input, load_config, read_transcript, last_turn, last_assistant_text, is_progress_report,
                     block, use_round, log, work_dir, STATE_DIR)

data = read_hook_input()
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records) or ""
if not text or is_progress_report(text, records, cfg):
    sys.exit(0)
folder = os.path.join(work_dir(), "docs", "reports")
now = {}
for f in glob.glob(os.path.join(folder, "*.md")):
    try:
        now[os.path.basename(f)] = int(os.path.getmtime(f))
    except OSError:
        pass
path = os.path.join(STATE_DIR, "reports-delivered.json")
try:
    seen = json.load(open(path, encoding="utf-8"))
except (OSError, ValueError):
    seen = None


def save(d):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        json.dump(d, open(path, "w", encoding="utf-8"))
    except OSError:
        pass


if seen is None:
    save(now)
    sys.exit(0)
fresh = [n for n, t in sorted(now.items()) if seen.get(n) != t]
if not fresh:
    sys.exit(0)
sent = " ".join(json.dumps((b.get("input") or {}), ensure_ascii=False)
                for r in last_turn(records) if r.get("type") == "assistant"
                for b in ((r.get("message") or {}).get("content") or []) if isinstance((r.get("message") or {}).get("content"), list)
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "SendUserFile")
# the file name and its Quick read in the reply are required; SendUserFile is asked for but not required, because
# not every Claude Code surface has it
missing = [n for n in fresh if not (n in text + " " + sent and re.search(r"quick read", text, re.I))]
delivered = [n for n in fresh if n not in missing]
for n in delivered:
    seen[n] = now[n]
if not missing:
    save(seen)
    sys.exit(0)
r = use_round("report-delivery", data.get("session_id"), 1)
for n in missing:          # never twice for the same file version
    seen[n] = now[n]
save(seen)
if (r is None and data.get("stop_hook_active")) or (r is not None and not r[1]):
    sys.exit(0)
log("report-delivery", {"missing": missing})
block("The report " + ", ".join(f"docs/reports/{n}" for n in missing) + " is written but I have not got it. Send the "
      "file to me with SendUserFile (load it with ToolSearch). In your reply give its Quick read and the file name. Do "
      "not repeat the rest of your report.")
