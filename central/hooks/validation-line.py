#!/usr/bin/env python3
"""Stop hook:
- a final answer ends with a three-line quote block (📌 Result / 👉 I need from you / ➡️ Next), after a --- line,
  so the lines I act on sit right above where I type. Above the --- line, in this order: the technical detail,
  the Completion lines when required, the validation line, then the "❓ Decisions" list. Result is status only;
  "I need from you" is one short action;
- the version line is shown to me by the Stop notice (stats.py); replies do not write it;
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
    block(" ".join(problems) + " Send only what is missing: do not repeat the rest of the report, which I "
          "already see. Your re-send is short: the Completion line if one is required, the validation line, then "
          "a line with just --- and the three closing lines last.")


problems = []
if re.search(cfg["validation_line_pattern"], text):
    lines = plain_lines(text)
    labels = cfg["report_top_labels"]
    tail = lines[-len(labels):]
    if len(tail) < len(labels) or not all(norm(l).startswith(norm(lab)) for l, lab in zip(tail, labels)):
        problems.append("A final answer ends with a quote block of three lines, in everyday words with no file names, "
                        "commands or code, after a line with just ---. Nothing comes after these three lines:\n"
                        "---\n"
                        "> 📌 **Result:** <status only: what works now or what I get — no requests>\n"
                        "> 👉 **I need from you:** <one action, one short line, or nothing>\n"
                        "> ➡️ **Next:** <what happens after>\n"
                        "Above the --- line: the detail, the Completion lines if required, the validation line, then "
                        "decisions for me in a '❓ Decisions' list, one line each with your recommendation. The icons "
                        "are part of the labels.")
    else:
        need = re.sub(r"^.*?I need from you:\s*", "", tail[1].replace("*", ""), flags=re.I)
        if len(need.split()) > int(cfg["need_line_max_words"]):
            problems.append(f"The 'I need from you' line is one action in at most {cfg['need_line_max_words']} words. "
                            "Move explanations above the --- line and decisions into the '❓ Decisions' list.")
    if problems:
        send_back(problems)
    sys.exit(0)

if is_progress_report(text, records, cfg):
    if problems:
        send_back(problems)
    sys.exit(0)
send_back(problems + ["This reply has no closing line. While a worker runs, send nothing; if I ask for status, reply "
                      "with one line only: '⏳ Working on: <names> · <n> of <m> done'. Otherwise this is a final answer: "
                      "include 'Confidence: High|Medium|Low · Status: Proposed|Checked|Validated — <what was run>|"
                      "Uncertain' with honest values, and end with --- and the three closing quote lines."])
