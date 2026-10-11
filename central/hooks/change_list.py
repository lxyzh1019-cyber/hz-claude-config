#!/usr/bin/env python3
"""v3.2.15: the "what changed" list for one Part (owner, 11 Oct: "I have no idea what has been changed, added or
removed"). Usage: python3 change_list.py [base] (default origin/main). Prints a table per file: the line ranges added,
changed and removed (from git diff), and an empty "What" column the worker fills with one plain line per file. Goes
into the pull request description and the checkpoint report."""
import re, subprocess, sys

base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
out = subprocess.run(["git", "diff", "-U0", "--no-color", f"{base}...HEAD"], capture_output=True, text=True,
                     encoding="utf-8", errors="replace").stdout
files, cur = {}, None
for ln in out.splitlines():
    if ln.startswith("+++ "):
        cur = ln[6:] if ln.startswith("+++ b/") else None
        if cur:
            files.setdefault(cur, {"added": [], "changed": [], "removed": [], "new": False})
    elif ln.startswith("--- /dev/null") and cur is None:
        pass
    elif ln.startswith("@@") and cur:
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
        a, b, c, d = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
        rng = lambda s, n: f"{s}" if n == 1 else f"{s}–{s + n - 1}"
        if b == 0:
            files[cur]["added"].append(rng(c, d))
        elif d == 0:
            files[cur]["removed"].append("old " + rng(a, b))
        else:
            files[cur]["changed"].append(rng(c, d))
new = set(subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"], capture_output=True,
                         text=True).stdout.split())
gone = subprocess.run(["git", "diff", "--name-only", "--diff-filter=D", f"{base}...HEAD"], capture_output=True,
                      text=True).stdout.split()
print("| File | Lines | What |")
print("|---|---|---|")
for f, r in files.items():
    if f in new:
        lines = "new file"
    else:
        parts = [f"{k} {', '.join(v[:6])}{' …' if len(v) > 6 else ''}" for k, v in r.items() if isinstance(v, list) and v]
        lines = "; ".join(parts) or "—"
    print(f"| `{f}` | {lines} |  |")
for f in gone:
    print(f"| `{f}` | removed file |  |")
