#!/usr/bin/env python3
"""Rebuild central/MANIFEST.txt — the list of files the loader fetches.
Usage: python3 tools/build_manifest.py 3.1.1   (the new version; run after every change under central/)"""
import os, shutil, sys
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "central")
# the stub files every app repository updates itself from (session-start → stubupdate.py) travel with the rules
stub_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stub")
stub_dst = os.path.join(root, "stub-files")
os.makedirs(stub_dst, exist_ok=True)
# v3.2.4: every published helper file stays "known", so a later change is updated and never skipped as "local edits".
# The copy about to be replaced is the last published one: add its hash to the known list (additive, never removes).
import hashlib
_known = os.path.join(stub_src, "v2-known-files.txt")
_have = set()
for _l in open(_known, encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#"):
        _have.add(_l.split()[0])
_add = []
for n in ("opus-worker.md", "sonnet-worker.md", "reviewer.md", "reviewer-light.md", "explore.md", "planner.md", "planner-opus.md"):
    _old = os.path.join(stub_dst, n)
    if os.path.isfile(_old):
        _h = hashlib.sha256(open(_old, encoding="utf-8").read().replace("\r\n", "\n").encode("utf-8")).hexdigest()
        _cur = hashlib.sha256(open(os.path.join(stub_src, n), encoding="utf-8").read().replace("\r\n", "\n")
                              .encode("utf-8")).hexdigest()
        if _h not in _have and _h != _cur:
            _add.append(f"{_h}  # {n}, published before this build")
if _add:
    with open(_known, "a", encoding="utf-8") as _f:
        _f.write("\n".join(_add) + "\n")
    print(f"known helper-file versions added: {len(_add)}")
for n in ("settings.json", "opus-worker.md", "sonnet-worker.md", "reviewer.md", "reviewer-light.md", "explore.md", "planner.md", "planner-opus.md", "hz-loader.py",
          "CLAUDE-pointer.md",
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
