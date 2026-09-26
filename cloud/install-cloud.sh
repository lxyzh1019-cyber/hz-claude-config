#!/usr/bin/env bash
# Installs hz-rules into ~/.claude of the cloud VM. Run by the cloud environment's setup script.
# Rules load natively as ~/.claude/CLAUDE.md; hooks, agent and skills are registered at user level.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
P="$SRC/plugins/hz-rules"
VER="$(python3 -c "import json;print(json.load(open('$P/.claude-plugin/plugin.json'))['version'])")"

install_to() {
  local H="$1" D="$1/.claude"
  mkdir -p "$D/agents" "$D/skills"
  rm -rf "$D/hz-rules" && cp -r "$P" "$D/hz-rules"
  cp "$P/agents/opus-worker.md" "$D/agents/opus-worker.md"
  for s in "$P"/skills/*/; do n="$(basename "$s")"; rm -rf "$D/skills/$n"; cp -r "$s" "$D/skills/$n"; done
  cp "$P/rules/CLAUDE-rules.md" "$D/CLAUDE.md"
  sed "s#{ROOT}#$D/hz-rules#g" "$SRC/cloud/settings-template.json" > /tmp/hz-settings.json
  python3 "$SRC/scripts/merge_settings.py" /tmp/hz-settings.json "$D/settings.json" "hz-rules/hooks/"
  if [ "$H" != "$HOME" ]; then chown -R "$(stat -c %U "$H")":"$(stat -c %G "$H")" "$D" 2>/dev/null || true; fi
  echo "hz-rules v$VER installed into $D"
}

install_to "$HOME"
# The setup script may run as a different user than the session; cover every home directory present.
for h in ${HZ_EXTRA_HOMES:-/home/*}; do
  if [ -d "$h" ] && [ "$h" != "$HOME" ]; then install_to "$h"; fi
done
exit 0
