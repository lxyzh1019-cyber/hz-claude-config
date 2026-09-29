#!/usr/bin/env python3
"""PreToolUse hook (Bash and the GitHub pull-request tools): block a commit on main/master and any push to
main/master, without prompting, and block opening a pull request as a draft — on the command line (gh pr create
--draft) and through the GitHub tool (create/update_pull_request with draft set to true). PRs open ready for
review; the user merges on GitHub. Feature-branch commits and pushes pass through untouched. A hook "deny" is
honoured in auto mode."""
import re, shlex, subprocess, sys
from _common import read_hook_input, deny_tool, PROJECT_DIR

PROTECTED = {"main", "master"}
PR_TOOL = re.compile(r"^mcp__.*(create|update)_pull_request$")
data = read_hook_input()
tool = data.get("tool_name") or ""
tool_input = data.get("tool_input") or data.get("input") or {}
if tool.startswith("mcp__"):
    if PR_TOOL.match(tool) and tool_input.get("draft") is True:
        deny_tool(f"git-guard: pull requests open ready for review, not as drafts. Call {tool} again with draft set "
                  "to false, or leave the draft field out — create it ready for review. If a draft pull request "
                  "already exists, mark it ready for review instead.")
    sys.exit(0)
cmd = (tool_input.get("command") or "")
if "git" not in cmd and "gh" not in cmd:
    sys.exit(0)


def current_branch():
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_DIR,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def git_args(segment):
    try:
        toks = shlex.split(segment)
    except ValueError:
        toks = segment.split()
    while toks and re.match(r"^\w+=", toks[0]):  # leading VAR=value
        toks = toks[1:]
    if not toks or toks[0] != "git":
        return None
    toks = toks[1:]
    while toks and toks[0] in ("-C", "-c"):  # git -C dir / -c key=val
        toks = toks[2:]
    return toks


def target_is_protected(ref):
    dst = ref.split(":")[-1].lstrip("+")
    dst = dst[len("refs/heads/"):] if dst.startswith("refs/heads/") else dst
    return dst in PROTECTED


def is_draft_pr(segment):
    try:
        toks = shlex.split(segment)
    except ValueError:
        toks = segment.split()
    while toks and re.match(r"^\w+=", toks[0]):
        toks = toks[1:]
    return toks[:3] == ["gh", "pr", "create"] and any(t in ("--draft", "-d") or t.startswith("--draft=") for t in toks[3:])


branch = None
for segment in re.split(r"&&|\|\||;|\n", cmd):
    if is_draft_pr(segment.strip()):
        deny_tool("git-guard: pull requests open ready for review, not as drafts. Run the same gh pr create without "
                  "--draft/-d. If a draft PR already exists, mark it ready with gh pr ready <number>.")
    args = git_args(segment.strip())
    if not args:
        continue
    sub, rest = args[0], args[1:]
    if sub == "commit":
        branch = branch if branch is not None else current_branch()
        if branch in PROTECTED:
            deny_tool(f"git-guard: no commits on {branch}. Create a branch first (git switch -c claude/<topic>), "
                      "commit there, push it and open a pull request; the user merges on GitHub.")
    elif sub == "push":
        if any(a in ("--all", "--mirror") for a in rest):
            deny_tool("git-guard: --all/--mirror could push main. Push the working branch only.")
        positional = [a for a in rest if not a.startswith("-")]
        refspecs = positional[1:]  # first positional is the remote
        if any(target_is_protected(r) for r in refspecs):
            deny_tool("git-guard: pushing to main is not allowed. Push the working branch and open a pull request; "
                      "the user merges on GitHub.")
        if not refspecs:
            branch = branch if branch is not None else current_branch()
            if branch in PROTECTED:
                deny_tool(f"git-guard: this would push {branch}. Switch to a working branch first.")
sys.exit(0)
