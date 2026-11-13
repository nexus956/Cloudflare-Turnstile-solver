#!/usr/bin/env python3
"""Live token view — fire N solves at once and print each token as it lands.

Run on the solver box (or anywhere that can reach it):

    python3 live_tokens.py 50
    python3 live_tokens.py 10 https://target.com/login/ 0x4AAAAAAA...

Stdlib only, no dependencies.
"""
import sys, time, json, urllib.request, urllib.parse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
URL = sys.argv[2] if len(sys.argv) > 2 else "https://dashboard.proxyscrape.com/v2/login/"
KEY = sys.argv[3] if len(sys.argv) > 3 else "0x4AAAAAAAFWUVCKyusT9T8r"
BASE = "http://127.0.0.1:6767"

lock = threading.Lock()
n_done = n_ok = 0


def one():
    u = f"{BASE}/solve?url={urllib.parse.quote(URL, safe='')}&sitekey={KEY}"
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(u, timeout=300).read())
        return d, t0
    except Exception as e:
        return {"success": False, "err": str(e)[:40]}, t0


T0 = time.time()
print(f"firing {N} solve requests at {BASE} ...")
with ThreadPoolExecutor(max_workers=N) as ex:
    futs = [ex.submit(one) for _ in range(N)]
    for f in as_completed(futs):
        d, t0 = f.result()
        wall = time.time() - t0
        with lock:
            n_done += 1
            clock = time.time() - T0
            tok = d.get("token") or ""
            if d.get("success"):
                n_ok += 1
                print(f"[t={clock:5.1f}s] #{n_done:>2}/{N}  OK  solved in {wall:4.1f}s  {tok[:32]}...", flush=True)
            else:
                print(f"[t={clock:5.1f}s] #{n_done:>2}/{N}  FAIL  {d.get('err', '')}", flush=True)

print(f"\n=== {n_ok}/{N} tokens in {time.time() - T0:.1f}s ===")
