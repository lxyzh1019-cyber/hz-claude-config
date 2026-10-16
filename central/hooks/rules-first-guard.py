#!/usr/bin/env python3
"""PreToolUse (every tool), v3.1.29: the session start no longer carries the rules (Claude Code cuts hook text over
10,000 characters to a 2,000-character preview), so the main session reads the rules file first. Until it does,
tools that change or run something are refused with the exact path; reading and searching stay allowed. Workers
(subagents) are never stopped: they have their own instructions. The session start clears the mark, so every new
start or /compact reads the rules again.
v3.3.3: steps that only read (Read, Grep, Glob, read-only shell commands such as git status, read-only MCP calls)
are never refused; only steps that change or run something wait for the rules."""
import json, os, sys
from _common import read_hook_input, load_config, deny_tool, log, STATE_DIR, RULES_PATH

if os.environ.get("HZ_RULES_FIRST_OFF"):   # test suite only: older tests run as if the rules were read
    sys.exit(0)
data = read_hook_input()
cfg = load_config()
if any(data.get(f) for f in (cfg.get("subagent_marker_fields") or ["agent_id"])):
    sys.exit(0)                       # a worker
if not os.path.exists(RULES_PATH):
    sys.exit(0)                       # nothing to read: session start already said "NOT loaded"
sid = str(data.get("session_id") or "")
from _common import sess_get, sess_set   # v3.2.7: one mark per session (two sessions in one folder blocked each other)
if sess_get("rules-read.json", sid):
    sys.exit(0)
tool = str(data.get("tool_name") or "")
inp = data.get("tool_input") or {}
path = str(inp.get("file_path") or inp.get("path") or "").replace("\\", "/").lower()
own = RULES_PATH.replace("\\", "/").lower()
if tool == "Read" and (path == own or ("hz-rules" in path and path.endswith("rules/claude-rules.md"))):
    sess_set("rules-read.json", sid, True)
    log("rules-first-guard", {"rules_read": True})
    sys.exit(0)
if tool in set(cfg.get("rules_first_allowed_tools") or ["Read", "Glob", "Grep", "LS", "TodoWrite", "NotebookRead",
                                                        "WebFetch", "WebSearch", "BashOutput", "ToolSearch",
                                                        "ListMcpResourcesTool", "ReadMcpResourceTool"]):
    sys.exit(0)
# v3.3.3: steps that only read never wait for the rules; only steps that change something do (fix 6, 15 Oct:
# the first refused step of a session was a read such as git status).
import re as _re
if tool.startswith("mcp__") and _re.match(r"(get|list|search|read|fetch|view|find)_", tool.rsplit("__", 1)[-1]):
    sys.exit(0)


def _read_only_bash(cmd):
    """True when every part of a shell command only reads (git status/log/diff, ls, cat, gh pr view...)."""
    c = _re.sub(r"\d?>\s*/dev/null|2>&1", "", cmd)
    if _re.search(r">|`|\$\(|\btee\b|<<", c):
        return False
    plain = {"ls", "pwd", "cat", "head", "tail", "wc", "grep", "rg", "echo", "which", "type", "stat",
             "du", "df", "cd", "true", "printf", "basename", "dirname", "realpath"}
    git_ro = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-remote", "describe", "blame",
              "shortlog", "rev-list", "cat-file", "grep"}
    gh_ro = {("pr", "view"), ("pr", "list"), ("pr", "status"), ("pr", "checks"), ("pr", "diff"), ("run", "list"),
             ("run", "view"), ("issue", "view"), ("issue", "list"), ("repo", "view"), ("auth", "status")}
    for part in _re.split(r"&&|\|\||;|\||\n", c):
        w = part.split()
        if not w:
            continue
        head = w[0]
        if head == "rg" and any(x.startswith("--pre") for x in w):
            return False
        if head in plain:
            continue
        if head == "find" and not any(x.startswith(("-delete", "-exec", "-ok", "-fprint", "-fls")) for x in w):
            continue
        if head == "git":
            if any(x.startswith("--output") for x in w):
                return False
            a = w[1:]
            while a and a[0].startswith("-"):           # git -C <folder>, git --no-pager ...
                a = a[2:] if a[0] in ("-C", "-c") else a[1:]
            sub = a[0] if a else ""
            if sub in git_ro:
                continue
            if sub == "branch" and all(x in ("-a", "-r", "-v", "-vv", "--list", "--show-current", "--all",
                                             "--remotes", "--no-color") for x in a[1:]):
                continue
            if sub == "remote" and a[1:] in ([], ["-v"]):
                continue
            if sub == "reflog" and a[1:2] in ([], ["show"]):
                continue
            if sub in ("stash", "worktree", "tag") and a[1:2] in (["list"], ["-l"]):
                continue
            if sub == "config" and len(a) > 1 and a[1] in ("--get", "--list", "-l", "--get-all"):
                continue
            return False
        if head == "gh" and len(w) > 2 and (w[1], w[2]) in gh_ro:
            continue
        return False
    return True


if tool == "Bash" and _read_only_bash(str(inp.get("command") or "")):
    sys.exit(0)
# v3.2.15: Read, Grep and Glob no longer start the checks (12% of a session's time on Windows), so the Read of the rules
# is found in the session file at the next checked step.
try:
    from _common import read_transcript as _rt
    for _r in _rt(data.get("transcript_path")):
        for _b in ((_r.get("message") or {}).get("content") or []) if isinstance((_r.get("message") or {}).get("content"), list) else []:
            if isinstance(_b, dict) and _b.get("type") == "tool_use" and _b.get("name") == "Read":
                _p = str((_b.get("input") or {}).get("file_path") or "").replace("\\", "/").lower()
                if _p == own or ("hz-rules" in _p and _p.endswith("rules/claude-rules.md")):
                    sess_set("rules-read.json", sid, True)
                    sys.exit(0)
except SystemExit:
    raise
except Exception:
    pass
log("rules-first-guard", {"refused": tool})
deny_tool(f"Read the working rules first, with the Read tool: {RULES_PATH} — then do this step again. "
          f"Steps that only read (git status, ls, Read, Grep) need no wait.")
