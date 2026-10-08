#!/usr/bin/env python3
"""PreToolUse hook (Bash and the GitHub pull-request tools): block a commit on main/master and any push to
main/master, without prompting, and block opening a pull request as a draft — on the command line (gh pr create
--draft) and through the GitHub tool (create_pull_request with draft set to true; v3.1.30: switching an open one
back to draft with update_pull_request is allowed). v3.1.30: a pull request opens last (pr_last_check). PRs open ready for
review; the user merges on GitHub. Feature-branch commits and pushes pass through untouched. A hook "deny" is
honoured in auto mode."""
import os, re, shlex, subprocess, sys
from _common import read_hook_input, deny_tool, PROJECT_DIR, read_transcript, pr_timeline, pr_branch_state

PROTECTED = {"main", "master"}
PR_TOOL = re.compile(r"^mcp__.*(create|update)_pull_request$")
data = read_hook_input()
tool = data.get("tool_name") or ""
tool_input = data.get("tool_input") or data.get("input") or {}


def pr_last_check():
    """v3.1.30: a pull request opens last — after every worker and reviewer has finished, and after a reviewer ran
    following the last build worker (it checks the tests, the picture comparison and the plan). In the Weekly-Planner
    PR 118 session the pull request opened before the picture comparison, which then found gaps, so a ready pull
    request sat on GitHub while a worker was still fixing it."""
    events, running = pr_timeline(read_transcript(data.get("transcript_path")))
    if running:
        deny_tool("git-guard: a worker or the reviewer is still running. Open the pull request last: after it "
                  "finishes and every check passes.")
    kinds = [k for k, _ in events]
    if "worker" in kinds:
        last_worker = max(i for i, k in enumerate(kinds) if k == "worker")
        if "reviewer" not in kinds[last_worker + 1:]:
            deny_tool("git-guard: open the pull request last. Send the reviewer first (moment: Before the pull "
                      "request) — it checks the tests and the picture and figure comparison against their "
                      "references, and every agreed point of the plan. Fix what it blocks, then open the pull request.")


SID = data.get("session_id")


def mark(state, branch=None):
    b = branch or current_branch()
    if b and b not in PROTECTED:
        pr_branch_state(SID, b, state)


if tool.startswith("mcp__"):
    if PR_TOOL.match(tool) and tool_input.get("draft") is True and "create_pull_request" in tool:
        deny_tool(f"git-guard: pull requests open ready for review, not as drafts. Call {tool} again with draft set "
                  "to false, or leave the draft field out — create it ready for review. (Switching an open pull "
                  "request back to draft while it is being fixed is allowed.)")
    if re.match(r"^mcp__.*create_pull_request$", tool):
        pr_last_check()
        mark("ready", str(tool_input.get("head") or "") or None)
    elif re.match(r"^mcp__.*update_pull_request$", tool) and "draft" in tool_input:
        mark("draft" if tool_input.get("draft") is True else "ready")
    sys.exit(0)
cmd = (tool_input.get("command") or "")
if "git" not in cmd and "gh" not in cmd:
    sys.exit(0)


def current_branch(where=None):
    """v3.2.0: the branch of the folder the command runs in (cd <dir> / git -C <dir>), so parallel worktrees work."""
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=where if where and os.path.isdir(where) else PROJECT_DIR,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError, UnicodeError):
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
where = None
for segment in re.split(r"&&|\|\||;|\n", cmd):
    _cd = re.match(r"^\s*cd\s+(\"[^\"]+\"|'[^']+'|\S+)\s*$", segment)
    if _cd:
        where, branch = os.path.join(PROJECT_DIR, _cd.group(1).strip("\"'")), None
        continue
    _gc = re.search(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)", segment)
    if _gc:
        where, branch = os.path.join(PROJECT_DIR, _gc.group(1).strip("\"'")), None
    if is_draft_pr(segment.strip()):
        deny_tool("git-guard: pull requests open ready for review, not as drafts. Run the same gh pr create without "
                  "--draft/-d. If a draft PR already exists, mark it ready with gh pr ready <number>.")
    if re.match(r"^(\w+=\S+\s+)*gh\s+pr\s+create\b", segment.strip()):
        pr_last_check()
        mark("ready")
    elif re.match(r"^(\w+=\S+\s+)*gh\s+pr\s+ready\b", segment.strip()):
        mark("draft" if "--undo" in segment else "ready")
    args = git_args(segment.strip())
    if not args:
        continue
    sub, rest = args[0], args[1:]
    if sub == "commit":
        branch = branch if branch is not None else current_branch(where)
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
            branch = branch if branch is not None else current_branch(where)
            if branch in PROTECTED:
                deny_tool(f"git-guard: this would push {branch}. Switch to a working branch first.")
sys.exit(0)
