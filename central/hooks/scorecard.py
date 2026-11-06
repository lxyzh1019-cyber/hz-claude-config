#!/usr/bin/env python3
"""v3.3.7 (piece 9, D8 = B): the scorecard of one job, from the session file only (and its subagents folder).
One line per check: name · PASS or FAIL · the numbers behind it. The hook writes the lines into the pull request text
(between <!-- hz-scorecard --> markers) when the pull request opens and again at the merge stop; it works the same in a
cloud session, where the owner cannot upload the session file. tools/scorecard.py runs it by hand.
Checks:
 1 Git prompts on a work branch: my permission clicks (source user_temporary or user_permanent) on Bash steps that run
   git add, commit, push or merge, on a branch other than main. PASS = 0.
 2 Plan re-showings: every ExitPlanMode after a sent-back plan carries at least one colour mark, and its "What changed
   since Rev N" number is one below its newest mark. PASS = all.
 3 Phone notices: notice send-backs whose turn's notice already had a question word or the number of waiting
   decisions. PASS = 0. Also at most one notice per stop, not counting the notice that answers a correct send-back.
 4 Summary vs session file: no "Slowest steps" entry is mostly a permission wait, and the summary's send-back count
   equals the session file's hook refusals plus Stop blocks. PASS = both.
 5 Config waste: time and tokens of hook-refused steps, send-back turns and config-caused permission waits under 60
   minutes, as a share of worked time and tokens. PASS = 10% or less of each. The one review pass is shown apart.
Watch lines (not pass/fail): the clear option at plan approval and the first build step's context; whether
anthropic-skills:hz-change-guard was loaded; features broken (judged over the next 3 jobs).
Usage: python3 scorecard.py <session.jsonl>"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_facts as sf  # noqa: E402

GIT_STEP = re.compile(r"\bgit\s+(?:(?:-C|-c)\s+\S+\s+)*(add|commit|push|merge)\b")
QWORDS = re.compile(r"(?i)\b(question|decision|answer|choose|choice)s?\b")
NUMW = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
AWAY = 3600


def _m(s):
    return f"{s / 60:.1f} min"


def _tok(r, seen=None):
    """An answer's tokens, once per message id, as stats.py counts them: Claude Code writes one record per content
    block, each with the whole answer's usage (Build 3: 191.8 M counted per record, 83.1 M per answer)."""
    m = r.get("message") or {}
    if str(m.get("model") or "") == "<synthetic>":
        return 0
    if seen is not None:
        mid = m.get("id") or id(r)
        if mid in seen:
            return 0
        seen.add(mid)
    u = m.get("usage") or {}
    return sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                                             "cache_read_input_tokens"))


def _text(r):
    c = (r.get("message") or {}).get("content")
    if isinstance(c, str):
        return c
    return "\n".join(str(b.get("text") or "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")


def check1(recs, uses, res):
    waits = [w for w in sf.permission_waits(recs, uses, res)
             if w["name"] == "Bash" and GIT_STEP.search(w["command"]) and w["branch"] not in ("main", "master")]
    by = {}
    for w in waits:
        by[w["branch"] or "?"] = by.get(w["branch"] or "?", 0) + 1
    return (len(waits) == 0, f"{len(waits)} git questions, {_m(sum(w['secs'] for w in waits))} waiting"
            + (" (" + ", ".join(f"{b} {n}" for b, n in by.items()) + ")" if by else ""))


def check2(recs, uses, res):
    shows = sorted([(t0 or 0, tid, inp) for tid, (t0, n, inp, _r) in uses.items() if n == "ExitPlanMode"])
    bad, n_after, prev_sent_back = [], 0, False
    for t0, tid, inp in shows:
        txt, out = str(inp.get("plan") or ""), res.get(tid)
        if prev_sent_back:
            n_after += 1
            revs = [int(x) for x in re.findall(r"\*\*Rev (\d+)\*\*", txt)]
            marks = len(re.findall(r"[🟦🟩🟧🟪]", txt))
            since = re.search(r"(?i)What changed since\s*\**\s*Rev\s*(\d+)", txt)
            ok = marks > 0 and revs and (not since or int(since.group(1)) == max(revs) - 1)
            if not ok:
                bad.append(f"marks {marks}" + (f", since Rev {since.group(1)} vs newest Rev {max(revs)}" if since and revs else ""))
        rtxt = (out or (0, ""))[1]
        prev_sent_back = bool(out) and ("doesn't want to proceed" in rtxt or sf.is_hook_refusal(rtxt, out[3]))
    return (not bad, f"{n_after - len(bad)} of {n_after} re-showings marked and numbered right"
            + (" · wrong: " + "; ".join(bad) if bad else ""))


def _turns(recs):
    """Segments that end at a Stop (a stop_hook_summary record)."""
    seg, out = [], []
    for r in recs:
        seg.append(r)
        if r.get("subtype") == "stop_hook_summary":
            out.append(seg); seg = []
    return out


def check3(recs):
    false_sb, extra, stops = 0, 0, 0
    pushes_since = []
    answered = False
    for r in recs:
        if r.get("type") == "assistant" and not r.get("isSidechain"):
            for b in ((r.get("message") or {}).get("content") or []) if isinstance((r.get("message") or {}).get("content"), list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "PushNotification":
                    pushes_since.append(str((b.get("input") or {}).get("message") or ""))
        t = _text(r) if r.get("type") == "user" else ""
        if t.lstrip().startswith("Stop hook feedback") and re.search(r"notice", t, re.I) and re.search(
                r"PushNotification", t):
            last = next((_text(x) for x in reversed(recs[:recs.index(r)]) if x.get("type") == "assistant" and _text(x).strip()), "")
            dec = re.search(r"❓\s*\**\s*Decisions\**\s*\n(.*?)(?:\n\s*---\s*\n|\Z)", last, re.S)
            n_q = len([l for l in (dec.group(1).splitlines() if dec else []) if re.match(r"^\s*(\d+[.)]|[-*•])\s+\S", l)])
            named = any(QWORDS.search(p) or (n_q and re.search(r"(?<![#\d])\b%d\b|\b%s\b" % (n_q, NUMW.get(n_q, "@@")), p, re.I))
                        for p in pushes_since)
            if pushes_since and named:
                false_sb += 1
            answered = not (pushes_since and named)   # a correct send-back: its answering notice does not count
        if r.get("subtype") == "stop_hook_summary":
            stops += 1
            n = len(pushes_since) - (1 if answered and pushes_since else 0)
            if n > 1:
                extra += 1
            pushes_since, answered = [], False
    ok = false_sb == 0 and extra == 0
    return ok, f"{false_sb} notice send-backs although the notice named what waits · {extra} stops with more than one notice ({stops} stops)"


def check4(recs, uses, res):
    waits = sf.wait_secs_by_id(recs, uses, res)
    sb = sf.sendback_count(recs)
    shown = None
    for r in recs:
        a = r.get("attachment") or {}
        txt = str(a.get("content") or a.get("stdout") or "") if a.get("type") == "hook_system_message" else ""
        if not txt and r.get("type") == "assistant":
            txt = _text(r) if "Slowest steps" in _text(r) else ""
        if "Slowest steps" in txt or re.search(r"send-backs \d+", txt):
            shown = txt
    if shown is None:
        return True, f"no summary shown in the session file · session file: {sb['total']} send-backs ({sb['refusals']} refusals + {sb['stop_blocks']} Stop blocks)"
    bad_slow = []
    m = re.search(r"Slowest steps:?\**\s*(.+)", shown)
    if m:
        for part in re.split(r" · ", m.group(1).split("\n")[0]):
            lab = re.sub(r"^main:\s*", "", part).rsplit(" ", 2)[0].strip()[:38]
            for tid, (t0, n, inp, _r) in uses.items():
                d = str(inp.get("description") or inp.get("command") or "")
                if n == "Bash" and lab and d.startswith(lab):
                    tot = ((res.get(tid) or (t0,))[0] or 0) - (t0 or 0)
                    if tot > 0 and waits.get(tid, 0) > tot / 2:
                        bad_slow.append(f"'{lab[:30]}' {_m(waits[tid])} of {_m(tot)} was my click")
                    break
    sm = re.search(r"send-backs (\d+)", shown)
    shown_sb = int(sm.group(1)) if sm else None
    ok = not bad_slow and (shown_sb is None or shown_sb == sb["total"])
    return ok, (f"slowest steps that are mostly my click: {len(bad_slow)}" + (" (" + "; ".join(bad_slow[:3]) + ")" if bad_slow else "")
                + f" · send-backs shown {shown_sb if shown_sb is not None else '?'} vs session file {sb['total']} "
                  f"({sb['refusals']} refusals + {sb['stop_blocks']} Stop blocks)")


def check5(recs, uses, res, tp):
    # worked time: the summary's own definition (session_facts.session_time, also used by stats.py)
    try:
        from _common import is_test_run as _itr
    except Exception:
        _itr = None
    st = sf.session_time(recs, AWAY, sf.wait_secs_by_id(recs, uses, res), _itr)
    worked = st["active"] if st else 0.0
    left = st["left_out"] if st else []
    seen = set()
    main_tok = sum(_tok(r, seen) for r in recs if r.get("type") == "assistant")
    helpers = sf.helper_files(tp)
    help_tok = sum(_tok(r, seen) for _, _, hr in helpers for r in hr if r.get("type") == "assistant")
    total_tok = main_tok + help_tok
    w_sec, w_tok, w_seen = 0.0, 0, set()
    # hook-refused steps: the step after the refusal
    for rf in sf.refusals(recs, uses, res):
        i = next((k for k, r in enumerate(recs) if sf.ts(r) == rf["ts"]), None)
        nxt = next((x for x in recs[(i or 0) + 1:] if x.get("type") == "assistant"), None) if i is not None else None
        if nxt:
            w_tok += _tok(nxt, w_seen); w_sec += max((sf.ts(nxt) or 0) - (rf["ts"] or 0), 0)
    # send-back turns: from the Stop block to the next Stop
    idx = [k for k, r in enumerate(recs) if r.get("type") == "user" and _text(r).lstrip().startswith("Stop hook feedback")]
    for k in idx:
        end = next((j for j in range(k + 1, len(recs)) if recs[j].get("subtype") == "stop_hook_summary"), len(recs) - 1)
        seg = recs[k:end + 1]
        w_tok += sum(_tok(r, w_seen) for r in seg if r.get("type") == "assistant")
        t0, t1 = sf.ts(recs[k]), sf.ts(recs[end])
        if t0 and t1:
            w_sec += max(t1 - t0, 0)
    # permission waits the setup caused (a settings rule), under 60 minutes
    cw = [w for w in sf.permission_waits(recs, uses, res) if w["reason"].startswith(("rule:", "subcommands:")) and
          "rule:projectSettings" in w["reason"] and w["secs"] < AWAY]
    w_sec += sum(w["secs"] for w in cw)
    pt = 100 * w_sec / worked if worked else 0
    pk = 100 * w_tok / total_tok if total_tok else 0
    rev = [(k, hr) for k, _, hr in helpers if k.startswith("reviewer")]
    rv_sec = sum((max(sf.ts(r) or 0 for r in hr) - min(sf.ts(r) or 0 for r in hr if sf.ts(r))) for _, hr in rev if hr)
    rv_seen = set()
    rv_tok = sum(_tok(r, rv_seen) for _, hr in rev for r in hr if r.get("type") == "assistant")
    return (pt <= 10 and pk <= 10,
            f"{_m(w_sec)} of {_m(worked)} worked ({pt:.0f}%) · {w_tok / 1e6:.1f} M of {total_tok / 1e6:.1f} M tokens ({pk:.0f}%)"
            f" — refused steps, send-back turns, {len(cw)} setup permission waits"
            + (f" · left out as away (as in the summary): " + "; ".join(f"{k} {_m(sec)}" for _, sec, k in left) if left else ""),
            f"Review pass (the check step, not waste): {len(rev)} reviewer run(s), {_m(rv_sec)}, {rv_tok / 1e6:.1f} M tokens")


def watch(recs, uses, res):
    out = []
    appr = next(((t1, r) for tid, (t1, txt, err, r) in sorted(res.items(), key=lambda kv: kv[1][0] or 0)
                 if (uses.get(tid) or (0, ""))[1] == "ExitPlanMode" and "approved your plan" in txt), None)
    cleared = any(re.search(r"(?i)context (was )?cleared|clear(ed)? the context|/clear\b", json.dumps(r, ensure_ascii=False)[:4000])
                  for r in recs if r.get("type") in ("system", "user") and (appr is None or (sf.ts(r) or 0) >= (appr[0] or 0)))
    first = next((r for r in recs if appr and r.get("type") == "assistant" and (sf.ts(r) or 0) > (appr[0] or 0)
                  and (r.get("message") or {}).get("usage")), None)
    ctx = 0
    if first:
        u = first["message"]["usage"]
        ctx = int(u.get("input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
    out.append(f"Watch · clear option at plan approval: {'used' if cleared else 'not seen'}"
               + (f" · first build step after approval carried {ctx // 1000} k context" if appr else " · no approved plan"))
    loaded = any(n == "Skill" and "hz-change-guard" in str(inp.get("skill") or inp) for _, (t0, n, inp, _r) in uses.items()) or \
        any("anthropic-skills:hz-change-guard" in json.dumps(r.get("attachment") or {}, ensure_ascii=False)[:3000] for r in recs)
    out.append(f"Watch · anthropic-skills:hz-change-guard loaded: {'yes' if loaded else 'no'}")
    out.append("Watch · features broken: judged over the next 3 jobs")
    return out


def lines(tp):
    recs = [r for r in sf.load(tp) if not r.get("isSidechain")]
    uses, res = sf.tool_uses(recs), sf.results(recs)
    out = []
    for name, (ok, nums) in (("1 Git prompts on a work branch", check1(recs, uses, res)),
                             ("2 Plan re-showings", check2(recs, uses, res)),
                             ("3 Phone notices", check3(recs)),
                             ("4 Summary vs session file", check4(recs, uses, res))):
        out.append(f"{name} · {'PASS' if ok else 'FAIL'} · {nums}")
    ok5, n5, rv = check5(recs, uses, res, tp)
    out.append(f"5 Config waste · {'PASS' if ok5 else 'FAIL'} · {n5}")
    out.append(rv)
    out += watch(recs, uses, res)
    return out


def pr_text(tp):
    return "## Scorecard (made by code from the session file)\n\n" + "\n".join(f"- {l}" for l in lines(tp))


if __name__ == "__main__":
    for l in lines(sys.argv[1]):
        print(l)
