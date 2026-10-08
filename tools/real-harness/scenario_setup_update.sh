#!/bin/bash
# usage: scenario_setup_update.sh <central dir of the rules to serve> <label> <app repo folder>
# v3.2.4: the real Claude Code program starts a session in a copy of a real app repository. The loader fetches the rules
# from a local web server, so the session-start check of the served version runs for real. Prints what the session was
# told about the setup update, and whether the setup file on disk changed.
CENTRAL=$1; LABEL=$2; APP=$3; HERE=$(cd "$(dirname "$0")" && pwd); B=${HARNESS_DIR:-/tmp/hz-harness}/$LABEL
rm -rf $B && mkdir -p $B/home $B/web && cp -r "$APP" $B/proj && cp -r "$CENTRAL" $B/web/central
PORT=${WEB_PORT:-8130}
cd $B/web && python3 -m http.server $PORT >/dev/null 2>&1 &
WP=$!; sleep 1
cd $B
python3 - "$B" <<'PY'
import json,sys
B=sys.argv[1]
json.dump({'projects':{f'{B}/proj':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}},'hasCompletedOnboarding':True},open(f'{B}/home/.claude.json','w'))
json.dump([{'text':'Session ready.'}],open('script.json','w'))
PY
cp "$HERE/stand_in_model.py" server.py
HARNESS_LOG=$B/requests.log python3 server.py 8129 script.json > server.out 2>&1 & SP=$!; sleep 0.7
cd proj
HZ_CENTRAL_URL=http://127.0.0.1:$PORT/central/ HOME=$B/home ANTHROPIC_BASE_URL=http://127.0.0.1:8129 ANTHROPIC_API_KEY=sk-fake HZ_RULES_FIRST_OFF=1 timeout 90 ${CLAUDE_BIN:-claude} -p "hi" --output-format json > ../out.txt 2>&1 < /dev/null
cd ..; kill $SP 2>/dev/null; kill $WP 2>/dev/null
echo "rules version the session loaded: $(grep -o 'Rules v[0-9.]* loaded' $B/requests.log | head -1)"
grep -o '\[setup-update\][^|]\{0,230\}' $B/requests.log | head -1
grep -o '\[stub\][^|]\{0,120\}' $B/requests.log | head -1
echo "reviewer.md on disk: $(grep '^effort' $B/proj/.claude/agents/reviewer.md)"
