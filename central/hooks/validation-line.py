#!/usr/bin/env python3
"""Stop hook:
- the first reply of a session starts with the line "Rules v<version> · <branch>";
- a final answer opens with a three-line quote block (📌 Result / 👉 I need from you / ➡️ Next) followed by a ---
  line, and ends with the validation line;
- a progress report (workers still running) ends with the Progress line instead, accepted only after a dispatch."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, block, is_progress_report,
                     real_prompts, last_turn, first_text_of_turn, plain_lines, central_version, prompt_number)

data = read_hook_input()
if data.get("stop_hook_active"):
    sys.exit(0)  # already continuing because of a stop hook; never loop
cfg = load_config()
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records)
if not text:
    sys.exit(0)

def norm(s):
    """Compare labels without the quote marker, bold, double spaces or the invisible variation selector."""
    return re.sub(r"\s+", " ", (s or "").replace("\ufe0f", "")).strip().lower()


problems = []
# the prompt counter (UserPromptSubmit) says which prompt this is; Stop-hook feedback does not advance it
n = prompt_number(data.get("session_id"))
first_reply = n == 1 if n else len(real_prompts(records)) == 1
if first_reply:
    first = plain_lines(first_text_of_turn(last_turn(records)))
    if not (first and first[0].startswith("Rules v")):
        v = central_version() or "<version>"
        problems.append(f"This is the first reply of the session: its very first line must be 'Rules v{v} · <branch>' "
                        "(from the session-start line), before anything else, even before a note on what you will do.")

has_validation = bool(re.search(cfg["validation_line_pattern"], text))
if has_validation:
    lines = plain_lines(text)
    if lines and lines[0].startswith("Rules v"):
        lines = lines[1:]
    labels = cfg["report_top_labels"]
    top = lines[:len(labels)]
    if len(top) < len(labels) or not all(norm(l).startswith(norm(lab)) for l, lab in zip(top, labels)):
        problems.append("A final answer opens with a quote block of three lines, in everyday words with no file names, "
                        "commands or code, then a line with just ---:\n"
                        "> 📌 **Result:** <what works now or what I get>\n"
                        "> 👉 **I need from you:** <the exact action, or nothing>\n"
                        "> ➡️ **Next:** <what happens after>\n"
                        "---\n"
                        "The icons are part of the labels; a label without its icon is not accepted. Put all technical "
                        "detail below the --- line.")
    if problems:
        block(" ".join(problems) + " Rewrite the reply accordingly.")
    sys.exit(0)

if is_progress_report(text, records, cfg):
    if problems:
        block(" ".join(problems))
    sys.exit(0)
if re.search(cfg["progress_line_pattern"], text):
    block(" ".join(problems + ["A Progress line is only for reports while dispatched workers are still running, and no "
          "worker was dispatched in this session. If the work is finished, end with the validation line instead: "
          "'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|Uncertain'."]))
block(" ".join(problems + ["This reply is missing its closing line. If any worker is still running, this is a progress "
      "report: open with 'In progress — not done', drop any regression table and Confidence/Status line, and end with "
      "'Progress: <n> of <total> done · Running: <names>'. Otherwise it is a final answer: open with the quote block "
      "(> 📌 **Result:** / > 👉 **I need from you:** / > ➡️ **Next:**) followed by a --- line, and end with "
      "'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|Uncertain' with honest "
      "values."]))
