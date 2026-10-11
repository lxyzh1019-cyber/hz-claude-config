#!/usr/bin/env python3
"""Content-ledger coverage gate.

Usage:
  python coverage_gate.py ARTIFACT            # ledger embedded in ARTIFACT (line starting 'CONTENT LEDGER')
  python coverage_gate.py ARTIFACT LEDGER     # ledger in a separate file

Ledger lines look like:  L07 Label text | phrase one; phrase two
Every phrase must appear in the artifact text. Exit code 1 if any is missing
or a ledger number is repeated; 2 for a usage problem.

Before matching, the artifact text has HTML comments removed (the ledger and
commented-out old text never count as a match), HTML entities decoded (.htm/.html),
and runs of spaces and line breaks made into one space (none between two CJK
characters). Phrases get the same spacing rule.
"""
import html
import re
import sys

CJK = r"\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def ledger_lines(text):
    return [l for l in text.splitlines() if re.match(r"\s*L\d+\s", l) and "|" in l]


def even_spaces(text):
    text = re.sub(r"\s+", " ", text)
    return re.sub(rf"(?<=[{CJK}]) (?=[{CJK}])", "", text)


def main():
    if len(sys.argv) not in (2, 3) or sys.argv[1].startswith("-"):
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    artifact = read(path)
    if len(sys.argv) == 3:
        lines = ledger_lines(read(sys.argv[2]))
        searched = artifact
    else:
        start = artifact.find("CONTENT LEDGER")
        if start < 0:
            print("No 'CONTENT LEDGER' block found in the artifact.")
            sys.exit(2)
        end = artifact.find("-->", start)
        end = len(artifact) if end < 0 else end + 3
        block_start = artifact.rfind("<!--", 0, start)
        block_start = start if block_start < 0 else block_start
        lines = ledger_lines(artifact[start:end])
        searched = artifact[:block_start] + artifact[end:]   # the ledger never counts as a match
    if not lines:
        print("Ledger is empty.")
        sys.exit(2)
    searched = re.sub(r"<!--.*?-->", " ", searched, flags=re.S)   # commented-out text never counts
    if path.lower().endswith((".html", ".htm")):
        searched = html.unescape(searched)
    searched = even_spaces(searched)
    ids = [l.split()[0] for l in lines]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    missing = []
    for line in lines:
        lid = line.split()[0]
        for phrase in [p.strip() for p in line.split("|", 1)[1].split(";") if p.strip()]:
            if even_spaces(phrase) not in searched:
                missing.append(f'{lid}: "{phrase}"')
    print(f"Ledger items: {len(lines)}  Missing: {len(missing)}")
    for m in missing:
        print("  MISSING", m)
    for r in repeated:
        print("  REPEATED NUMBER", r)
    sys.exit(1 if missing or repeated else 0)


if __name__ == "__main__":
    main()
