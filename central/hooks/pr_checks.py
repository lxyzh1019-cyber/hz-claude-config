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
    if runs is None:
        return "unknown", []
    if not runs:
        return "pending", []
    lines = [f"{r.get('name')}: {r.get('conclusion') or r.get('status')}" for r in runs]
    if any(r.get("status") != "completed" for r in runs):
        return "pending", lines
    bad = [r for r in runs if r.get("conclusion") not in ("success", "neutral", "skipped")]
    return ("failed" if bad else "passed"), lines


def main(argv):
    num = next((a for a in argv if a.isdigit()), None)
    limit = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv else 540
    repo = gh_repo()
    if not repo:
        print("checks: unknown (no GitHub remote)")
        return 1
    sha = None
    if num:
        pr = gh_rest(f"repos/{repo}/pulls/{num}")
        sha = ((pr or {}).get("head") or {}).get("sha") if isinstance(pr, dict) else None
    sha = sha or run_text(["git", "rev-parse", "HEAD"], timeout=10).stdout.strip()
    end = time.time() + limit
    while True:
        st, lines = state(repo, sha)
        if st in ("passed", "failed") or time.time() >= end:
            break
        time.sleep(20)
    for l in lines:
        print(l)
    print(f"checks: {st} (commit {sha[:7]})")
    return 0 if st == "passed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
