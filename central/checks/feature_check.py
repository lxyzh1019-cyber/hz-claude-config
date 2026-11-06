#!/usr/bin/env python3
"""v3.3.7 (piece 8, D4 = B): the feature check, run in an app's GitHub test run on each pull request.
It reads three things: the files the pull request changes (git diff against the base), the feature map in FEATURES.md,
and the pull request text. It never reads the plan.

The map: each feature line ends with "— files: <files> — test: <test name>", for example
  - Lake panel — files: js/lake-sheet.js, css/sheet.css — test: test_lake_sheet
A red ✗ (exit 1) for each feature whose file changed when:
  - its line names no test ("test:" empty or "none"), or
  - the named test is not in the repository, or
  - the feature is missing from the pull request's impact table (a table row in the pull request text naming it).
FEATURES.md with no map yet: a notice and a pass.

The step in the app's test workflow (on pull_request):
  - run: |
      curl -fsSL https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/central/checks/feature_check.py -o "$RUNNER_TEMP/feature_check.py"
      python3 "$RUNNER_TEMP/feature_check.py" --base "origin/${{ github.base_ref }}"
  (actions/checkout with fetch-depth: 0, so the base is there.)
Usage: feature_check.py [--base <ref>] [--head <ref>] [--pr-body <file>] [--repo <folder>]
The pull request text comes from --pr-body, else the GitHub event file ($GITHUB_EVENT_PATH)."""
import json, os, re, subprocess, sys

MAP = re.compile(r"^\s*[-*]\s*(?P<name>.+?)\s+[—–-]{1,2}\s*files:\s*(?P<files>.+?)\s+[—–-]{1,2}\s*test:\s*(?P<test>.*?)\s*$", re.I)


def arg(name, default=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else ""


def features(text):
    out = []
    for line in (text or "").splitlines():
        m = MAP.match(line)
        if m:
            files = [f.strip().strip("`").replace("\\", "/") for f in re.split(r"[,;]\s*", m.group("files")) if f.strip()]
            test = m.group("test").strip().strip("`")
            out.append({"name": m.group("name").strip().strip("*`"), "files": files,
                        "test": "" if test.lower() in ("", "none", "-", "—", "no test") else test})
    return out


def test_exists(repo, test):
    """The named test is in the repository: a file with that name, or that name in a test file."""
    if not test:
        return False
    tracked = git(repo, "ls-files").splitlines()
    base = test.split("::")[0].split(" ")[0]
    if any(os.path.basename(f) == base or f == base or os.path.splitext(os.path.basename(f))[0] == base for f in tracked):
        return True
    hit = git(repo, "grep", "-l", "-F", test.split("::")[-1], "--", "*test*")
    return bool(hit.strip())


def in_impact_table(body, name):
    rows = [l for l in (body or "").splitlines() if l.strip().startswith("|")]
    n = re.sub(r"\s+", " ", name).strip().lower()
    return any(n in re.sub(r"\s+", " ", r).lower() for r in rows)


def main():
    repo = os.path.abspath(arg("--repo", "."))
    base = arg("--base") or ("origin/" + os.environ["GITHUB_BASE_REF"] if os.environ.get("GITHUB_BASE_REF") else "origin/main")
    head = arg("--head", "HEAD")
    try:
        feat_text = open(os.path.join(repo, "FEATURES.md"), encoding="utf-8").read()
    except OSError:
        feat_text = ""
    fmap = features(feat_text)
    if not fmap:
        print("::notice::feature check: FEATURES.md has no feature map yet (lines ending with "
              "'— files: <files> — test: <test name>'). Pass.")
        return 0
    rng = f"{base}...{head}" if "..." not in base and ".." not in base else base
    changed = [f.strip().replace("\\", "/") for f in git(repo, "diff", "--name-only", rng).splitlines() if f.strip()]
    if not changed and "..." in rng:
        changed = [f.strip() for f in git(repo, "diff", "--name-only", base, head).splitlines() if f.strip()]
    body = ""
    if arg("--pr-body"):
        body = open(arg("--pr-body"), encoding="utf-8").read()
    elif os.environ.get("GITHUB_EVENT_PATH"):
        try:
            body = (json.load(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8")).get("pull_request") or {}).get("body") or ""
        except (OSError, ValueError):
            body = ""
    bad, ok = [], []
    for f in fmap:
        hit = [c for c in changed if any(c == x or c.startswith(x.rstrip("/") + "/") for x in f["files"])]
        if not hit:
            continue
        why = []
        if not f["test"]:
            why.append("its line names no test")
        elif not test_exists(repo, f["test"]):
            why.append(f"the test '{f['test']}' is not in the repository")
        if not in_impact_table(body, f["name"]):
            why.append("it is missing from the pull request's impact table")
        (bad if why else ok).append((f["name"], hit, why))
    for name, hit, why in ok:
        print(f"✓ {name} ({', '.join(hit)})")
    for name, hit, why in bad:
        print(f"✗ {name} ({', '.join(hit)}): " + "; ".join(why))
        print(f"::error::feature check: {name} changed ({', '.join(hit)}): " + "; ".join(why))
    print(f"feature check: {len(bad)} red, {len(ok)} green, {len(changed)} changed files")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
