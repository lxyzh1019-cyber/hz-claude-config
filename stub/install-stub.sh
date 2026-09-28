#!/usr/bin/env bash
# One-time install of the hz-rules stub into THIS repository (run from the repo root in a cloud session):
#   curl -fsSL https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main/stub/install-stub.sh | bash
# Removes rules-v2 copies, installs the stable stub, seeds per-repo files, restores a README the v2 bundle
# overwrote, then smoke-tests the loader (which also proves this repo can fetch from hz-claude-config).
set -euo pipefail
BASE="${HZ_BASE_URL:-https://raw.githubusercontent.com/lxyzh1019-cyber/hz-claude-config/main}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
get(){ curl -fsSL "$BASE/$1" -o "$T/$(basename "$1")"; }
for f in stub/hz-loader.py stub/settings.json stub/opus-worker.md stub/sonnet-worker.md stub/CLAUDE-pointer.md stub/retired.txt \
         stub/merge_settings.py stub/unmerge_settings.py stub/v2-managed-settings.json stub/split_claude_md.py stub/v2-known-files.txt stub/retired-permissions.json \
         central/seed/FEATURES.md central/seed/WORKING_RECORD.md; do get "$f"; done
[ -d .git ] || { echo "Run this from the repository root."; exit 1; }
say(){ echo "- $*"; }

# 0. stop if this repo's own sessions changed any rules-v2 file (their improvements would be lost)
if [ "${HZ_ALLOW_LOCAL_HOOK_CHANGES:-0}" != "1" ]; then
  changed="$(python3 - "$T/v2-known-files.txt" "$T/opus-worker.md" "$T/sonnet-worker.md" <<'PY'
import hashlib, os, sys
known = {l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")}
for a in sys.argv[2:]:
    known.add(hashlib.sha256(open(a, "rb").read()).hexdigest())  # the current stub's own worker files
out = []
for base in (".claude/hooks", ".claude/skills/hz-guarantee-audit", ".claude/skills/hz-plan-regression-guard",
             ".claude/agents/opus-worker.md", ".claude/agents/sonnet-worker.md", "tests/replay-hooks.sh", "tests/test-routing-hook.md", "test/hooks.test.mjs"):
    files = [base] if os.path.isfile(base) else [os.path.join(d, f) for d, _, fs in os.walk(base) if "__pycache__" not in d for f in fs]
    for p in files:
        if hashlib.sha256(open(p, "rb").read()).hexdigest() not in known:
            out.append(p)
print("\n".join(out))
PY
)"
  if [ -n "$changed" ]; then
    echo "LOCAL CHANGES FOUND in rules-v2 files — this repo's sessions improved them after the v2 install:"
    echo "$changed" | sed 's/^/  /'
    echo "Nothing was changed. Show the user what each file changed (git log -p on it) so the improvements can be"
    echo "added to hz-claude-config first. To install anyway: HZ_ALLOW_LOCAL_HOOK_CHANGES=1."
    echo "NOT INSTALLED"
    exit 1
  fi
fi

# 1. retire rules-v2 copies and probe files
while IFS= read -r f; do
  [[ -z "$f" || "$f" == \#* ]] && continue
  if [ -e "$f" ]; then git rm -rq -- "$f" 2>/dev/null || rm -rf -- "$f"; say "removed $f"; fi
done < "$T/retired.txt"

# 2. README the v2 bundle overwrote -> restore the app's own
if head -1 README.md 2>/dev/null | grep -q '^# Working-rules bundle'; then
  c="$(git log --format=%H -S '# Working-rules bundle' -- README.md | tail -1)"
  if [ -n "$c" ] && git cat-file -e "$c^:README.md" 2>/dev/null; then git show "$c^:README.md" > README.md; say "README.md restored from before ${c:0:7} — check it"
  else git rm -q README.md; say "README.md was the v2 bundle README with no earlier version — removed"; fi
fi

# 3. settings: drop v2 entries, add the stub (keeps anything else this repo has)
mkdir -p .claude/agents
if [ -f .claude/settings.json ] && grep -q '\.claude/hooks/' .claude/settings.json; then python3 "$T/unmerge_settings.py" .claude/settings.json "$T/v2-managed-settings.json"; fi
if [ -f .claude/settings.json ]; then python3 - .claude/settings.json "$T/retired-permissions.json" <<'PY'
import json, sys
p, r = sys.argv[1], json.load(open(sys.argv[2]))
s = json.load(open(p)); perm = s.get("permissions", {})
for key, gone in r.items():
    if key in perm:
        perm[key] = [x for x in perm[key] if x not in gone]
        if not perm[key]: perm.pop(key)
json.dump(s, open(p, "w"), indent=2)
PY
fi
python3 "$T/merge_settings.py" "$T/settings.json" .claude/settings.json "hz-loader.py"
cp "$T/hz-loader.py" .claude/hz-loader.py
cp "$T/opus-worker.md" .claude/agents/opus-worker.md
cp "$T/sonnet-worker.md" .claude/agents/sonnet-worker.md
say "installed .claude/settings.json, .claude/hz-loader.py, .claude/agents/opus-worker.md, .claude/agents/sonnet-worker.md"

# 4. pointer CLAUDE.md — a repo's own content is kept: sections added under the v2 rules, or a whole own CLAUDE.md
if [ ! -f CLAUDE.md ]; then cp "$T/CLAUDE-pointer.md" CLAUDE.md; say "CLAUDE.md created as the pointer"
elif head -1 CLAUDE.md | grep -q '^# Global Working Rules'; then
  kept="$(python3 "$T/split_claude_md.py" CLAUDE.md "$T/CLAUDE-pointer.md")"
  if [ -n "$kept" ]; then say "CLAUDE.md is now the pointer; kept this repo's own sections after it: $(echo "$kept" | paste -sd ';' -)"
  else say "CLAUDE.md is now the pointer"; fi
elif ! grep -q 'hz-loader.py' CLAUDE.md; then printf '\n' >> CLAUDE.md; cat "$T/CLAUDE-pointer.md" >> CLAUDE.md; say "kept this repo's CLAUDE.md content, appended the pointer"; fi

# 5. per-repo files, created only if missing
for f in FEATURES.md WORKING_RECORD.md; do [ -e "$f" ] || { cp "$T/$f" "$f"; say "created template $f — fill it in this repo"; }; done
if grep -qi '^|.*fix rounds' WORKING_RECORD.md && ! grep -qi '^|.*workarounds' WORKING_RECORD.md; then
  say "WORKING_RECORD.md hotspot table uses old columns: add 'Regressions caused' and 'Workarounds/exceptions' after Recurrences"
fi
for ig in '.claude/state/' '__pycache__/'; do grep -qxF "$ig" .gitignore 2>/dev/null || echo "$ig" >> .gitignore; done

# 6. smoke test: the loader must fetch and inject the rules
out="$(echo '{}' | CLAUDE_PROJECT_DIR="$PWD" python3 .claude/hz-loader.py session-start.py)"
line="$(printf '%s' "$out" | python3 -c 'import json,sys;c=json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"];print([l for l in c.splitlines() if l.startswith("[session-start]")][0])')"
echo "SMOKE TEST: $line"
case "$line" in *"Rules v"*" loaded"*) echo "INSTALL OK";; *) echo "INSTALL FAILED — do not merge"; exit 1;; esac
