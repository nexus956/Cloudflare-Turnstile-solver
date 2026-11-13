#!/usr/bin/env python3
"""Rolling Turnstile token buffer.

Solves tokens in the background and keeps a rolling stock of fresh ones.
Consumers grab instantly:

    GET /token   -> {"token": "...", "age_s": 12, "buffer_left": 9}   (oldest first)
    GET /buffer  -> {"count": 10, "ages": [...], "target": 10}
    GET /health  -> {"ok": true, "count": N, "solver": "up"}

Usage:
    python3 token_buffer.py [buffer_size] [port] [target_url] [sitekey]

Defaults: size 10, port 6768, Proxyscrape demo target.
Tokens are pruned after TTL_SECONDS (Cloudflare expires them ~300s; we use
a safe margin). Buffer only keeps solving while below target — with no
consumption the refill duty is light (one solve per TTL/size seconds).

Note: a big buffer (e.g. 50) means ~size seconds to fill initially and a
steady background solve rate even when idle — tokens die unused unless
consumed within the TTL window.
"""
import sys, time, json, threading, urllib.request, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 10
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 6768
TARGET = sys.argv[3] if len(sys.argv) > 3 else "https://dashboard.proxyscrape.com/v2/login/"
SITEKEY = sys.argv[4] if len(sys.argv) > 4 else "0x4AAAAAAAFWUVCKyusT9T8r"
SOLVER = "http://127.0.0.1:6767/solve"
TTL_SECONDS = 240  # safe margin under Cloudflare's ~300s token lifetime

buf = []  # list of [token, timestamp]
lock = threading.Lock()
stats = {"solved": 0, "served": 0, "failed": 0}


def solve_one():
    u = f"{SOLVER}?url={urllib.parse.quote(TARGET, safe='')}&sitekey={SITEKEY}&timeout=90"
    d = json.loads(urllib.request.urlopen(u, timeout=120).read())
    if not d.get("success"):
        raise RuntimeError(str(d.get("err"))[:40])
    return d["token"]


def refiller():
    while True:
        try:
            with lock:
                fresh = [t for t in buf if time.time() - t[1] < TTL_SECONDS]
                buf[:] = fresh
                need = SIZE - len(buf)
            if need > 0:
                tok = solve_one()
                with lock:
                    buf.append([tok, time.time()])
                    stats["solved"] += 1
            else:
                time.sleep(1)
        except Exception:
            stats["failed"] += 1
            time.sleep(2)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/token":
            with lock:
                fresh = [t for t in buf if time.time() - t[1] < TTL_SECONDS]
                buf[:] = fresh
                if buf:
                    tok, ts = buf.pop(0)
                    stats["served"] += 1
                    body = {"token": tok, "age_s": round(time.time() - ts, 1), "buffer_left": len(buf)}
                else:
                    body = {"token": None, "err": "buffer empty — grab again in a few seconds"}
            code = 200
        elif path == "/buffer":
            with lock:
                body = {"count": len(buf), "target": SIZE,
                        "ages_s": [round(time.time() - t[1]) for t in buf]}
            code = 200
        elif path == "/health":
            with lock:
                body = {"ok": True, "count": len(buf), **stats}
            code = 200
        else:
            body = {"err": "use /token /buffer /health"}
            code = 404
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"token buffer: target={SIZE} ttl={TTL_SECONDS}s port={PORT} target={TARGET}", flush=True)
    threading.Thread(target=refiller, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
