#!/usr/bin/env bash
# ONE-TIME migration: remove rules-v2 per-repo copies, add the CLAUDE.md pointer, seed per-repo files.
# After every repo is migrated this script and its workflow are retired; rules are installed centrally.
# Run by .github/workflows/sync-rules.yml. Needs env GH_TOKEN (secret RULES_SYNC_TOKEN); optional ONLY=owner/repo.
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1
[ -n "${GH_TOKEN:-}" ] || { echo "::error::Secret RULES_SYNC_TOKEN is missing — add it under Settings > Secrets and variables > Actions"; exit 1; }
CFG="$(pwd)"
VERSION="v$(python3 -c "import json;print(json.load(open('plugins/hz-rules/.claude-plugin/plugin.json'))['version'])")"
[ "$VERSION" != "v" ] || { echo "::error::cannot read the plugin version"; exit 1; }
if ! bash plugins/hz-rules/hooks/replay-hooks.sh > /tmp/replay.txt 2>&1; then echo "::error::hook tests failed: $(tail -1 /tmp/replay.txt)"; exit 1; fi
TEST="$(tail -1 /tmp/replay.txt)"
BRANCH="rules-central/$VERSION"
if [ -n "${ONLY:-}" ]; then TARGETS="$ONLY"; else TARGETS="$(grep -vE '^\s*(#|$)' repos.txt || true)"; fi
[ -n "$TARGETS" ] || { echo "::error::no target repos — uncomment at least one line in repos.txt"; exit 1; }
git config --global user.name "rules-sync"
git config --global user.email "rules-sync@users.noreply.github.com"
REPORT="$CFG/sync-report.md"; echo "## Migration to central rules $VERSION" > "$REPORT"
fail=0

for REPO in $TARGETS; do
  echo "::group::$REPO"
  W="$(mktemp -d)"; NOTES=""
  if ! git clone -q "https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git" "$W"; then
    echo "::error::cannot clone $REPO (token lacks access?)"; echo "- $REPO: **clone failed** — check the token's repository access" >> "$REPORT"; fail=1; echo "::endgroup::"; continue
  fi
  cd "$W"
  DEFAULT="$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')"
  git checkout -q -B "$BRANCH" "origin/$DEFAULT"

  # 1. retire superseded files from earlier bundle versions
  while IFS= read -r f; do
    [[ -z "$f" || "$f" == \#* ]] && continue
    if [ -e "$f" ]; then git rm -rq -- "$f"; NOTES+="- removed retired \`$f\`"$'\n'; fi
  done < "$CFG/retired.txt"

  # 2. repair: v2 install copied the bundle README over the app README in some repos
  if head -1 README.md 2>/dev/null | grep -q '^# Working-rules bundle'; then
    c="$(git log --format=%H -S '# Working-rules bundle' -- README.md | tail -1)"
    if [ -n "$c" ] && git cat-file -e "$c^:README.md" 2>/dev/null; then
      git show "$c^:README.md" > README.md; NOTES+="- **README.md had been overwritten by the v2 bundle README — restored your version from before commit ${c:0:7}. Please check it.**"$'\n'
    else
      git rm -q README.md; NOTES+="- **README.md was the v2 bundle README with no earlier version — removed.**"$'\n'
    fi
  fi

  # 3. v2 settings entries out; pointer CLAUDE.md in (a repo's own CLAUDE.md content is kept)
  if [ -f .claude/settings.json ]; then
    python3 "$CFG/scripts/unmerge_settings.py" .claude/settings.json "$CFG/scripts/v2-managed-settings.json"
    [ -f .claude/settings.json ] || { git rm -q --cached .claude/settings.json 2>/dev/null || true; NOTES+="- removed \`.claude/settings.json\` (it held only rules-v2 entries)"$'\n'; }
  fi
  if [ ! -f CLAUDE.md ] || head -1 CLAUDE.md | grep -q '^# Global Working Rules'; then
    cp "$CFG/repo-stub/CLAUDE.md" CLAUDE.md
  elif ! grep -q 'installed centrally from `hz-claude-config`' CLAUDE.md; then
    printf '\n' >> CLAUDE.md; cat "$CFG/repo-stub/CLAUDE.md" >> CLAUDE.md; NOTES+="- kept this repo's own CLAUDE.md content and appended the central-rules pointer"$'\n'
  fi

  # 4. per-repo files: created only if missing, never overwritten
  for f in FEATURES.md WORKING_RECORD.md; do
    if [ ! -e "$f" ]; then cp "$CFG/plugins/hz-rules/seed/$f" "$f"; NOTES+="- created template \`$f\` — fill it in this repo"$'\n'; fi
  done
  if grep -qi '^|.*fix rounds' WORKING_RECORD.md 2>/dev/null && ! grep -qi '^|.*workarounds' WORKING_RECORD.md; then
    NOTES+="- \`WORKING_RECORD.md\` hotspot table uses the old columns: add **Regressions caused** and **Workarounds/exceptions** after Recurrences. The hooks read the old table, but those two redesign triggers cannot fire without the columns."$'\n'
  fi
  grep -q '<app or plan name>' FEATURES.md 2>/dev/null && NOTES+="- \`FEATURES.md\` is still the template: the first implementation session here will be asked to fill it"$'\n'
  for ig in '.claude/state/' '__pycache__/'; do
    grep -qxF "$ig" .gitignore 2>/dev/null || { echo "$ig" >> .gitignore; NOTES+="- added \`$ig\` to .gitignore"$'\n'; }
  done
  git rm -rq --cached .claude/hooks/__pycache__ 2>/dev/null && NOTES+="- untracked Python cache files"$'\n' || true

  git add -A
  if git diff --cached --quiet; then
    echo "- $REPO: already migrated, no PR" >> "$REPORT"; cd "$CFG"; echo "::endgroup::"; continue
  fi
  git commit -qm "Move to central rules (hz-rules $VERSION)"
  git push -qf origin "$BRANCH"

  BODY="One-time move to **central rules** (hz-rules $VERSION). After this, rules, hooks, the executor agent and the audit skills come from the cloud environment's setup script and the local \`hz-rules\` plugin — this repository keeps only a pointer \`CLAUDE.md\`, \`FEATURES.md\` and \`WORKING_RECORD.md\`. Future rule updates need no pull request here.

Hook tests (run in hz-claude-config): \`$TEST\`

${NOTES:-- nothing else to note}

After merging: close any old \`rules-v2\` / \`rules-sync/*\` pull requests here and delete those branches; in GitHub Desktop clones of this repo, click **Fetch origin** then **Pull origin** so the old local copies are removed too."
  PR="$(gh pr list --repo "$REPO" --head "$BRANCH" --state open --json url -q '.[0].url' 2>/dev/null || true)"
  if [ -n "$PR" ]; then
    gh pr edit "$PR" --body "$BODY" >/dev/null 2>&1 || true
  elif ! PR="$(gh pr create --repo "$REPO" --base "$DEFAULT" --head "$BRANCH" --title "Move to central rules (hz-rules $VERSION)" --body "$BODY" 2>&1)"; then
    PR="https://github.com/$REPO/compare/$DEFAULT...$BRANCH (PR not created automatically: open it from this link)"
  fi
  echo "- $REPO: $PR" >> "$REPORT"
  cd "$CFG"; echo "::endgroup::"
done

cat "$REPORT"; [ -n "${GITHUB_STEP_SUMMARY:-}" ] && cat "$REPORT" >> "$GITHUB_STEP_SUMMARY"
exit $fail
