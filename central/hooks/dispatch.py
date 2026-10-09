#!/usr/bin/env python3
"""Central switchboard. The repository stub registers only this script for each hook event it forwards
(UserPromptSubmit, PreToolUse, Stop). Which check scripts run for which event and
tool is decided here, from "dispatch" in config.json, so adding or removing a check never needs Step B.

Scripts run one after another with the same input. Combining their answers:
- Stop and SubagentStop: every check runs, and all block reasons go back in one message, with any notices for me
  (the session summary) kept beside them; every Stop is logged to .claude/state/dispatch.jsonl;
- other events: a block or deny (PreToolUse "permissionDecision": "deny" or "ask"; UserPromptSubmit "decision":
  "block"; exit code 2) wins at once and later scripts do not run;
- added context (UserPromptSubmit and others) from every script is joined into one answer."""
import json, os, re, subprocess, sys
# v3.2.7: keep the compiled checks. Every hook call used to start one python process per check, and each one compiled
# the large shared module again (bytecode caching was off). In your sessions a Read or Grep call took 1.2 s instead of
# milliseconds (Weekly-Planner 433 calls, Figure-Skate 228). Now the checks run in this one process and their compiled
# form is kept in __pycache__ of the rules cache. HZ_DISPATCH_SUBPROCESS=1 restores the old way (tests compare both).
sys.dont_write_bytecode = False
import io, importlib.util, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import save_fixes, load_config, bump_stat, log, live_proof  # noqa: E402

raw = sys.stdin.buffer.read()
try:
    data = json.loads(raw or b"{}")
except ValueError:
    data = {}
event = data.get("hook_event_name", "")
tool = data.get("tool_name", "") or ""
cfg = load_config()
entries = (cfg.get("dispatch") or {}).get(event, [])

JOIN_BLOCKS = event in ("Stop", "SubagentStop")   # every check runs; all reasons go back in one message
class _R:
    def __init__(self, code, out, err):
        self.returncode, self.stdout, self.stderr = code, out, err


def _run(path, raw):
    """Run one check in this process with its own stdin, stdout and stderr; its exit code comes back as before."""
    if os.environ.get("HZ_DISPATCH_SUBPROCESS"):
        return subprocess.run([sys.executable, "-B", path], input=raw, capture_output=True, env=os.environ)
    bout, berr = io.BytesIO(), io.BytesIO()
    old = (sys.stdin, sys.stdout, sys.stderr, sys.argv)
    tin = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
    tout = io.TextIOWrapper(bout, encoding="utf-8", write_through=True)
    terr = io.TextIOWrapper(berr, encoding="utf-8", write_through=True)
    sys.stdin, sys.stdout, sys.stderr = tin, tout, terr
    sys.argv = [path]
    code = 0
    try:
        name = "hzcheck_" + re.sub(r"\W", "_", os.path.basename(path)[:-3])
        spec = importlib.util.spec_from_file_location(name, path)
        code_obj = spec.loader.get_code(name)       # compiled once, then read from __pycache__
        exec(code_obj, {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__})
    except SystemExit as e:
        if e.code is None:
            code = 0
        elif isinstance(e.code, int):
            code = e.code
        else:
            sys.stderr.write(str(e.code) + "\n")
            code = 1
    except Exception:
        traceback.print_exc()
        code = 1
    finally:
        try:
            tout.flush(); terr.flush()
        except Exception:
            pass
        out, err = bout.getvalue(), berr.getvalue()
        sys.stdin, sys.stdout, sys.stderr, sys.argv = old
        for w in (tin, tout, terr):      # detach, so the wrappers do not close the buffers when they are freed
            try:
                w.detach()
            except Exception:
                pass
    return _R(code, out, err)


contexts, passthrough, reasons, notes, kinds = [], None, [], [], []
sid = data.get("session_id")
for e in entries:
    if isinstance(e, str):
        e = {"script": e}
    pattern = e.get("tools")
    if pattern and not re.fullmatch(pattern, tool):
        continue
    path = os.path.join(HERE, e["script"])
    if not os.path.isfile(path):
        continue
    r = _run(path, raw)
    if r.stderr:
        sys.stderr.buffer.write(r.stderr)
    if r.returncode == 2:
        sys.exit(2)
    out = r.stdout.decode("utf-8", "replace").strip()
    if not out:
        continue
    try:
        obj = json.loads(out)
    except ValueError:
        contexts.append(out)          # plain stdout counts as added context
        continue
    hso = obj.get("hookSpecificOutput") or {}
    if obj.get("systemMessage"):
        notes.append(obj.pop("systemMessage"))   # shown to the user by Claude Code; costs no AI turn
    if JOIN_BLOCKS and obj.get("decision") == "block":
        reasons.append(obj.get("reason", "").strip())
        kinds.append(obj.get("hz_kind") or "fix")
        bump_stat(sid, ("sendback:" if obj.get("hz_kind") == "work" else "savedfix:") + e["script"].replace(".py", ""))
        continue
    if obj.get("decision") == "block" or hso.get("permissionDecision") in ("deny", "ask"):
        bump_stat(sid, "refused:" + e["script"].replace(".py", ""))
        if notes:
            obj["systemMessage"] = "\n".join(notes)
        print(json.dumps(obj))
        sys.exit(0)
    if hso.get("additionalContext"):
        contexts.append(hso["additionalContext"])
    elif passthrough is None:
        passthrough = obj

# v3.1.31: only "work" problems send the answer back (the work must continue); format, wording and record problems
# are saved for the next step, so the answer is never shown twice. With a work problem, everything goes back together.
refusal_note = False
if reasons and "work" in kinds and event == "Stop":
    # v3.2.6: after a refusal by the auto-mode safety check a send-back cannot help and would repeat the whole reply
    try:
        from _common import refused_by_safety_check, read_transcript, last_turn
        if refused_by_safety_check(last_turn(read_transcript(data.get("transcript_path")))):
            kinds = [k for k in kinds if k != "work"]
            refusal_note = True
    except Exception:
        pass
if reasons and "work" not in kinds:
    # the re-send instructions in a reason make no sense for a saved fix: keep only the problem itself
    save_fixes(sid, [re.split(r"\s+(?:Send only|Your re-send|Do not repeat|Send the |Then send)", r_, maxsplit=1)[0]
                     for r_ in reasons])
    bump_stat(sid, "savedfixes")
    live_proof("saved-fixes", {"saved": len(reasons)})
    notes.append("Noted for the next step: " + str(len(reasons)) + " format or record fix(es). This answer is not repeated."
                 + (" The safety check refused the last step, so no send-back." if refusal_note else ""))
    log("dispatch", {"event": event, "sent_back": 0, "saved_fixes": len(reasons), "notices": len(notes)})
    out = {"systemMessage": "\n".join(notes)}
    print(json.dumps(out))
    sys.exit(0)
if reasons:
    body = reasons[0] if len(reasons) == 1 else "Fix all of these in one reply:\n" + "\n".join(
        f"{i}. {r}" for i, r in enumerate(reasons, 1))
    bump_stat(sid, "sendbacks")
    out = {"decision": "block", "reason": body}
    # v3.1.23: a send-back keeps the notices; v3.1.24: only the version line, so the summary shows once, at the end
    notes = [n.split("\n")[0] if n.startswith("Rules v") else n for n in notes]
    if notes:
        out["systemMessage"] = "\n".join(notes)
    log("dispatch", {"event": event, "sent_back": len(reasons), "notices": len(notes)})
    print(json.dumps(out))
    sys.exit(0)
out = {}
if contexts:
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n\n".join(contexts)}}
elif passthrough is not None:
    out = passthrough
if notes:
    out["systemMessage"] = "\n".join(notes)
if event == "Stop":
    log("dispatch", {"event": event, "sent_back": 0, "notices": len(notes)})
if out:
    print(json.dumps(out))
sys.exit(0)
