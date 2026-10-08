#!/usr/bin/env python3
"""v3.2.0: word check for ASD-STE100-lite. Prints each sentence over the word limit (default 25 words).
Code blocks, inline code, templates in <...>, paths and URLs are not counted. Use: ste_check.py <file>... or stdin.
Exit 1 when a sentence is too long, so the replay suite can fail on it."""
import re, sys

LIMIT = int(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--max=")), 25))


def sentences(text):
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`[^`]*`", "X", t)
    t = re.sub(r"<[^<>\n]{1,200}>", "X", t)
    t = re.sub(r"(?:https?://|/|[A-Za-z]:\\)\S+?(?=[.,;:!?]?(?:\s|$))", "X", t)
    out = []
    for line in t.splitlines():
        line = line.strip().lstrip("-*>#|0123456789.) ").strip()
        if not line or line.startswith(("|", "---")):
            continue
        for s in re.split(r"(?<=[.!?])[\"”]?\**\s+(?=[A-Z\"'(*`])|;\s+|:\s+(?=[A-Z(\"])", line):
            words = re.findall(r"[A-Za-z0-9][\w'’/-]*", s)
            if len(words) > LIMIT:
                out.append((len(words), s.strip()[:160]))
    return out


if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    texts = [(f, open(f, encoding="utf-8").read()) for f in files] or [("stdin", sys.stdin.read())]
    bad = 0
    for name, text in texts:
        for n, s in sentences(text):
            bad += 1
            print(f"{name}: {n} words: {s}")
    print(f"long sentences: {bad}")
    sys.exit(1 if bad else 0)
