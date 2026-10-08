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
import os, re, sys
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
# v3.1.26: a short chat reply in a request that used no tools (a greeting, a quick answer) is not sent back for its
# closing lines — a send-back re-reads the whole session for a few words. Work reports still are.
_turn = last_turn(records)
_used_tools = any(isinstance(b, dict) and b.get("type") == "tool_use"
                  for r in _turn if r.get("type") == "assistant"
                  for b in ((r.get("message") or {}).get("content") or []) if isinstance((r.get("message") or {}).get("content"), list))
_limit = int(os.environ.get("HZ_CHAT_REPLY_MAX_CHARS") or cfg.get("chat_reply_max_chars", 800))
if not _used_tools and len(text) <= _limit:
    sys.exit(0)
# v3.1.26: work started in the background this request (a worker or command still running) — a short note without
# the closing lines is a status message, not a final answer; the final answer comes when the work returns
_bg = any(isinstance(b, dict) and b.get("type") == "tool_use" and (b.get("input") or {}).get("run_in_background")
          for r in _turn if r.get("type") == "assistant"
          for b in ((r.get("message") or {}).get("content") or []) if isinstance((r.get("message") or {}).get("content"), list))
if _bg and len(text) <= min(_limit, 400) and not re.search(cfg["validation_line_pattern"], text):
    sys.exit(0)


def norm(s):
    """Compare labels without the quote marker, bold, double spaces or the invisible variation selector."""
    return re.sub(r"\s+", " ", (s or "").replace("\ufe0f", "")).strip().lower()


import formats as F   # v3.2.0: the formats come from the format file
RESEND_DEFAULT = ("Send only what is missing. Do not repeat the rest of the report; I already see it. Send the "
                  "Completion line if one is required, the validation line, a line with just ---, and the closing "
                  "block last.")
# v3.1.29: everything already on my screen stays there, so a re-send repeats only the part that failed
RESEND_CLOSING = ("Send only a line with just --- and the closing block. Do not repeat the rest; I already see it.")
RESEND_LINE = ("Send only the validation line. The closing block above was right.")


def send_back(problems, resend=RESEND_DEFAULT):
    r = use_round("format", sid, int(cfg["auto_fix_max_rounds"]))
    if r is None and data.get("stop_hook_active"):
        sys.exit(0)            # no prompt number here: never loop
    if r is not None and not r[1]:
        sys.exit(0)            # limit reached for this prompt
    block(" ".join(problems) + " " + resend)


def closing_ok(t):
    lines = plain_lines(t)
    labels = cfg["report_top_labels"]
    tail = lines[-len(labels):]
    return len(tail) == len(labels) and all(norm(l).startswith(norm(lab)) for l, lab in zip(tail, labels))


problems = []
if re.search(cfg["validation_line_pattern"], text):
    outside_code = re.sub(r"```.*?```", " ", text, flags=re.S)
    utc = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:UTC|GMT)\b|\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z\b"
                     "", outside_code)
    if utc:   # v3.1.25: times for me are in Edmonton time
        problems.append(f"Give times in Edmonton time (MDT/MST), not UTC ({', '.join(sorted(set(utc))[:3])}); the "
                        "session start gives the current Edmonton time. Logs inside a code block may keep UTC.")
    lines = plain_lines(text)
    labels = cfg["report_top_labels"]
    tail = lines[-len(labels):]
    if len(tail) < len(labels) or not all(norm(l).startswith(norm(lab)) for l, lab in zip(tail, labels)):
        problems.append("A final answer ends with the closing block. Nothing comes after it.\n" + F.CLOSING_SHAPE +
                        "\n" + F.ANSWER_ORDER + " " + F.CLOSING_WORDS + " The icons are part of the labels.")
    else:
        jargon = sorted({j.strip() for l in tail for j in re.findall(
            r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\b\d+(?:\.\d+)?\s?(?:px|pt|rem|em)\b", l)})
        if jargon:   # v3.1.24: colour codes and sizes mean nothing to me; say what I will see
            problems.append("The three closing lines are in everyday words: no colour codes or sizes (" +
                            ", ".join(jargon[:4]) + "). Say what I will see — for example 'a slightly darker "
                            "orange-red' or 'finger-sized buttons'. A change from what I approved is a question in "
                            "the '❓ Decisions' list, not news.")
        # v3.1.28: a difference from the prototype is asked with pictures — prototype and build side by side
        dev_lines = [l for l in re.sub(r"```.*?```", " ", text, flags=re.S).splitlines()
                     if re.search(cfg.get("deviation_subject", r"(?i)\b(prototype|reference|mock-?ups?|approved design)\b"), l)
                     and re.search(cfg.get("deviation_words", r"(?i)\b(differ\w*|deviat\w*|doesn't have|does not have|"
                                                                 r"instead of|not in the|unlike|changes? from|departs?)\b"), l)]
        has_pictures = re.search(r"https?://\S+|!\[[^\]]*\]\(|\.(png|jpe?g|webp|gif|html)\b", text, re.I)
        if dev_lines and "❓" in text and not has_pictures:
            problems.append("A difference from the prototype is a question with pictures. Show the prototype and the "
                            "build side by side for each difference, numbered like the '❓ Decisions' list. A worker "
                            "makes one comparison page per batch. Put its link in this reply. Words alone are not "
                            "enough for me to decide.")
        # v3.2.0: every problem comes with a solution — each line of the decisions list names a recommendation
        _dec = re.search(r"❓\s*\**\s*Decisions\**\s*\n(.*?)(?:\n\s*---\s*\n|\Z)", text, re.S)
        if _dec:
            _items = [l.strip() for l in _dec.group(1).splitlines() if re.match(r"^\s*(\d+[.)]|[-*•])\s+\S", l)]
            _bare = [l for l in _items if not re.search(cfg.get("recommend_words", r"(?i)recommend"), l)]
            if _bare:
                problems.append(f"Each line of the '❓ Decisions' list names your recommendation. {len(_bare)} line(s) "
                                "have none: " + "; ".join(x[:50] for x in _bare[:3]) + ".")
        need = re.sub(r"^.*?I need from you:\s*", "", tail[1].replace("*", ""), flags=re.I)
        if len(need.split()) > int(cfg["need_line_max_words"]):
            problems.append(f"The 'I need from you' line is one action in at most {cfg['need_line_max_words']} words. "
                            "Move explanations above the --- line and decisions into the '❓ Decisions' list.")
    if problems:
        # only the closing block failed (no time, colour or picture problem in the body) → re-send just that block
        only_closing = len(problems) == 1 and problems[0].startswith("A final answer ends with the closing block")
        send_back(problems, RESEND_CLOSING if only_closing else RESEND_DEFAULT)
    sys.exit(0)

if is_progress_report(text, records, cfg):
    if problems:
        send_back(problems)
    sys.exit(0)
if closing_ok(text):   # v3.1.29: the closing block is right; only the validation line is missing or malformed
    send_back(problems + ["This reply has no valid validation line: '" + F.VALIDATION_SHAPE + "'. You can add ' — "
                          "<short note>'. Validated names what ran."], RESEND_LINE)
send_back(problems + ["This reply has no closing block. While a worker runs, send nothing. If I ask for status, reply "
                      "with one line only: '" + F.WORKING_LINE + "'. Otherwise this is a final answer. Add the "
                      "validation line with honest values: '" + F.VALIDATION_SHAPE + "'. End with --- and the "
                      "closing block."])
