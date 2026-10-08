#!/usr/bin/env python3
"""Self-update of an app repository's own setup files (the stub), run from session-start.

Claude Code reads .claude/settings.json and .claude/agents/*.md before any hook runs, so these files cannot be
fetched centrally the way the rules and checks are. Instead, when the stub check finds them outdated, this module
rewrites them on disk from the central copies in stub-files/ (which the loader downloads with the rules), and
session-start tells the session to commit them on their own branch and open a pull request for the user to merge.
- Never in hz-claude-config itself (its own setup files change through Step E).
- Never twice: if a setup branch with changes main lacks exists (on GitHub or locally), the session only reminds the user
  (v3.2.4: an empty or already merged branch does not count; the update then uses the next branch name).
- A worker file with local edits (not a published version) is left alone and reported."""
import hashlib, json, os, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STUB = os.path.normpath(os.path.join(HERE, "..", "stub-files"))


def _git(project_dir, *args, timeout=8):
    try:
        return subprocess.run(["git", *args], cwd=project_dir, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().replace("\r\n", "\n")
    except OSError:
        return None


def _write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _known_hashes():
    out = set()
    for line in (_read(os.path.join(STUB, "v2-known-files.txt")) or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0])
    return out


def _refresh_pointer(text, pointer):
    start = text.find("# Repository rules")
    marker = "Repository-specific files: `FEATURES.md` and `WORKING_RECORD.md`."
    end = text.find(marker, start) if start >= 0 else -1
    if start < 0 or end < 0:
        return text
    return text[:start] + pointer.rstrip("\n") + text[end + len(marker):]


def _hotspot_columns(text):
    """Add 'Regressions caused' and 'Workarounds/exceptions' after 'Recurrences' in an old-layout hotspot table,
    with 0 in every row. Leaves the text unchanged if the table is not exactly the old five-column layout."""
    import re
    lines = text.split("\n")
    try:
        i = next(k for k, l in enumerate(lines) if re.match(r"#+\s*Hotspot counter", l, re.I))
    except StopIteration:
        return text
    out, k = list(lines), i + 1
    while k < len(lines) and not lines[k].startswith("#"):
        l = lines[k]
        if l.strip().startswith("|"):
            cells = re.split(r"(?<!\\)\|", l.strip())[1:-1]
            if len(cells) != 5:
                return text
            if "Recurrences" in cells[2]:
                cells[3:3] = [" Regressions caused ", " Workarounds/exceptions "]
            elif "Regressions caused" in l:
                return text
            elif set("".join(cells)) <= set("-: "):
                cells[3:3] = ["---", "---"]
            else:
                cells[3:3] = [" 0 ", " 0 "]
            out[k] = "|" + "|".join(cells) + "|"
        k += 1
    return "\n".join(out)


def update(cfg, project_dir):
    """Returns (stub_line, instruction or None). Called only when the stub is outdated."""
    if os.path.exists(os.path.join(project_dir, "tools", "build_manifest.py")):
        return None, None                                   # hz-claude-config itself
    if not os.path.isdir(STUB) or not os.path.isdir(os.path.join(project_dir, ".git")):
        return None, None
    if "hz-loader.py" not in (_read(os.path.join(project_dir, "CLAUDE.md")) or ""):
        return None, None                                   # not installed through the stub: installer's job
    version = (cfg.get("stub_expect") or {}).get("version", "latest")
    # v3.2.4: a branch counts as waiting only when it holds setup changes main lacks (an empty or merged branch does
    # not); then the update goes on a new branch name (-2, -3, ...). Nothing is deleted.
    from _common import setup_update_target
    kind, branch = setup_update_target(project_dir, version)
    if kind == "unpushed":   # v3.2.5: committed on this PC, never pushed: there is no pull request to merge
        return ("committed on this PC but not pushed (branch " + branch + ")",
                f"[setup-update] This repository's setup update is committed on branch {branch} on this PC, but it was never "
                f"pushed, so no pull request exists. Before any other work: push the branch (`git push -u origin {branch}`), "
                "open a pull request ready for review, then switch back to the branch you started on. If the switch is "
                "refused, stop and tell me. In your first reply's 'I need from you' line, ask me to merge that pull request.")
    if kind == "waiting":
        return ("waiting for you to merge the setup update (branch " + branch + ")",
                f"[setup-update] This repository's setup update is already waiting in a pull request (branch {branch}). "
                "Do not make another one. In your first reply's 'I need from you' line, ask me to merge it.")

    changed, skipped = [], []
    known = _known_hashes()
    for name in ("opus-worker.md", "sonnet-worker.md", "reviewer.md", "explore.md", "planner.md", "planner-opus.md"):
        dst = os.path.join(project_dir, ".claude", "agents", name)
        new = _read(os.path.join(STUB, name))
        old = _read(dst)
        if new is None or old == new:
            continue
        if old is not None and hashlib.sha256(old.encode("utf-8")).hexdigest() not in known:
            skipped.append(f".claude/agents/{name} (has local edits)")
            continue
        _write(dst, new)
        changed.append(f".claude/agents/{name}")
    dst = os.path.join(project_dir, ".claude", "settings.json")
    old = _read(dst)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    tmp.write(old or "{}"); tmp.close()
    try:
        r = subprocess.run(["python3" if shutil.which("python3") else "python", os.path.join(STUB, "merge_settings.py"),
                            os.path.join(STUB, "settings.json"), tmp.name, "hz-loader.py"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        merged = _read(tmp.name) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        merged = None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    if merged and old is not None and json.loads(merged) != json.loads(old):
        _write(dst, merged)
        changed.append(".claude/settings.json")
    new = _read(os.path.join(STUB, "hz-loader.py"))
    dst = os.path.join(project_dir, ".claude", "hz-loader.py")
    if new and _read(dst) != new:
        _write(dst, new)
        changed.append(".claude/hz-loader.py")
    pointer = _read(os.path.join(STUB, "CLAUDE-pointer.md"))
    dst = os.path.join(project_dir, "CLAUDE.md")
    old = _read(dst)
    if pointer and old:
        upd = _refresh_pointer(old, pointer)
        if upd != old:
            _write(dst, upd)
            changed.append("CLAUDE.md")

    rec = os.path.join(project_dir, cfg.get("record_file", "WORKING_RECORD.md"))
    text = _read(rec)
    if text:
        upd = _hotspot_columns(text)
        if upd != text:
            _write(rec, upd)
            changed.append(cfg.get("record_file", "WORKING_RECORD.md") + " (hotspot table: two missing columns added, nothing removed)")

    if not changed:
        return None, ("[setup-update] This repository's setup files are out of date but could not be updated "
                      "automatically" + (": " + "; ".join(skipped) if skipped else "") + ". In the 'I need from you' "
                      "line, tell me that the chat about hz-claude-config needs to look at this repository.")
    files = " ".join(changed)
    note = (" Left unchanged: " + "; ".join(skipped) + " — say so in your report.") if skipped else ""
    return ("updated on disk just now; waiting for the pull request",
            f"[setup-update] This repository's own setup files were out of date and were updated on disk just now: "
            f"{files}.{note} Before any other work: run `git fetch origin main`, then `git switch -c {branch} "
            f"origin/main` (the updated files come along), commit exactly these files (names without the notes in brackets) with the message 'Setup update "
            f"(automatic, v{version})', push the branch, open a pull request ready for review, then switch back to the "
            "branch you started on. If the switch is refused, stop and tell me. In plan mode, present this first as a "
            "one-stage micro-plan. In your first reply's 'I need from you' line, ask me to merge that pull request; "
            "the new setup takes effect in the next session after the merge. Then continue with my request.")
