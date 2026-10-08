#!/usr/bin/env python3
"""Content-ledger coverage gate.

Usage:
  python coverage_gate.py ARTIFACT            # ledger embedded in ARTIFACT (line starting 'CONTENT LEDGER')
  python coverage_gate.py ARTIFACT LEDGER     # ledger in a separate file

Ledger lines look like:  L07 Label text | phrase one; phrase two
Every phrase must appear verbatim in the artifact text. Exit code 1 if any is missing.
"""
import re
import sys


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def ledger_lines(text):
    return [l for l in text.splitlines() if re.match(r"\s*L\d+\s", l) and "|" in l]


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(2)
    artifact = read(sys.argv[1])
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
    missing = []
    for line in lines:
        lid = line.split()[0]
        for phrase in [p.strip() for p in line.split("|", 1)[1].split(";") if p.strip()]:
            if phrase not in searched:
                missing.append(f'{lid}: "{phrase}"')
    print(f"Ledger items: {len(lines)}  Missing: {len(missing)}")
    for m in missing:
        print("  MISSING", m)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
