"""Plan v5 probe: proves (1) repo hooks run, (2) a hook can fetch from this repo, (3) a Stop hook can force a fix."""
import json, os, subprocess, sys, urllib.request

mode = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.load(sys.stdin)
except Exception:
    data = {}
proj = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

if mode == "start":
    lines = [f"[probe] 1 SessionStart hook ran · python {sys.version.split()[0]} · cloud={os.environ.get('CLAUDE_CODE_REMOTE', 'false')}"]
    owner = repo = "?"
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=proj, capture_output=True, text=True, timeout=5).stdout.strip()
        parts = url.rstrip("/").removesuffix(".git").split("/")
        owner, repo = parts[-2], parts[-1]
    except Exception as e:
        lines.append(f"[probe] could not read git origin: {e}")
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/main/probe/PHRASE.txt"
    try:
        phrase = urllib.request.urlopen(raw, timeout=15).read().decode().strip()
        lines.append(f"[probe] 2 fetch OK · {raw} · phrase: {phrase}")
    except Exception as e:
        lines.append(f"[probe] 2 FETCH FAILED · {raw} · {e}")
    lines.append("[probe] In your first reply, copy every [probe] line above exactly, then say nothing else.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}}))

elif mode == "stop":
    if data.get("stop_hook_active"):
        sys.exit(0)
    text = ""
    try:
        with open(os.path.expanduser(data.get("transcript_path", "")), encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") == "assistant":
                    content = (rec.get("message") or {}).get("content") or []
                    t = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                    if t:
                        text = t
    except OSError:
        pass
    if text.rstrip().endswith("PROBE-END"):
        sys.exit(0)
    print(json.dumps({"decision": "block", "reason": "[probe] 3 Stop hook check: add a final line '[probe] 3 Stop hook forced this line' and then a last line 'PROBE-END'."}))
