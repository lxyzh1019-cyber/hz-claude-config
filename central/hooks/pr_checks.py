#!/usr/bin/env python3
"""v3.3.7: wait once for a pull request's checks with GitHub REST, never `gh pr checks` (403 in a cloud session).
Usage: python3 pr_checks.py <pull request number> [--timeout <seconds, default 540>]
Reads the head commit of the pull request (repos/{owner}/{repo}/pulls/{n}), then its check runs
(repos/{owner}/{repo}/commits/{sha}/check-runs) every 20 s until all are done. Last line: 'checks: passed',
'checks: failed', 'checks: pending' or 'checks: unknown'. The PostToolUse check then makes the summary again."""
import os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import gh_repo, gh_rest, run_text  # noqa: E402


def state(repo, sha):
    d = gh_rest(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
    runs = (d or {}).get("check_runs") if isinstance(d, dict) else None
    s = gh_rest(f"repos/{repo}/commits/{sha}/status")      # review item 12: the older commit statuses count too
    sts = (s or {}).get("statuses") if isinstance(s, dict) else None
    if runs is None and sts is None:
        return "unknown", []
    runs, sts = runs or [], sts or []
    if not runs and not sts:
        return "none", []
    lines = [f"{r.get('name')}: {r.get('conclusion') or r.get('status')}" for r in runs] + \
            [f"{x.get('context')}: {x.get('state')}" for x in sts]
    if any(r.get("status") != "completed" for r in runs) or any(x.get("state") == "pending" for x in sts):
        return "pending", lines
    bad = [r for r in runs if r.get("conclusion") not in ("success", "neutral", "skipped")] + \
          [x for x in sts if x.get("state") in ("failure", "error")]
    return ("failed" if bad else "passed"), lines


def main(argv):
    num = next((a for i, a in enumerate(argv) if a.isdigit() and (i == 0 or argv[i - 1] != "--timeout")), None)
    try:
        limit = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 540
    except (IndexError, ValueError):
        limit = 540
    repo = gh_repo()
    if not repo:
        print("checks: unknown (no GitHub remote)")
        return 0
    sha = None
    if num:
        pr = gh_rest(f"repos/{repo}/pulls/{num}")
        sha = ((pr or {}).get("head") or {}).get("sha") if isinstance(pr, dict) else None
    sha = sha or run_text(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
    start = time.time(); end = start + limit
    while True:
        st, lines = state(repo, sha)
        if st in ("passed", "failed", "unknown") or time.time() >= end or (st == "none" and time.time() - start >= 60):
            break
        time.sleep(20)
    for l in lines:
        print(l)
    print(f"checks: {st} (commit {sha[:7]})")
    return 0   # review item 6: the result is the last line; a failed run must still reach the summary check


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
