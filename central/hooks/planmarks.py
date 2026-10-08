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
HEAD = "**Changes in this version**"
_MARK = re.compile(r"(?:[" + SQ + r"]\s*)?\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*")
_ANYMARK = re.compile(r"[" + SQ + r"]\s*\*{0,2}Rev\s*\d+\*{0,2}\s*[—–:-]\s*")
_PREFIX = re.compile(r"^(\s*(?:#{1,6}\s+|[-*•+]\s+|\d+[.)]\s+|\|\s*)?)(.*)$")
_BLOCK = re.compile(r"(?ms)^[ \t]*\**\s*Changes in this version\b[^\n]*\n(?:[ \t]*\n)*```diff\n.*?^```[ \t]*\n"
                    r"(?:[ \t]*-[ \t]*[" + SQ + r"][^\n]*\n)*")


def square(rev):
    return F.SQUARES[rev % 4]


def strip_marks(text):
    """The plan without any change list and without any Rev marks in front of lines."""
    t = _BLOCK.sub("", text or "")
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


def _key(line):
    return re.sub(r"\s+", " ", line).strip().lower()


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
    """(added_or_changed_line_indexes_in_text, added_lines, removed_lines, technical_detail_changes)."""
    a, b = _content_lines(base), _content_lines(text)
    ta, tb = _tech_start(base), _tech_start(text)
    sm = difflib.SequenceMatcher(None, [_key(l) for _, l in a], [_key(l) for _, l in b], autojunk=False)
    added_idx, added, removed, tech = [], [], [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                added_idx.append(b[j][0])
                if tb is not None and b[j][0] >= tb:
                    tech += 1
                else:
                    added.append(b[j][1].strip())
        if tag in ("replace", "delete"):
            for i in range(i1, i2):
                if ta is not None and a[i][0] >= ta:
                    tech += 1
                else:
                    removed.append(a[i][1].strip())
    return added_idx, added, removed, tech


def _clean(line, limit=160):
    s = re.sub(r"^(?:[-*•+]|\d+[.)])\s+", "", line.strip().strip("|").strip().replace(" | ", " · ")).strip()
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def gist(added, removed):
    n = len(added) + len(removed)
    first = "; ".join(_clean(l)[:40] for l in (added or removed)[:2])
    return n, first


def apply(text, base, version, rev, history, since):
    """The plan with marks on this showing's changed lines and the change list under the Summary."""
    idx, added, removed, tech = changes(base, text)
    sq = square(rev)
    label = f"{sq} **Rev {rev}** — "
    lines = text.split("\n")
    for i in idx:
        m = _PREFIX.match(lines[i])
        lines[i] = m.group(1) + label + m.group(2)
    if not added and not removed and not tech:
        return "\n".join(lines), (0, "")
    diff = [f"+ {sq} Rev {rev} — {_clean(l)}" for l in added] + [f"- {sq} Rev {rev} — {_clean(l)}" for l in removed]
    more = len(diff) - F.CHANGE_BLOCK_MAX_LINES
    diff = diff[:F.CHANGE_BLOCK_MAX_LINES] + ([f"+ … and {more} more changed lines, marked {sq} Rev {rev} below"]
                                               if more > 0 else [])
    if tech:
        diff.append(f"+ {sq} Rev {rev} — {tech} lines changed in Technical details")
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
    n, g = gist(added, removed)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)), (n + tech, g)
