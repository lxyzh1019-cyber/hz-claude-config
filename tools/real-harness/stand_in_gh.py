#!/usr/bin/env python3
"""v3.3.7: a stand-in `gh` for a simulated cloud session (code.claude.com cloud-environments: the GitHub proxy rejects
GraphQL, so `gh pr …` and `gh issue …` answer 403, while `gh api` REST calls for attached repositories work).
Use: HZ_GH_CMD='["python3", "<this file>"]' and STAND_IN_GH_STORE=<json file>. Every call is logged in the store.
REST it answers: GET/PATCH repos/{o}/{r}/pulls/{n}, GET repos/{o}/{r}/pulls?…, POST repos/{o}/{r}/pulls,
GET repos/{o}/{r}/commits/{sha}/check-runs (the store's "checks", default all passed)."""
import json, os, re, sys

store_path = os.environ.get("STAND_IN_GH_STORE") or "stand-in-gh.json"
try:
    st = json.load(open(store_path, encoding="utf-8"))
except (OSError, ValueError):
    st = {}
st.setdefault("calls", []).append(sys.argv[1:])
st.setdefault("pulls", {})


def save():
    json.dump(st, open(store_path, "w", encoding="utf-8"), indent=1)


a = sys.argv[1:]
if not a or a[0] in ("pr", "issue"):
    save()
    sys.stderr.write("HTTP 403: GraphQL requests are not allowed through the GitHub proxy\n")
    sys.exit(1)
if a[0] != "api":
    save()
    sys.exit(1)
method, path, fields, body = "GET", None, {}, None
i = 1
while i < len(a):
    x = a[i]
    if x == "-X":
        method = a[i + 1]; i += 2; continue
    if x in ("-f", "-F"):
        k, _, v = a[i + 1].partition("="); fields[k] = v; i += 2; continue
    if x == "--input":
        body = json.load(open(a[i + 1], encoding="utf-8")); i += 2; continue
    if path is None:
        path = x
    i += 1
body = dict(body or {}, **fields)
m = re.fullmatch(r"repos/([^/]+)/([^/]+)/pulls/(\d+)", path or "")
if m:
    pr = st["pulls"].setdefault(m.group(3), {"number": int(m.group(3)), "body": "", "draft": False, "state": "open",
                                             "head": {"sha": st.get("head_sha", "abc1234")}})
    if method == "PATCH":
        pr.update({k: v for k, v in body.items() if k in ("body", "title", "base")})
    save(); print(json.dumps(pr)); sys.exit(0)
if re.fullmatch(r"repos/[^/]+/[^/]+/pulls(\?.*)?", path or ""):
    if method == "POST":
        n = str(max([int(k) for k in st["pulls"]] + [0]) + 1)
        st["pulls"][n] = {"number": int(n), "body": body.get("body", ""), "draft": str(body.get("draft")) == "true",
                          "state": "open", "html_url": f"https://github.com/{path.split('/')[1]}/{path.split('/')[2]}/pull/{n}",
                          "head": {"ref": body.get("head"), "sha": st.get("head_sha", "abc1234")}}
        save(); print(json.dumps(st["pulls"][n])); sys.exit(0)
    save(); print(json.dumps(st.get("pull_list", []))); sys.exit(0)
if re.fullmatch(r"repos/[^/]+/[^/]+/commits/[^/]+/check-runs(\?.*)?", path or ""):
    save(); print(json.dumps({"check_runs": st.get("checks", [{"name": "test", "status": "completed", "conclusion": "success"}])}))
    sys.exit(0)
save()
print("{}")
