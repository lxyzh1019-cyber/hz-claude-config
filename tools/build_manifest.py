#!/usr/bin/env python3
"""Rebuild central/MANIFEST.txt — the list of files the loader fetches.
Usage: python3 tools/build_manifest.py 3.1.1   (the new version; run after every change under central/)"""
import os, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "central")
version = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: build_manifest.py <version>")
files = []
for d, _, names in os.walk(root):
    for n in names:
        rel = os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/")
        if rel != "MANIFEST.txt" and "__pycache__" not in rel:
            files.append(rel)
with open(os.path.join(root, "MANIFEST.txt"), "w", encoding="utf-8") as f:
    f.write(f"version: {version}\n" + "\n".join(sorted(files)) + "\n")
print(f"MANIFEST.txt: version {version}, {len(files)} files")
