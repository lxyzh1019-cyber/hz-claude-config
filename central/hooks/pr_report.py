"""v3.3.4 (P4, P5, P12; owner 16 Oct: "the token and time is too general, I need some breakdown like Weekly-Planner").
The measured part of the pull request report, in the shape of the Weekly-Planner checkpoint reports, read from the
session's own files (main session and helpers), plus the approved plan for the fold-out.
Time: every gap between two records of the main session is given to what ended it: a tool result (by tool), a
helper's hand-back (that helper), a background notice, a message from me (my time) or the next model step (thinking).
So helper time is counted (3.3.3 dropped a helper's 12 minutes as a pause) and my time is shown apart from work."""
import glob, json, os, re, subprocess
from datetime import datetime

TEST_RE = re.compile(r"\b(npm\s+(run\s+)?(test|check|smoke)|npx\s+(playwright|jest|vitest)|pytest|unittest|jest|vitest|"
                     r"node\s+\S*tests?[/\\]|run[-_]?tests?|replay-hooks)\b", re.I)
GH_WAIT_RE = re.compile(r"\bgh\s+(pr\s+checks|run\s+(watch|view|list))\b")
RECORD_FILES = ("WORKING_RECORD.md", "FEATURES.md", "docs/", "plans/")


def _ts(r):
    try:
        return datetime.fromisoformat(str(r.get("timestamp")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _load(p):
    out = []
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def _blocks(r):
    c = (r.get("message") or {}).get("content")
    return c if isinstance(c, list) else []


def _tokens(recs):
    seen, k, by_model = set(), 0, {}
    for r in recs:
        if r.get("type") != "assistant":
            continue
        m = r.get("message") or {}
        u = m.get("usage") or {}
        if not u or m.get("id") in seen:
            continue
        seen.add(m.get("id"))
        n = sum(int(u.get(x) or 0) for x in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
                                             "output_tokens"))
        k += n
        mod = re.sub(r"^claude-", "", str(m.get("model") or "?"))
        by_model[mod] = by_model.get(mod, 0) + n
    return k, by_model


def _is_mine(text):
    t = str(text or "").lstrip()
    return bool(t) and not t.startswith(("<", "Another Claude session", "Stop hook feedback", "[Request interrupted"))


def measure(transcript_path):
    tp = str(transcript_path or "")
    main = _load(tp)
    if not main:
        return None
    helpers = {}
    for f in sorted(glob.glob(os.path.join(os.path.splitext(tp)[0], "subagents", "*.jsonl"))):
        try:
            kind = json.load(open(f[:-6] + ".meta.json", encoding="utf-8")).get("agentType") or "helper"
        except (OSError, ValueError):
            kind = "helper"
        helpers[os.path.basename(f)[6:-6]] = (kind, _load(f))
    uses, kinds, steps = {}, {}, []
    refused = {"plan": 0, "pull request": 0, "other": 0}
    gh_waits, pictures, tool_calls = 0, 0, 0
    recs = [r for r in main if _ts(r) is not None and r.get("type") in ("user", "assistant")]
    ctx = []
    for r in recs:
        for b in _blocks(r):
            if b.get("type") == "tool_use":
                tool_calls += 1
                uses[b.get("id")] = (_ts(r), b.get("name"), b.get("input") or {})
                cmd = str((b.get("input") or {}).get("command") or "")
                if re.search(r"\bgh\s+(pr\s+checks|run\s+watch)\b", cmd) or \
                        re.search(r"mcp__.*(check|status)", str(b.get("name"))):
                    gh_waits += 1
            elif b.get("type") == "tool_result":
                t = json.dumps(b.get("content"), ensure_ascii=False)
                if '"type": "image"' in t:
                    pictures += 1
                if "hook error" in t[:200] or t.lstrip('"[').startswith("PreToolUse"):
                    if "plan check" in t or "Plan sent back" in t:
                        refused["plan"] += 1
                    elif "git-guard" in t and "pull request" in t:
                        refused["pull request"] += 1
                    else:
                        refused["other"] += 1
        if r.get("type") == "assistant":
            u = (r.get("message") or {}).get("usage") or {}
            if u:
                ctx.append(int(u.get("input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0)
                           + int(u.get("cache_creation_input_tokens") or 0))
    for _, (_, hr) in helpers.items():
        for r in hr:
            for b in _blocks(r):
                if b.get("type") == "tool_use":
                    tool_calls += 1
                elif b.get("type") == "tool_result" and '"type": "image"' in json.dumps(b.get("content")):
                    pictures += 1

    def add(kind, sec):
        kinds[kind] = kinds.get(kind, 0) + sec

    for i in range(len(recs) - 1):
        a, b = recs[i], recs[i + 1]
        sec = _ts(b) - _ts(a)
        if sec <= 0:
            continue
        kind = "model thinking"
        c = (b.get("message") or {}).get("content")
        if b.get("type") == "user":
            if isinstance(c, str):
                if "<agent-message" in c or "Subagent hand-back" in c:
                    m = re.search(r'agent-message\s+from=\\?"([A-Za-z0-9_-]+)', c)
                    kind = "helper: " + (helpers.get(m.group(1), ("helper",))[0] if m else "helper")
                elif "<task-notification>" in c:
                    kind = "waiting for a background command"
                elif _is_mine(c):
                    kind = "your time (answers, approvals)"
                else:
                    kind = "checks sending a reply back"
            else:
                for blk in c or []:
                    if isinstance(blk, dict) and blk.get("type") == "tool_result" and blk.get("tool_use_id") in uses:
                        t0, name, inp = uses[blk["tool_use_id"]]
                        cmd = str(inp.get("command") or "")
                        if name in ("ExitPlanMode", "AskUserQuestion"):
                            kind = "your time (answers, approvals)"
                        elif name in ("Agent", "Task"):
                            kind = "helper: " + str(inp.get("subagent_type") or "helper")
                        elif name == "Bash" and TEST_RE.search(cmd):
                            kind = "test runs"
                        elif (name == "Bash" and GH_WAIT_RE.search(cmd)) or re.search(r"mcp__.*(check|status)", name):
                            kind = "waiting for GitHub"
                        elif name == "Bash" and re.search(r"\b(git|gh)\b", cmd):
                            kind = "git and pull request"
                        elif name and name.startswith("mcp__") and "pull_request" in name:
                            kind = "git and pull request"
                        elif name in ("Edit", "Write", "MultiEdit"):
                            kind = "edits"
                        else:
                            kind = "reading and other commands"
                        if sec >= 60 and not kind.startswith("your"):
                            steps.append((sec, name, (cmd or json.dumps(inp, ensure_ascii=False))[:90]))
                        break
        if sec > 3600 or (sec > 600 and kind == "model thinking"):
            kind = "pauses (over 10 min, not counted as work)"
        add(kind, sec)
    tok_main, by_model = _tokens(main)
    tok_help = {}
    for _, (kind, hr) in helpers.items():
        k, bm = _tokens(hr)
        n, s = tok_help.get(kind, (0, 0))
        tok_help[kind] = (n + 1, s + k)
        for mod, v in bm.items():
            by_model[mod] = by_model.get(mod, 0) + v
    clock = _ts(recs[-1]) - _ts(recs[0]) if len(recs) > 1 else 0
    return {"kinds": kinds, "steps": sorted(steps, reverse=True)[:5], "refused": refused, "gh_waits": gh_waits,
            "pictures": pictures, "tool_calls": tool_calls, "tok_main": tok_main, "tok_help": tok_help,
            "by_model": by_model, "clock": clock, "ctx": (ctx[0] if ctx else 0, max(ctx) if ctx else 0),
            "build_helpers": sum(n for k, (n, _) in tok_help.items() if not re.search(r"review|explore", k, re.I))}


def record_lines(project_dir):
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=project_dir, capture_output=True,
                              text=True, timeout=10).stdout.strip()
        out = subprocess.run(["git", "diff", "--numstat", base or "HEAD~1"], cwd=project_dir, capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    n = 0
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[0].isdigit() and (p[2] in RECORD_FILES or p[2].startswith(RECORD_FILES)):
            n += int(p[0])
    return n


def measured_part(transcript_path, project_dir=None):
    m = measure(transcript_path)
    if not m:
        return None
    mins = lambda s: f"{s / 60:.1f} min"
    k = m["kinds"]
    mine = k.get("your time (answers, approvals)", 0)
    pause = k.get("pauses (over 10 min, not counted as work)", 0)
    work = {x: v for x, v in k.items() if not x.startswith(("your time", "pauses"))}
    worked = sum(work.values())
    total_tok = m["tok_main"] + sum(s for _, s in m["tok_help"].values())
    out = ["## Measured part (by code, from the session files, when the pull request opened)", "",
           "### Top 3 time sinks"]
    for i, (x, v) in enumerate(sorted(work.items(), key=lambda kv: -kv[1])[:3], 1):
        out.append(f"{i}. {x}: {mins(v)} ({v * 100 / (worked or 1):.0f}% of time worked)")
    out += ["", "### Top 3 token sinks"]
    sinks = [("main session", m["tok_main"])] + [(f"{kind} ({n}×)", s) for kind, (n, s) in m["tok_help"].items()]
    for i, (x, v) in enumerate(sorted(sinks, key=lambda kv: -kv[1])[:3], 1):
        out.append(f"{i}. {x}: {v / 1e6:.2f} M ({v * 100 / (total_tok or 1):.0f}%)")
    out += ["", "### Time by kind", "| Kind | Time |", "|---|---|"]
    out += [f"| {x} | {mins(v)} |" for x, v in sorted(k.items(), key=lambda kv: -kv[1])]
    out += ["", "### Tokens by helper and by model", "| Who | Tokens |", "|---|---|"]
    out += [f"| {x} | {v / 1e6:.2f} M |" for x, v in sorted(sinks, key=lambda kv: -kv[1])]
    out += [f"| model {x} | {v / 1e6:.2f} M |" for x, v in sorted(m["by_model"].items(), key=lambda kv: -kv[1])]
    try:   # v3.3.4 (O5): tokens by task, so reading by parts can be measured against #14 (read and check 4.75 M)
        from _common import session_table
        rows = [r for r in (session_table(transcript_path) or "").split("\n") if r.startswith("| ") and " M |" in r
                and not r.startswith("| Model") and not r.startswith("| opus") and not r.startswith("| sonnet")]
        if rows:
            out += ["", "### Tokens by task (main session and helpers)", "| Task | Tokens |", "|---|---|"]
            out += ["| " + r.split("|")[1].strip() + " | " + r.split("|")[3].strip() + " |" for r in rows
                    if len(r.split("|")) > 4]
    except Exception:
        pass
    rl = record_lines(project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ok = lambda b: "works" if b else "**does not work**"
    out += ["", "### Scorecard (default first)", "| Measure (goal) | Measured | Result |", "|---|---|---|",
            f"| Plan showings refused by the plan check (0) | {m['refused']['plan']} | {ok(m['refused']['plan'] == 0)} |",
            f"| Pull request refused (0) | {m['refused']['pull request']} | {ok(m['refused']['pull request'] == 0)} |",
            f"| Other refused steps (0) | {m['refused']['other']} | {ok(m['refused']['other'] == 0)} |",
            f"| GitHub waits (1) | {m['gh_waits']} | {ok(m['gh_waits'] <= 1)} |",
            f"| Build helpers (0 unless parallel parts) | {m['build_helpers']} | {ok(m['build_helpers'] == 0)} |",
            f"| Record and doc lines (25 or fewer) | {'?' if rl is None else rl} | "
            f"{'measured' if rl is None else ok(rl <= 25)} |",
            f"| Browser pictures in this session (every screen change) | {m['pictures']} | measured |",
            "", "### Totals", "| Measure | Value |", "|---|---|",
            f"| On the clock | {mins(m['clock'])} |", f"| Worked (your time and pauses left out) | {mins(worked)} |",
            f"| Your time (answers, approvals) | {mins(mine)} |", f"| Pauses | {mins(pause)} |",
            f"| Tokens | {total_tok / 1e6:.2f} M |", f"| Tool calls | {m['tool_calls']} |",
            f"| Helpers | {sum(n for n, _ in m['tok_help'].values())} |",
            f"| Refused steps | {sum(m['refused'].values())} |",
            f"| Main context at start / peak | {m['ctx'][0] // 1000} k / {m['ctx'][1] // 1000} k |"]
    if m["steps"]:
        out += ["", "**Slowest steps (60 s or more, your time left out):**"]
        out += [f"- {mins(s)} · {n} · `{c}`" for s, n, c in m["steps"]]
    return "\n".join(out)


def approved_plan():
    """The approved plan for the fold-out: the plan's own text, marks removed, titled Approved."""
    try:
        from _common import plan_store_load
        import planmarks
        st = plan_store_load()
        e = (st.get("plans") or {}).get(st.get("last") or "") or {}
        t = planmarks.strip_marks(e.get("text") or "")
        if not t.strip():
            return None, None
        t = re.sub(r"(?im)^(#+\s*Plan v\d+[^\n]*?)(awaiting approval)", r"\1Approved", t, count=1)
        return t.strip(), int(e.get("rev") or 1)
    except Exception:
        return None, None


# ---- v3.3.5 (owner, 16 Oct: "3.3.5 A only changes for the summary section") ----
# The summary in the Weekly-Planner shape: the Completion block, then "Tokens and time" and "Session time" as bold
# lines, not tables (tables take too much room). Tokens and time use one set of types, so every type shows both.

def _step_type(blocks):
    for b in blocks:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        n, i = str(b.get("name") or ""), (b.get("input") or {})
        c = str(i.get("command") or "")
        if n in ("ExitPlanMode", "AskUserQuestion", "EnterPlanMode"):
            return "plan"
        if n in ("Agent", "Task"):
            return "hand-overs"
        if n in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            return "edits"
        if n == "Bash" and TEST_RE.search(c):
            return "tests"
        if (n == "Bash" and re.search(r"\bgh\s+(pr\s+checks|run\s+watch)\b", c)) or re.search(r"mcp__.*(check|status)", n):
            return "waiting for GitHub"
        if (n == "Bash" and re.search(r"\b(git|gh)\b", c)) or (n.startswith("mcp__") and "pull_request" in n):
            return "git and pull request"
        return "reading and checking"
    return "answers"


def summary_data(transcript_path):
    tp = str(transcript_path or "")
    main = _load(tp)
    recs = [r for r in main if _ts(r) is not None and r.get("type") in ("user", "assistant")]
    if len(recs) < 2:
        return None
    by_id = {}
    for r in recs:
        if r.get("type") == "assistant":
            m = r.get("message") or {}
            by_id.setdefault(m.get("id"), []).extend(_blocks(r))
    tok, sec, seen, mine, hsec = {}, {}, set(), 0.0, {}
    ids = {}
    for f in glob.glob(os.path.join(os.path.splitext(tp)[0], "subagents", "*.jsonl")):
        try:
            ids[os.path.basename(f)[6:-6]] = json.load(open(f[:-6] + ".meta.json", encoding="utf-8")).get("agentType")
        except (OSError, ValueError):
            pass
    cur = "answers"
    uses = {}
    for r in recs:
        for b in _blocks(r):
            if b.get("type") == "tool_use":
                uses[b.get("id")] = (str(b.get("name") or ""), (b.get("input") or {}))
    for i, r in enumerate(recs):
        if r.get("type") == "assistant":
            m = r.get("message") or {}
            cur = _step_type(by_id.get(m.get("id")) or [])
            u = m.get("usage") or {}
            if u and m.get("id") not in seen:
                seen.add(m.get("id"))
                tok[cur] = tok.get(cur, 0) + sum(int(u.get(x) or 0) for x in (
                    "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"))
        if i + 1 >= len(recs):
            break
        nxt = recs[i + 1]
        gap = _ts(nxt) - _ts(r)
        if gap <= 0:
            continue
        kind, hk = cur, None
        if nxt.get("type") == "assistant":
            kind = _step_type(by_id.get((nxt.get("message") or {}).get("id")) or [])   # thinking for that step
        else:
            c = (nxt.get("message") or {}).get("content")
            if isinstance(c, str):
                if "<agent-message" in c or "Subagent hand-back" in c:
                    kind = "helpers"
                    _hm = re.search(r'agent-message\s+from=\\?"([A-Za-z0-9_-]+)', c)
                    hk = ids.get(_hm.group(1)) if _hm else None
                elif "<task-notification>" in c:
                    kind = "waiting for GitHub" if cur == "waiting for GitHub" else cur
                elif _is_mine(c):
                    mine += gap
                    continue
            else:
                for blk in c or []:
                    if isinstance(blk, dict) and blk.get("type") == "tool_result":
                        name, hin = uses.get(blk.get("tool_use_id"), ("", {}))
                        if name in ("ExitPlanMode", "AskUserQuestion"):
                            mine += gap
                            kind = None
                        elif name in ("Agent", "Task"):
                            kind = "helpers"
                            hk = str(hin.get("subagent_type") or "helper")
                        break
                if kind is None:
                    continue
        if gap > 3600 or (gap > 600 and kind not in ("helpers", "tests", "waiting for GitHub")):
            mine += gap          # a pause: not work
            continue
        sec[kind] = sec.get(kind, 0) + gap
        if kind == "helpers":
            hsec[hk or "helper"] = hsec.get(hk or "helper", 0) + gap
    helpers = {}
    for f in sorted(glob.glob(os.path.join(os.path.splitext(tp)[0], "subagents", "*.jsonl"))):
        try:
            kind = json.load(open(f[:-6] + ".meta.json", encoding="utf-8")).get("agentType") or "helper"
        except (OSError, ValueError):
            kind = "helper"
        k, _ = _tokens(_load(f))
        n, s = helpers.get(kind, (0, 0))
        helpers[kind] = (n + 1, s + k)
    if helpers:
        tok["helpers"] = tok.get("helpers", 0) + sum(s for _, s in helpers.values())
    _, by_model = _tokens(main)
    for f in glob.glob(os.path.join(os.path.splitext(tp)[0], "subagents", "*.jsonl")):
        for mod, v in _tokens(_load(f))[1].items():
            by_model[mod] = by_model.get(mod, 0) + v
    clock = _ts(recs[-1]) - _ts(recs[0])
    return {"tok": tok, "sec": sec, "mine": mine, "hsec": hsec, "clock": clock, "helpers": helpers, "by_model": by_model,
            "main_tok": sum(v for k, v in tok.items() if k != "helpers")}


def _m(s):
    m = s / 60
    return f"{m:.1f} min" if m < 10 else f"{round(m)} min"


def _p(v, of):
    return f"{round(100 * v / of)}%" if of and 100 * v / of >= 0.5 else "<1%"


def summary_block(transcript_path, pr_url="", rev=None, plan_name="", checks=""):
    """The chat summary and the report summary: bold labels, lines, no tables."""
    d = summary_data(transcript_path)
    if not d:
        return None
    total = sum(d["tok"].values()) or 1
    worked = sum(d["sec"].values())
    clock = d["clock"] or 1
    link = (pr_url or "").rstrip("/")
    plan_link = f"[Plan v1 Rev {rev}]({link}#approved-plan-rev-{rev})" if link and rev else f"Plan Rev {rev or '?'}"
    rep_link = f"[#{link.rsplit('/', 1)[-1]}]({link})" if link else "the pull request"
    out = [f"**Completion:** Build 1 of 1 done (100%) · Check 0 of 1 — {plan_name or 'this job'} · "
           f"**GitHub checks:** {checks or 'not read yet'}",
           f"**Waiting on you** (one stop): merge {rep_link}, then the device check",
           f"**Then, in order:** nothing · **Plan:** {plan_link} · **Report:** {rep_link}", "",
           f"**Tokens and time:** {total / 1e6:.1f} M tokens · {_m(worked)} worked"]
    out.append("- **By model:** " + " · ".join(f"{k} {_p(v, total)} ({v / 1e6:.1f} M)"
                                               for k, v in sorted(d["by_model"].items(), key=lambda kv: -kv[1])))
    roles = [("main session", d["main_tok"], worked - d["sec"].get("helpers", 0))]
    roles += [(f"{k} ({n}×)", s, d["hsec"].get(k)) for k, (n, s) in sorted(d["helpers"].items(), key=lambda kv: -kv[1][1])]
    out.append("- **By role:** " + " · ".join(f"{k} {_p(v, total)} ({v / 1e6:.1f} M)" + (f" {_m(t)}" if t else "")
                                              for k, v, t in roles))
    types = sorted(set(d["tok"]) | set(d["sec"]), key=lambda k: -d["tok"].get(k, 0))
    out.append("- **By type:** " + " · ".join(f"{k} {_p(d['tok'].get(k, 0), total)} ({d['tok'].get(k, 0) / 1e6:.1f} M) "
                                              f"{_m(d['sec'].get(k, 0))}" for k in types))
    parts = [f"your answers {_p(d['mine'], clock)} ({_m(d['mine'])})"] + [
        f"{k} {_p(v, clock)} ({_m(v)})" for k, v in sorted(d["sec"].items(), key=lambda kv: -kv[1]) if v >= 1]
    out.append(f"**Session time:** {_m(clock)} on the clock · " + " · ".join(parts))
    return "\n".join(out)
