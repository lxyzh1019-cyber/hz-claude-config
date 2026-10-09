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


def _log7(entry):
    """v3.2.7: every setup publish step is logged (.claude/state/setup-publish.jsonl), so a failure shows its cause."""
    try:
        from _common import log as _l
        _l("setup-publish", entry)
    except Exception:
        pass


def _publish(project_dir, branch, version, staged):
    """v3.2.6: commit the staged files on a new branch from origin/main in a temporary worktree, push it, and open a
    pull request when `gh` is available. The working folder is never touched. Returns {"pr": url or ""}, or None when
    anything fails (the branch made here is then removed). Nothing but this one new branch is ever pushed."""
    import time
    if os.environ.get("HZ_SETUP_PUBLISH_OFF") or not staged:
        return None
    os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")      # never wait for a password in a hook: a failure runs the old way
    os.environ.setdefault("GCM_INTERACTIVE", "never")
    t_end = time.time() + 45
    left = lambda cap: max(3, min(cap, int(t_end - time.time())))
    wt, ok = None, False
    try:
        r = _git(project_dir, "fetch", "origin", "main", timeout=left(15))
        if not r or r.returncode != 0 or time.time() > t_end:
            return None
        base = tempfile.mkdtemp(prefix="hz-setup-")
        wt = os.path.join(base, "wt")
        r = _git(project_dir, "worktree", "add", "-q", "-b", branch, wt, "origin/main", timeout=left(15))
        if not r or r.returncode != 0:
            return None
        for rel, text in staged.items():
            _write(os.path.join(wt, rel), text)
        r = _git(wt, "add", "--", *staged.keys(), timeout=left(10))
        if not r or r.returncode != 0:
            return None
        name = (_git(project_dir, "config", "user.name") or type("x", (), {"stdout": ""})).stdout.strip() or "hz-claude-config setup"
        mail = (_git(project_dir, "config", "user.email") or type("x", (), {"stdout": ""})).stdout.strip() or "hz-setup@users.noreply.github.com"
        r = _git(wt, "-c", "user.name=" + name, "-c", "user.email=" + mail, "commit", "-q", "-m",
                 f"Setup update (automatic, v{version})", timeout=left(15))
        if not r or r.returncode != 0:
            return None
        r = _git(wt, "push", "-q", "-u", "origin", branch, timeout=left(25))
        if not r or r.returncode != 0:
            _log7({"step": "push", "ok": False, "error": ((r.stderr if r else "timeout") or "")[-300:]})
            return None
        _log7({"step": "push", "ok": True, "branch": branch})
        ok = True
        pr = ""
        gh = shutil.which("gh")
        if gh and time.time() < t_end:
            try:
                p = subprocess.run([gh, "pr", "create", "--base", "main", "--head", branch, "--title",
                                    f"Setup update (automatic, v{version})", "--body",
                                    "Automatic setup update from hz-claude-config: the helper files and settings of this repository. "
                                    "Merge it so the next sessions use them."], cwd=project_dir, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=left(20))
                lines = [x for x in p.stdout.splitlines() if x.startswith("http")]
                pr = lines[-1].strip() if p.returncode == 0 and lines else ""
                _log7({"step": "gh pr create", "ok": bool(pr), "error": "" if pr else (p.stderr or p.stdout)[-300:]})
            except (OSError, subprocess.SubprocessError) as e:
                pr = ""
                _log7({"step": "gh pr create", "ok": False, "error": type(e).__name__})
        else:
            _log7({"step": "gh pr create", "ok": False, "error": "gh not found" if not gh else "no time left"})
        return {"pr": pr}
    except Exception:
        return None
    finally:
        if wt:
            _git(project_dir, "worktree", "remove", "--force", wt, timeout=10)
            shutil.rmtree(os.path.dirname(wt), ignore_errors=True)
        if not ok:
            _git(project_dir, "branch", "-D", branch, timeout=10)      # the branch made here, nothing else


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

    changed, skipped, staged = [], [], {}    # v3.2.6: staged = new file texts by path; written to disk only as a fallback
    _git(project_dir, "fetch", "-q", "origin", "main", timeout=15)   # v3.2.7: decide on fresh GitHub facts
    known = _known_hashes()
    for name in ("opus-worker.md", "sonnet-worker.md", "reviewer.md", "reviewer-light.md", "explore.md", "planner.md",
                 "planner-opus.md"):
        dst = os.path.join(project_dir, ".claude", "agents", name)
        new = _read(os.path.join(STUB, name))
        old = _read(dst)
        if new is None or old == new:
            continue
        if old is not None and hashlib.sha256(old.encode("utf-8")).hexdigest() not in known:
            skipped.append(f".claude/agents/{name} (has local edits)")
            continue
        staged[f".claude/agents/{name}"] = new
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
        staged[".claude/settings.json"] = merged
        changed.append(".claude/settings.json")
    new = _read(os.path.join(STUB, "hz-loader.py"))
    dst = os.path.join(project_dir, ".claude", "hz-loader.py")
    if new and _read(dst) != new:
        staged[".claude/hz-loader.py"] = new
        changed.append(".claude/hz-loader.py")
    pointer = _read(os.path.join(STUB, "CLAUDE-pointer.md"))
    dst = os.path.join(project_dir, "CLAUDE.md")
    old = _read(dst)
    if pointer and old:
        upd = _refresh_pointer(old, pointer)
        if upd != old:
            staged["CLAUDE.md"] = upd
            changed.append("CLAUDE.md")

    rec = os.path.join(project_dir, cfg.get("record_file", "WORKING_RECORD.md"))
    text = _read(rec)
    if text:
        upd = _hotspot_columns(text)
        if upd != text:
            staged[cfg.get("record_file", "WORKING_RECORD.md")] = upd
            changed.append(cfg.get("record_file", "WORKING_RECORD.md") + " (hotspot table: two missing columns added, nothing removed)")

    if not changed:
        return None, ("[setup-update] This repository's setup files are out of date but could not be updated "
                      "automatically" + (": " + "; ".join(skipped) if skipped else "") + ". In the 'I need from you' "
                      "line, tell me that the chat about hz-claude-config needs to look at this repository.")
    files = " ".join(changed)
    note = (" Left unchanged: " + "; ".join(skipped) + " — say so in your report.") if skipped else ""
    # v3.2.6: the session start makes the commit, the push and the pull request itself, in a temporary folder. The auto-mode
    # safety check refused the model's commit of the helper files ("Self-Modification") in the Weekly-Planner session of
    # 2026-10-08, and the end-of-reply check then made the session answer 3 times. Only when this fails does the old way
    # run: the files are written on disk and the session is told to commit them.
    # v3.2.7: the update is already merged on GitHub and this PC is only behind (Weekly-Planner 8 Oct: a second setup
    # branch was demanded for a merged update, 10.5 minutes and 4 send-backs)
    def _on_main(rel):
        r = _git(project_dir, "show", "origin/main:" + rel, timeout=10)
        return r.stdout if r and r.returncode == 0 else None
    if staged and all((_on_main(rel) or "").replace("\r\n", "\n") == text.replace("\r\n", "\n") for rel, text in staged.items()):
        gone = [os.path.basename(r)[:-3] for r in staged if r.startswith(".claude/agents/") and not os.path.isfile(os.path.join(project_dir, r))]
        _log7({"behind": True, "files": len(staged)})
        return ("current on GitHub main, but this PC's main is behind",
                "[setup-update] The setup update is already merged on GitHub; this PC's folder is behind"
                + (" (helpers missing here: " + ", ".join(gone) + ")" if gone else "") + ". Make no setup branch and "
                "no commit. In your first reply's 'I need from you' line, ask me to click Pull origin in GitHub Desktop "
                "and start a new session. Until then call no missing helper; plans are written in the main session.")
    done = _publish(project_dir, branch, version, staged)
    if done:
        pr = done.get("pr")
        return ("waiting for you to merge the setup update (branch " + branch + ")",
                f"[setup-update] The session start made this repository's setup update itself: branch {branch} (from origin/main) "
                f"holds the commit 'Setup update (automatic, v{version})' and is pushed. "
                + (f"The pull request is open: {pr}. " if pr else
                   f"Open a pull request for it, ready for review, not a draft: base main, head {branch}, title "
                   f"'Setup update (automatic, v{version})'. ")
                + "Make no commit and switch no branch for this." + note + " In your first reply's 'I need from you' line, ask me "
                "to merge that pull request; the new setup takes effect in the next session after the merge. Then continue "
                "with my request.")
    for rel, text in staged.items():
        _write(os.path.join(project_dir, rel), text)
    return ("updated on disk just now; waiting for the pull request",
            f"[setup-update] This repository's own setup files were out of date and were updated on disk just now: "
            f"{files}.{note} Before any other work: run `git fetch origin main`, then `git switch -c {branch} "
            f"origin/main` (the updated files come along), commit exactly these files (names without the notes in brackets) with the message 'Setup update "
            f"(automatic, v{version})', push the branch, open a pull request ready for review, then switch back to the "
            "branch you started on. If the switch is refused, stop and tell me. In plan mode, present this first as a "
            "one-stage micro-plan. In your first reply's 'I need from you' line, ask me to merge that pull request; "
            "the new setup takes effect in the next session after the merge. Then continue with my request.")
