#!/usr/bin/env python3
"""Revision gate: the new build keeps every feature and every open problem of its base.

Usage:
  python revision_gate.py NEW BASE

NEW and BASE are folders (a skill or a repo). Each may hold a revision record:
references/revision-record.md, revision-record.md or docs/revision-record.md.
Checks:
  1 base     - "Built on" in NEW equals "Version" in BASE (no record in BASE = first record).
  2 features - every F-line ID of BASE is in NEW (or named under "Removed"), and
               every phrase of NEW is found in NEW's files (record file excluded).
  3 problems - every P-line ID open in BASE is open in NEW or moved to Fixed with "proof:".
Exit 0 = PASS, 1 = FAIL, 2 = usage problem.
"""
import os, re, sys

NAMES = ("references/revision-record.md", "revision-record.md", "docs/revision-record.md")
TEXT = (".md", ".py", ".txt", ".json", ".html", ".js", ".css", ".yml", ".yaml", ".sh")


def find(folder):
    for n in NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            return p
    return None


def parse(path):
    r = {"version": None, "built": None, "F": {}, "P": {}, "X": {}, "removed": ""}
    if not path:
        return r
    sec = ""
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"(Version|Built on):\s*(\S+)", line)
        if m:
            r["version" if m.group(1) == "Version" else "built"] = m.group(2)
            continue
        if line.startswith("## "):
            sec = line[3:].lower()
            continue
        if sec.startswith("removed"):
            r["removed"] += line + "\n"
            continue
        m = re.match(r"([FPX])(\d+)\s+(.*)$", line)
        if m:
            k, i, rest = m.group(1), m.group(1) + m.group(2), m.group(3)
            if k == "F":
                label, _, ph = rest.partition("|")
                r["F"][i] = (label.strip(), [p.strip() for p in ph.split(";") if p.strip()])
            elif k == "P":
                r["P"][i] = rest
            else:
                r["X"][i] = rest
    return r


def corpus(folder, skip):
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in files:
            p = os.path.join(root, f)
            if os.path.abspath(p) == os.path.abspath(skip or "") or not f.endswith(TEXT):
                continue
            try:
                out.append(open(p, encoding="utf-8", errors="ignore").read())
            except OSError:
                pass
    return "\n".join(out)


def main():
    if len(sys.argv) != 3 or sys.argv[1].startswith("-"):
        print(__doc__)
        return 2
    new_dir, base_dir = sys.argv[1], sys.argv[2]
    nrec_p, brec_p = find(new_dir), find(base_dir)
    if not nrec_p:
        print(f"FAIL no revision record in {new_dir}")
        return 1
    n, b = parse(nrec_p), parse(brec_p)
    fails = []
    # 1 base
    if brec_p is None:
        print("base     first record: base has none")
    elif n["built"] != b["version"]:
        fails.append(f"base: new was built on {n['built']}, but the base is {b['version']}: rebuild on the base")
    elif n["version"] == b["version"]:
        fails.append(f"base: new Version {n['version']} is the same as the base; give the build a new version")
    else:
        print(f"base     ok: {b['version']} -> {n['version']}")
    # 2 features
    removed_ids = set(re.findall(r"^(F\d+)\s", n["removed"], re.M))
    for i, (label, _) in b["F"].items():
        if i not in n["F"] and i not in removed_ids:
            fails.append(f"feature {i} '{label}' is gone from the record and not under Removed")
    text = corpus(new_dir, nrec_p)
    miss = [(i, l, p) for i, (l, ps) in n["F"].items() for p in ps if p not in text]
    for i, l, p in miss:
        fails.append(f"feature {i} '{l}': phrase not found: {p}")
    print(f"features {len(n['F']) - len({m[0] for m in miss})}/{len(n['F'])} present")
    # 3 problems
    for i, t in b["P"].items():
        if i in n["P"]:
            continue
        fixed = [x for x in n["X"].values() if t.split("|")[0].strip()[:40] in x]
        if not fixed:
            fails.append(f"problem {i} dropped: {t.split('|')[0].strip()}")
        elif "proof:" not in fixed[0]:
            fails.append(f"problem {i} moved to Fixed without proof")
    print(f"problems open {len(n['P'])} · fixed {len(n['X'])} · base open {len(b['P'])}")
    for f in fails:
        print("FAIL", f)
    print("REVISION GATE: " + ("FAIL" if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
