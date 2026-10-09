"""v3.2.0: the coloured change marks, made by code.
Version (Plan vN) counts approvals. Rev counts each showing inside a version and starts at Rev 1 for each version.
At each showing after the first, code compares the plan with the one shown last time (for Rev 1 of a new version:
the approved version before it) and
- puts the square and label in front of each line that is new or changed ("🟩 **Rev 2** — …"),
- puts "Changes in this version" under the Summary: the newest showing in full (+ added or changed, - removed),
  the older showings of this version as one line each.
Old marks and old change lists (also ones the model wrote itself) are removed first, so the marks are always exact."""
import difflib
import re

import formats as F

SQ = "🟦🟩🟧🟪"
tagpairs = []
HEAD = "**Changes in this version**"
_MARK = re.compile(r"(?:[" + SQ + r"]\s*)?\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*")
_ANYMARK = re.compile(r"[" + SQ + r"]\s*\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*")
_PREFIX = re.compile(r"^(\s*(?:#{1,6}\s+|[-*•+]\s+|\d+[.)]\s+|\|\s*)?)(.*)$")
_BLOCK = re.compile(r"(?ms)^[ \t]*(?:[" + SQ + r"]\s*\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*)?\**\s*Changes in this version"
                    r"\b[^\n]*\n(?:[ \t]*\n)*```diff\n.*?^```[ \t]*\n"
                    r"(?:[ \t]*-[ \t]*[" + SQ + r"][^\n]*\n)*")


def square(rev):
    return F.SQUARES[rev % 4]


def strip_marks(text):
    """The plan without any change list and without any Rev marks in front of lines."""
    t = _BLOCK.sub("", (text or "").replace("\r\n", "\n"))   # v3.2.1: plan files on Windows end lines with CRLF
    out, fence = [], False
    for line in t.split("\n"):
        if line.strip().startswith("```"):
            fence = not fence
            out.append(line)
            continue
        if not fence:
            m = _PREFIX.match(line)
            pre, rest = m.group(1), m.group(2)
            rest2 = _MARK.sub("", rest, count=1) if _MARK.match(rest) else rest
            line = pre + _ANYMARK.sub("", rest2)
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


_NUM = re.compile(r"^\s*(?:[-*•+]|\d+[.)])\s+")
_TAGS = re.compile(r"\s*·\s*(files|after|level|size|group|proof|tests):.*$", re.I)


def _key(line):
    """Compare without list numbers (renumbering is not a change) and without spacing."""
    return re.sub(r"\s+", " ", _NUM.sub("", line.strip())).strip().lower()


def _core(line):
    """The line without its stage tags (files, after, level, size, group, proof, tests)."""
    return _TAGS.sub("", _key(line)).strip()


def _content_lines(text):
    """(index, line) of lines that can be marked: not blank, not a code fence or code, not a table rule, not the title."""
    out, fence = [], False
    for i, line in enumerate(text.split("\n")):
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            continue
        if fence or not s or re.match(r"^\|?\s*:?-{3,}", s) or (s.startswith("#") and re.search(r"\bPlan v\d+\b", s)):
            continue
        if re.match(r"^\|\s*\**summary\**\s*\|$", s, re.I) or re.match(r"^\|?\s*\**what changed", s, re.I):
            continue
        out.append((i, line))
    return out


def _tech_start(text):
    m = re.search(r"(?im)^[#>*\s]*technical details\b", text or "")
    return text[:m.start()].count("\n") if m else None


def changes(base, text):
    base, text = (base or "").replace("\r\n", "\n"), (text or "").replace("\r\n", "\n")
    """(marked line indexes, added lines, removed lines, changes in Technical details, stages with tag changes only).
    v3.2.1: renumbered lines are not changes; a stage whose only change is its tags (size, proof, …) is counted, not
    marked; lines in Technical details are counted, not marked (the owner reads the part above)."""
    a, b = _content_lines(base), _content_lines(text)
    ta, tb = _tech_start(base), _tech_start(text)
    sm = difflib.SequenceMatcher(None, [_core(l) for _, l in a], [_core(l) for _, l in b], autojunk=False)
    added_idx, added, removed, tech, tagonly, changed = [], [], [], 0, 0, []
    global tagpairs
    tagpairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if _key(a[i][1]) != _key(b[j][1]):
                    if tb is not None and b[j][0] >= tb:
                        tech += 1
                    elif _NUM.sub("", a[i][1].strip()) != _NUM.sub("", b[j][1].strip()):
                        tagonly += 1
                        tagpairs.append((a[i][1].strip(), b[j][1].strip()))
            continue
        olds, news = list(range(i1, i2)), list(range(j1, j2))
        if tag == "replace":   # v3.2.1: a line that changed in part is one changed line, not a removed plus an added one
            for j in list(news):
                best, score = None, 0.0
                for i in olds:
                    s = difflib.SequenceMatcher(None, _core(a[i][1]), _core(b[j][1]), autojunk=False).ratio()
                    if s > score:
                        best, score = i, s
                if best is not None and score >= 0.5:
                    olds.remove(best)
                    news.remove(j)
                    if tb is not None and b[j][0] >= tb:
                        tech += 1
                    else:
                        added_idx.append(b[j][0])
                        changed.append((a[best][1].strip(), b[j][1].strip()))
        for j in news:
            if tb is not None and b[j][0] >= tb:
                tech += 1
            else:
                added_idx.append(b[j][0])
                added.append(b[j][1].strip())
        for i in olds:
            if ta is not None and a[i][0] >= ta:
                tech += 1
            else:
                removed.append(a[i][1].strip())
    return added_idx, added, removed, tech, tagonly, changed


def _clean(line, limit=160):
    s = re.sub(r"^(?:[-*•+]|\d+[.)])\s+", "", line.strip().strip("|").strip().replace(" | ", " · ")).strip()
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def changed_words(old, new, limit=170):
    """Only what changed in a line: a few words of context, then "old words" → "new words" (v3.2.1)."""
    o, n = _clean(old, 10000).split(), _clean(new, 10000).split()
    sm = difflib.SequenceMatcher(None, o, n, autojunk=False)
    parts, first = [], None
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if first is None:
            first = max(0, i1 - 4)
        was, now = " ".join(o[i1:i2]), " ".join(n[j1:j2])
        parts.append(f'"{was}" → "{now}"' if was and now else f'+ "{now}"' if now else f'− "{was}"')
    head = " ".join(o[:5])
    ctx = " ".join(o[first:first + 4]) if first else ""
    s = head + (" … " + ctx if ctx and ctx not in head else "") + ": " + "; ".join(parts)
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def gist(added, removed):
    n = len(added) + len(removed)
    first = "; ".join(_clean(l)[:40] for l in (added or removed)[:2])
    return n, first


def apply(text, base, version, rev, history, since):
    """The plan with marks on this showing's changed lines and the change list under the Summary."""
    text = (text or "").replace("\r\n", "\n")
    idx, added, removed, tech, tagonly, changed = changes(base, text)
    sq = square(rev)
    label = f"{sq} **Rev {rev}** — "
    lines = text.split("\n")
    for i in idx:
        m = _PREFIX.match(lines[i])
        lines[i] = m.group(1) + label + m.group(2)
    if not added and not removed and not tech and not tagonly and not changed:
        return quick_read_count("\n".join(lines)), (0, "")
    # v3.2.9: no word-level change list any more. The owner reads "What changed" in the Quick read (written by the
    # planner, plain lines with the result) and the coloured marks below; the old block was hard to read and repeated
    # the marks (owner, 9 Oct, Plan v7).
    if F.QUICK_READ_GOAL_WORDS and "**Quick read**" in text:
        return quick_read_count("\n".join(lines)), (len(idx), gist(added, removed)[1])
    diff = ([f"+ {sq} Rev {rev} — {changed_words(o_, n_)}" for o_, n_ in changed] +
            [f"+ {sq} Rev {rev} — {_clean(l)}" for l in added] + [f"- {sq} Rev {rev} — {_clean(l)}" for l in removed])
    more = len(diff) - F.CHANGE_BLOCK_MAX_LINES
    diff = diff[:F.CHANGE_BLOCK_MAX_LINES] + ([f"+ … and {more} more changed lines, marked {sq} Rev {rev} below"]
                                               if more > 0 else [])
    if tagonly:   # v3.2.1: name what changed in the tags (size, proof, …), not only how many
        for o_, n_ in tagpairs[:3]:
            diff.append(f"+ {sq} Rev {rev} — tags only: {changed_words(o_, n_)}")
        if tagonly > 3:
            diff.append(f"+ {sq} Rev {rev} — tags changed on {tagonly - 3} more stage line(s); not marked below")
    if tech:
        diff.append(f"+ {sq} Rev {rev} — {tech} lines changed in Technical details; not marked there")
    older = []
    for h in reversed(history or []):
        if h.get("rev") == 1 and not h.get("n"):
            older.append(f"- {square(1)} **Rev 1** — first showing" + (f" ({h['since']})" if h.get("since") else ""))
        else:
            older.append(f"- {square(h['rev'])} **Rev {h['rev']}** — {h.get('n', 0)} lines changed"
                         + (f": {h['gist']}" if h.get("gist") else ""))
    block = (f"{HEAD} — Plan v{version} · {sq} Rev {rev}: what changed since {since}\n"
             "```diff\n" + "\n".join(diff) + "\n```\n" + ("\n".join(older) + "\n" if older else ""))
    # under the Summary table (the first table after the title), else right under the title
    title = next((k for k, l in enumerate(lines) if l.lstrip().startswith("#")), 0)
    k = title + 1
    while k < len(lines) and not lines[k].strip():
        k += 1
    if k < len(lines) and lines[k].lstrip().startswith("|"):
        while k < len(lines) and lines[k].lstrip().startswith("|"):
            k += 1
        pos = k
    else:
        pos = title + 1
    lines = lines[:pos] + ["", block.rstrip("\n"), ""] + lines[pos:]
    n, g = gist(added + [n_ for _, n_ in changed], removed)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)), (n + tech + tagonly, g)


def quick_read_count(text):
    """v3.2.9: write the exact word count and minutes into the Quick read title line."""
    import re as _re
    n = F.quick_read_words(text)
    if n is None:
        return text
    mins = max(1, -(-n // 200))
    return _re.sub(r"(?m)^(\s*(?:[\U0001F7E6\U0001F7E9\U0001F7E7\U0001F7EA]\s*\*\*Rev \d+\*\* — )?\*\*Quick read\*\*)[^\n]*$",
                   lambda m: f"{m.group(1)} · {n} words · about {mins} min", text, count=1)
