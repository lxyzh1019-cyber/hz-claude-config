#!/bin/bash
# usage: campaign.sh <app folder> <version folder>...   (v3.2.14) runs every item test on each rules version (oldest
# first), then the real-program scenarios on the last two. Needs CLAUDE_BIN for the real-program part.
APP=$1; shift; T=$(cd "$(dirname "$0")" && pwd)
echo "| Test | $(for v in "$@"; do printf '%s | ' "$(head -1 $v/central/MANIFEST.txt | tr -d '\r' | sed 's/version: //')"; done)"
for t in 3210 3211 3212 3213 3214; do
  printf '| item test %s |' "$t"
  for v in "$@"; do a=$v; [ $t -le 3211 ] && a=$v/central
    r=$(python3 "$T/test_v${t}_items.py" "$a" 2>/dev/null | tail -1 | grep -o 'checks passed [0-9]* of [0-9]*' | sed 's/checks passed //')
    printf ' %s |' "${r:-error}"; done; echo
done
printf '| replay suite |'; for v in "$@"; do r=$(cd $v && bash central/hooks/replay-hooks.sh 2>/dev/null | tail -1); printf ' %s |' "$r"; done; echo
[ -z "$CLAUDE_BIN" ] && exit 0
n=$#; prev=${@:n-1:1}; last=${@:n:1}; i=0
for v in "$prev" "$last"; do i=$((i+1))
  r=$(HARNESS_DIR=/tmp/hz-campaign WEB=$((8300+i*10)) MOD=$((8301+i*10)) bash "$T/real-harness/scenario_wakeups.sh" "$v/central" wake$i "$APP" 2>/dev/null | head -1)
  echo "| real program, wake-ups ($(head -1 $v/central/MANIFEST.txt | tr -d '\r' | sed 's/version: //')) | $r |"
  r=$(HARNESS_DIR=/tmp/hz-campaign WEB_PORT=$((8400+i*10)) MODEL_PORT=$((8401+i*10)) bash "$T/real-harness/scenario_workflow.sh" "$v/central" wf$i "$APP" 2>/dev/null | grep -E "role files|wait line|stopped at 20|committed|foreground|Helpers started" | tr '\n' ';')
  echo "| real program, workflow ($(head -1 $v/central/MANIFEST.txt | tr -d '\r' | sed 's/version: //')) | $r |"
done
