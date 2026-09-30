#!/usr/bin/env python3
"""Rebuild central/MANIFEST.txt — the list of files the loader fetches.
Usage: python3 tools/build_manifest.py 3.1.1   (the new version; run after every change under central/)"""
import os, shutil, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "central")
# the stub files every app repository updates itself from (session-start → stubupdate.py) travel with the rules
stub_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stub")
stub_dst = os.path.join(root, "stub-files")
os.makedirs(stub_dst, exist_ok=True)
for n in ("settings.json", "opus-worker.md", "sonnet-worker.md", "hz-loader.py", "CLAUDE-pointer.md",
          "merge_settings.py", "v2-known-files.txt"):
    shutil.copyfile(os.path.join(stub_src, n), os.path.join(stub_dst, n))
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
