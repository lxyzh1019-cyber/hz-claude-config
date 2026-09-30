#!/usr/bin/env python3
"""Stop hook:
- the first reply of a session starts with the line "Rules v<version> · <branch>";
- a final answer opens with a three-line quote block (📌 Result / 👉 I need from you / ➡️ Next) followed by a ---
  line, and ends with the validation line. Result is status only; "I need from you" is one short action;
  decisions go in a "❓ Decisions" list under the --- line;
- the only interim reply is one status line ("⏳ Working on: …") while a dispatched worker still runs.
Loop guard: at most auto_fix_max_rounds send-backs per user prompt (counted from the UserPromptSubmit hook's
prompt number, so another check's block does not make this one step aside). If the prompt number is unknown,
it falls back to stop_hook_active."""
import re, sys
from _common import (read_hook_input, load_config, read_transcript, last_assistant_text, block, is_progress_report,
                     real_prompts, last_turn, first_text_of_turn, plain_lines, central_version, prompt_number,
                     use_round)

data = read_hook_input()
cfg = load_config()
sid = data.get("session_id")
records = read_transcript(data.get("transcript_path"))
text = last_assistant_text(records)
if not text:
    sys.exit(0)


def norm(s):
    """Compare labels without the quote marker, bold, double spaces or the invisible variation selector."""
    return re.sub(r"\s+", " ", (s or "").replace("\ufe0f", "")).strip().lower()


def send_back(problems):
    r = use_round("format", sid, int(cfg["auto_fix_max_rounds"]))
    if r is None and data.get("stop_hook_active"):
        sys.exit(0)            # no prompt number here: never loop
    if r is not None and not r[1]:
        sys.exit(0)            # limit reached for this prompt
    block(" ".join(problems) + " Send only what is missing, placed at the top: do not repeat the rest of the "
          "report, which I already see. Your re-send is short: the missing lines, then the Completion line if one "
          "is required, then the validation line.")


problems = []
n = prompt_number(sid)
first_reply = n == 1 if n else len(real_prompts(records)) == 1
if first_reply:
    first = plain_lines(first_text_of_turn(last_turn(records)))
    if not (first and first[0].startswith("Rules v")):
        v = central_version() or "<version>"
        problems.append(f"This is the first reply of the session: its very first line must be 'Rules v{v} · <branch>' "
                        "(from the session-start line), before anything else, even before a note on what you will do.")

if re.search(cfg["validation_line_pattern"], text):
    lines = plain_lines(text)
    if lines and lines[0].startswith("Rules v"):
        lines = lines[1:]
    labels = cfg["report_top_labels"]
    top = lines[:len(labels)]
    if len(top) < len(labels) or not all(norm(l).startswith(norm(lab)) for l, lab in zip(top, labels)):
        problems.append("A final answer opens with a quote block of three lines, in everyday words with no file names, "
                        "commands or code, then a line with just ---:\n"
                        "> 📌 **Result:** <status only: what works now or what I get — no requests>\n"
                        "> 👉 **I need from you:** <one action, one short line, or nothing>\n"
                        "> ➡️ **Next:** <what happens after>\n"
                        "---\n"
                        "Decisions for me go in a '❓ Decisions' list under the --- line, one line each with your "
                        "recommendation. The icons are part of the labels.")
    else:
        need = re.sub(r"^.*?I need from you:\s*", "", top[1].replace("*", ""), flags=re.I)
        if len(need.split()) > int(cfg["need_line_max_words"]):
            problems.append(f"The 'I need from you' line is one action in at most {cfg['need_line_max_words']} words. "
                            "Move explanations below the --- line and decisions into the '❓ Decisions' list.")
    if problems:
        send_back(problems)
    sys.exit(0)

if is_progress_report(text, records, cfg):
    if problems:
        send_back(problems)
    sys.exit(0)
send_back(problems + ["This reply has no closing line. While a worker runs, send nothing; if I ask for status, reply "
                      "with one line only: '⏳ Working on: <names> · <n> of <m> done'. Otherwise this is a final answer: "
                      "open with the quote block and end with 'Confidence: High|Medium|Low · Status: "
                      "Proposed|Checked|Validated — <what was run>|Uncertain' with honest values."])
