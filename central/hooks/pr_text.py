#!/usr/bin/env python3
"""v3.3.7 (pieces 4 and 9): the check writes into the pull request text itself, with GitHub REST (`gh api`), never
`gh pr` (403 in a cloud session). Each part has its own markers, so the session's own text and other parts stay:
<!-- hz-report --> … <!-- /hz-report -->   the report (summary, measured part, approved plan)
<!-- hz-scorecard --> … <!-- /hz-scorecard -->   the scorecard lines (tools/scorecard.py checks)
When REST fails (no gh, no GitHub remote), the text is saved in .claude/state/pr-body.md and the caller tells the
session once to write it with the GitHub tool."""
import json, os, re

from _common import gh_repo, gh_rest, STATE_DIR, log


def pr_number(x):
    s = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x
    m = re.search(r"/pull/(\d+)", s) or re.search(r'"number"\s*:\s*(\d+)', s)
    return int(m.group(1)) if m else None


def set_section(body, name, content):
    a, b = f"<!-- hz-{name} -->", f"<!-- /hz-{name} -->"
    block = f"{a}\n{str(content or '').strip()}\n{b}"
    body = body or ""
    i, j = body.find(a), body.find(b)
    if i >= 0 and j > i:
        return body[:i] + block + body[j + len(b):]
    return (body.rstrip() + "\n\n" if body.strip() else "") + block + "\n"


def update(number, sections):
    """Write the sections into pull request #number. Returns (ok, why)."""
    repo = gh_repo()
    if not number:
        return False, "no pull request number"
    body = None
    if repo:
        pr = gh_rest(f"repos/{repo}/pulls/{number}")
        if isinstance(pr, dict):
            body = pr.get("body") or ""
    if body is None:
        _save(number, sections)
        return False, "the pull request could not be read with GitHub REST"
    new = body
    for k, v in sections.items():
        new = set_section(new, k, v)
    if new == body:
        return True, "unchanged"
    r = gh_rest(f"repos/{repo}/pulls/{number}", method="PATCH", input_json={"body": new})
    if not isinstance(r, dict):
        _save(number, sections)
        return False, "the GitHub REST write failed"
    log("pr_text", {"updated": number, "parts": list(sections)})
    return True, "written"


def _save(number, sections):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, "pr-body.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- pull request #{number} -->\n")
            for k, v in sections.items():
                f.write(set_section("", k, v) + "\n")
    except OSError:
        pass


def saved_path():
    return os.path.join(STATE_DIR, "pr-body.md").replace("\\", "/")
