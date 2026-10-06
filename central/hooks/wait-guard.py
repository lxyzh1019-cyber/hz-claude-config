#!/usr/bin/env python3
"""PreToolUse on Bash (v3.1.30), main session and workers alike:
1. No waiting commands: no sleep over 5 seconds, no loops that wait (while/until with sleep), no tail -f, no watch.
   Claude Code tells the session when a worker or a background command finishes. In the Weekly-Planner PR 118 session
   the main session started two "Wait for the PR 4 fix-pass worker" commands.
2. A command run in the background starts with a time limit of at most 30 minutes (timeout 1800 ...): in the same
   session a background script was still "running" after 11 h 49 m."""
import re, sys
from _common import read_hook_input, load_config, deny_tool, log

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
cmd = str(inp.get("command") or "")
limit = int(cfg.get("background_max_seconds", 1800))
max_sleep = float(cfg.get("max_sleep_seconds", 5))
UNIT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def seconds(tok):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", tok or "")
    return float(m.group(1)) * UNIT[m.group(2)] if m else None


body = re.sub(r"<<-?\s*'?(\w+)'?.*?^\s*\1\s*$", "", cmd, flags=re.S | re.M)   # ignore here-document text
problems = []
for m in re.finditer(r"(?:^|[;&|(\n]\s*|\bdo\s+|\bthen\s+)sleep\s+(\S+)", body):
    s = seconds(m.group(1))
    if s is None or s > max_sleep:
        problems.append(f"sleep {m.group(1)}")
if re.search(r"\b(while|until)\b[^\n]*?;\s*do\b[\s\S]*?\bsleep\b", body) or \
   re.search(r"\b(while|until)\b[\s\S]*?\bdo\b[\s\S]*?\bsleep\b[\s\S]*?\bdone\b", body):
    problems.append("a loop that waits")
if re.search(r"(?:^|[;&|\n]\s*)tail\s+(-\S*\s+)*-[fF]\b", body) or re.search(r"\btail\s+--follow\b", body):
    problems.append("tail -f")
if re.search(r"(?:^|[;&|\n]\s*)watch\s", body):
    problems.append("watch")
if problems:
    log("wait-guard", {"refused": problems[:3]})
    deny_tool("No waiting commands (" + ", ".join(sorted(set(problems))[:3]) + "). Claude Code tells you when a worker "
              "or a background command finishes: end the step and continue when that notice comes. Run tests and "
              "scripts in the foreground and let them finish.")
if inp.get("run_in_background"):
    # the limit may follow a cd or settings: "cd app && SMOKE=... timeout 1800 npm test" (real runs start with cd)
    m = re.search(r"(?:^|&&|;|\n|\s)timeout\s+(?:-\S+\s+)*(\S+)\s+\S", body)
    s = seconds(m.group(1)) if m else None
    if s is None or s > limit:
        log("wait-guard", {"refused": "background without limit"})
        deny_tool(f"A background command needs a time limit of at most {limit // 60} minutes: start it with "
                  f"'timeout {limit} ' (for example: cd <folder> && timeout {limit} npm test). A background script ran 11 h 49 m "
                  "in one session.")
sys.exit(0)
