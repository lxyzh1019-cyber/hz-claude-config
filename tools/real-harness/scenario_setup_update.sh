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
# v3.2.6: HZ_LOCAL_REMOTE=1 points origin at a local bare copy (nothing is pushed to GitHub) and puts a stand-in `gh` in PATH,
# so the setup commit, the push and the pull request made by the session start can be seen.
if [ -n "$HZ_LOCAL_REMOTE" ]; then
  git init -q --bare $B/remote.git && ( cd $B/proj && git remote remove origin 2>/dev/null; git remote add origin $B/remote.git \
    && git branch -f main HEAD 2>/dev/null; git push -q origin HEAD:refs/heads/main 2>&1 | tail -1; git fetch -q origin )
  mkdir -p $B/bin && printf '#!/bin/sh\necho "$@" > %s/gh-args.txt\necho https://github.com/owner/repo/pull/7\n' "$B" > $B/bin/gh && chmod +x $B/bin/gh
  export PATH=$B/bin:$PATH
fi
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
if [ -n "$HZ_LOCAL_REMOTE" ]; then
  echo "branches on the (local) remote: $(git -C $B/remote.git branch --list 'hz-setup-update-*' | tr -d ' ' | tr '\n' ' ')"
  BR=$(git -C $B/remote.git branch --list 'hz-setup-update-*' | head -1 | tr -d ' *')
  [ -n "$BR" ] && echo "files in its commit: $(git -C $B/remote.git show --stat --format=%s $BR | grep '|' | awk '{print $1}' | tr '\n' ' ')" && echo "commit message: $(git -C $B/remote.git log -1 --format=%s $BR)" && echo "reviewer.md in the commit: $(git -C $B/remote.git show $BR:.claude/agents/reviewer.md | grep '^effort')"
  echo "pull request call: $(cat $B/gh-args.txt 2>/dev/null | cut -c1-110)"
  echo "your working folder: $(git -C $B/proj status --short | wc -l) changed files, on $(git -C $B/proj rev-parse --abbrev-ref HEAD)"
fi
