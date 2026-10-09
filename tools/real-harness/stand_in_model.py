import json, sys, os, http.server, threading, itertools, re, time
LOG=open(os.environ.get('HARNESS_LOG','requests.log'),'a')
SCRIPT=json.load(open(sys.argv[2])) if len(sys.argv)>2 else []
counter=itertools.count()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        LOG.write(f"GET {self.path}\n"); LOG.flush()
        self.send_response(200); self.send_header('content-type','application/json'); self.end_headers(); self.wfile.write(b'{"data":[]}')
    def do_POST(self):
        n=int(self.headers.get('content-length') or 0); body=self.rfile.read(n)
        try: req=json.loads(body)
        except Exception: req={}
        i=next(counter)
        LOG.write(f"POST {self.path} #{i} model={req.get('model')} stream={req.get('stream')} msgs={len(req.get('messages',[]))} tools={[t.get('name') for t in req.get('tools',[])][:60]} toolchars={len(json.dumps(req.get('tools',[])))} systemchars={len(json.dumps(req.get('system','')))}\n"); LOG.flush()
        if not self.path.startswith('/v1/messages') or self.path.endswith('count_tokens'):
            self.send_response(200); self.send_header('content-type','application/json'); self.end_headers(); self.wfile.write(b'{"input_tokens":10}'); return
        # pick scripted reply: by order among main requests; default end_turn text
        first=req.get('messages',[{}])[0].get('content')
        ftxt=first if isinstance(first,str) else " ".join(x.get('text','') for x in (first or []) if isinstance(x,dict))
        m=re.search(r"Task: (W\d)", ftxt)
        if m:
            step={"text":"Finished "+m.group(1)+"."}
            time.sleep(float(os.environ.get('SUBAGENT_DELAY','0')))   # v3.2.2: a helper that takes time
            LOG.write(f"  -> subagent {m.group(1)}\n"); LOG.flush()
        else:
            # v3.2.2: log what the main session's last user message carries (notices and hook text)
            last=req.get('messages',[{}])[-1].get('content')
            ltxt=last if isinstance(last,str) else " ".join(x.get('text','') or json.dumps(x.get('content',''))[:300] for x in (last or []) if isinstance(x,dict))
            LOG.write("  LAST: "+ltxt.replace("\n"," | ")[:9000]+"\n"); LOG.flush()
            step = SCRIPT.pop(0) if SCRIPT else {"text":"all done"}
            LOG.write(f"  -> main step {json.dumps(step)[:120]}\n"); LOG.flush()
        content=[]
        if step.get("text"): content.append({"type":"text","text":step["text"]})
        for tu in step.get("tools",[]): content.append({"type":"tool_use","id":tu["id"],"name":tu["name"],"input":tu["input"]})
        stop="tool_use" if step.get("tools") else "end_turn"
        msg={"id":f"msg_{i}","type":"message","role":"assistant","model":req.get('model','claude'),"content":[],"stop_reason":None,"stop_sequence":None,"usage":{"input_tokens":100,"output_tokens":5}}
        self.send_response(200); self.send_header('content-type','text/event-stream'); self.end_headers()
        def ev(t,d): self.wfile.write(f"event: {t}\ndata: {json.dumps(d)}\n\n".encode()); self.wfile.flush()
        ev("message_start",{"type":"message_start","message":msg})
        for k,c in enumerate(content):
            if c["type"]=="text":
                ev("content_block_start",{"type":"content_block_start","index":k,"content_block":{"type":"text","text":""}})
                ev("content_block_delta",{"type":"content_block_delta","index":k,"delta":{"type":"text_delta","text":c["text"]}})
            else:
                ev("content_block_start",{"type":"content_block_start","index":k,"content_block":{"type":"tool_use","id":c["id"],"name":c["name"],"input":{}}})
                ev("content_block_delta",{"type":"content_block_delta","index":k,"delta":{"type":"input_json_delta","partial_json":json.dumps(c["input"])}})
            ev("content_block_stop",{"type":"content_block_stop","index":k})
        ev("message_delta",{"type":"message_delta","delta":{"stop_reason":stop,"stop_sequence":None},"usage":{"output_tokens":5}})
        ev("message_stop",{"type":"message_stop"})
http.server.ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()
