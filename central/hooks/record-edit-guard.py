#!/usr/bin/env python3
"""PreToolUse (Edit/Write/MultiEdit on the working record), v3.1.26: a ledger row set to COMPLETE needs its
Evidence in the same edit. Refusing the edit now costs one small step; finding it at the end costs a whole
re-sent report."""
import re
from _common import read_hook_input, deny_tool, load_config

data = read_hook_input()
cfg = load_config()
inp = data.get("tool_input") or {}
if not str(inp.get("file_path") or "").replace("\\", "/").endswith(cfg["record_file"]):
    raise SystemExit(0)
texts = [str(inp.get(k) or "") for k in ("new_string", "content")]
texts += [str(e.get("new_string") or "") for e in (inp.get("edits") or []) if isinstance(e, dict)]
bad, unproven = [], []
STOP = {"with", "that", "this", "from", "each", "every", "pass", "passes", "tests", "test", "check", "checks", "runs"}
for line in "\n".join(texts).splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
    if len(cells) >= 3 and re.match(r"(?i)^(✅\s*)?complete\b", cells[1]) and not cells[2].strip(" -—"):
        bad.append(cells[0][:80])
    elif len(cells) >= 3 and re.match(r"(?i)^(✅\s*)?complete\b", cells[1]):
        # v3.2.0: a stage row carries its planned proof ("proof: …"); the evidence must show that proof
        m = re.search(r"(?i)\bproof:\s*(.+)$", cells[0])
        if m:
            words = {w for w in re.findall(r"[a-z0-9][a-z0-9_.:-]{3,}", m.group(1).lower()) if w not in STOP}
            if words and not any(w in cells[2].lower() for w in words):
                unproven.append(f"{cells[0][:60]} (planned proof: {m.group(1)[:60]})")
# v3.2.2: a plan stage row starts its State cell with the state (COMPLETE, PARTIAL, QUEUED, BLOCKED, SUPERSEDED, …).
# The count reads only that first word, so a cell such as "after Stage 37; else SUPERSEDED" would count wrong.
from _common import row_lead_state, PLAN_ROW
no_state = []
for line in "\n".join(texts).splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
    if len(cells) >= 2 and PLAN_ROW.match(cells[0]) and cells[1] and not row_lead_state(cells[1]):
        no_state.append(f"{cells[0][:60]} (State: {cells[1][:40]})")
if no_state:
    deny_tool("Start the State cell of each plan stage row with its state: COMPLETE, PARTIAL, NOT STARTED, IN PROGRESS, "
              "OPEN, QUEUED, WAITING ON YOU, BLOCKED or SUPERSEDED. Put any note after it (\"QUEUED — after Stage 37\"). "
              "Rows: " + "; ".join(no_state[:3]) + ". Make the edit again.")
if unproven:
    deny_tool("The evidence must show the proof the plan named for the stage. Name what ran and its result for: " +
              "; ".join(unproven[:3]) + ".")
if bad:
    deny_tool("A row set to COMPLETE needs its Evidence in the same edit (what ran and its result): " +
              "; ".join(bad[:4]) + ". Add the evidence and make the edit again.")
