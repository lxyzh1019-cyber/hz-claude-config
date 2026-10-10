#!/usr/bin/env python3
"""v3.2.10 stand-in model for scenario_workflow.sh. Answers /v1/messages like the API (streamed), so the real Claude
Code program runs its real tools and hooks. The main session follows main.json. A workflow helper is recognised by
'WFAGENT <letter>' in its first message and follows PLAN below:
  A  test-speed helper: runs the tests 22 times (limits 20/40 apply, so it is warned at 20 and not stopped)
  B  edits css/b.css, commits it on the work branch, runs the tests 3 times
  C  reads its role file, runs the tests 3 times
Every request is logged to req.log with the last message the model saw (hook texts included)."""
import json, sys, re, http.server, itertools
LOG = open('req.log', 'a'); main_steps = json.load(open(sys.argv[2])); cnt = itertools.count()
ROLE = sys.argv[3] if len(sys.argv) > 3 else ''


def plan(a):
    t = {"command": "npm test", "description": "run tests"}
    if a == 'A':
        return [("Bash", t)] * 22
    if a == 'B':
        return [("Write", {"file_path": "css/b.css", "content": "/* b */\n"}),
                ("Bash", {"command": "git add css/b.css && git commit -q -m 'b from workflow'", "description": "commit"})] + [("Bash", t)] * 3
    return [("Read", {"file_path": ROLE})] + [("Bash", t)] * 3


def txt(c):
    return c if isinstance(c, str) else " ".join((x.get('text') or json.dumps(x.get('content', ''))) for x in (c or []) if isinstance(x, dict))


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200); self.send_header('content-type', 'application/json'); self.end_headers()
        self.wfile.write(b'{"data":[]}')

    def do_POST(self):
        n = int(self.headers.get('content-length') or 0); req = json.loads(self.rfile.read(n) or b'{}'); i = next(cnt)
        if 'count_tokens' in self.path or not self.path.startswith('/v1/messages'):
            self.send_response(200); self.send_header('content-type', 'application/json'); self.end_headers()
            self.wfile.write(b'{"input_tokens":10}'); return
        msgs = req.get('messages', []); first = txt(msgs[0].get('content')) if msgs else ''
        last = txt(msgs[-1].get('content')) if msgs else ''
        sysx = json.dumps(req.get('system', ''))
        if '<transcript>' in last or 'Respond with <severity>' in sysx + last or 'MUST begin with <block>' in sysx + last:
            step = {"text": "<severity>0</severity>" if 'severity' in sysx + last else "<block>no</block>"}
            LOG.write(f"#{i} classifier\n"); LOG.flush(); return self.reply(i, req, step)
        m = re.search(r"WFAGENT (\w)", first)
        if m:
            a = m.group(1); done = sum(1 for mm in msgs if mm.get('role') == 'assistant'); p = plan(a)
            LOG.write(f"#{i} agent {a} step {done} LAST: {last.replace(chr(10), ' | ')[:500]}\n")
            step = ({"tools": [{"id": f"toolu_{a}{done}_{i}", "name": p[done][0], "input": p[done][1]}]}
                    if done < len(p) else {"text": f"Agent {a} finished."})
        elif len(msgs) <= 1 and 'quota' in last.lower():
            step = {"text": "ok"}
        else:
            LOG.write(f"#{i} MAIN LAST: {last.replace(chr(10), ' | ')[:1500]}\n")
            step = main_steps.pop(0) if main_steps else {"text": "all done"}
        LOG.write(f"   -> {json.dumps(step)[:150]}\n"); LOG.flush()
        self.reply(i, req, step)

    def reply(self, i, req, step):
        content = []
        if step.get("text"):
            content.append({"type": "text", "text": step["text"]})
        for tu in step.get("tools", []):
            content.append({"type": "tool_use", **tu})
        stop = "tool_use" if step.get("tools") else "end_turn"
        msg = {"id": f"msg_{i}", "type": "message", "role": "assistant", "model": req.get('model', 'x'), "content": [],
               "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 5}}
        self.send_response(200); self.send_header('content-type', 'text/event-stream'); self.end_headers()

        def ev(t, d):
            self.wfile.write(f"event: {t}\ndata: {json.dumps(d)}\n\n".encode()); self.wfile.flush()
        ev("message_start", {"type": "message_start", "message": msg})
        for k, c in enumerate(content):
            if c["type"] == "text":
                ev("content_block_start", {"type": "content_block_start", "index": k, "content_block": {"type": "text", "text": ""}})
                ev("content_block_delta", {"type": "content_block_delta", "index": k, "delta": {"type": "text_delta", "text": c["text"]}})
            else:
                ev("content_block_start", {"type": "content_block_start", "index": k, "content_block": {"type": "tool_use", "id": c["id"], "name": c["name"], "input": {}}})
                ev("content_block_delta", {"type": "content_block_delta", "index": k, "delta": {"type": "input_json_delta", "partial_json": json.dumps(c["input"])}})
            ev("content_block_stop", {"type": "content_block_stop", "index": k})
        ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 5}})
        ev("message_stop", {"type": "message_stop"})


http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
