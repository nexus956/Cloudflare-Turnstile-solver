# Cloudflare Turnstile Solver

Fast, high-performance automated Cloudflare Turnstile token resolver built with Playwright and Express. Runs as a long-lived service: pre-warmed browser pools, hybrid headless/headful lanes, a bounded request queue, and automatic crash recovery.

**Verified performance** (8-vCPU VPS, live Cloudflare):

| Load | Result |
|---|---|
| 1 solve | ~4s |
| 50 simultaneous | 50/50 tokens in ~50s (~1 token/s) |
| 100 simultaneous | 100/100 in ~101s |
| 1000 simultaneous | 999/1000 in ~18 min |
| Non-interactive challenges | 4.4 tokens/s (headless lane) |

---

## How it works — the workflow

```
                       ┌────────────────────────────┐
 request ──► /solve ───►│  queue (per-lane limits)   │
                       └───────────┬────────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
     ┌── headless lane ──┐                    ┌── headful lane ──┐
     │ cheap, no display │   interactive?     │ Xvfb display,    │
     │ ~2s/solve         │ ── challenge ────► │ real click,      │
     │ limit 20          │    detected        │ ~4s/solve        │
     └───────────────────┘                    │ limit 10         │
                                              └────────┬─────────┘
                    ┌──────────────────────────────────┘
                    ▼
              token in response JSON
```

1. Every request enters a **queue** (per-lane concurrency limits) — bursts never
   melt the browser; they wait in line and are served at the machine's full speed.
2. Requests start on the **headless lane**. Non-interactive challenges (most
   sites) are solved there in ~2s.
3. If a challenge turns **interactive** (a click is required), the attempt is
   aborted instantly and **escalated** to the headful lane, which solves it
   100%. The sitekey is remembered — later solves for that site go straight to
   the headful lane.
4. Contexts keep their **cookies between solves**, so repeat solves look like
   returning visitors and run at warm speed (~4s vs 13s cold).
5. If the browser process dies (OOM, GPU abort), the next solve **relaunches
   it and rebuilds the pool automatically** — the service never stays down.
6. Tokens are **single-use** and expire after ~5 minutes. Solve → use quickly.

**Why the queue exists:** 8 CPU cores render ~10 interactive challenges at
once at full speed. More simultaneous pages = every solve stretches (15 → 20
pages) or collapses (50 pages: 86% success, 21GB RAM — measured). The queue
converts a flood into a steady, reliable stream instead of a meltdown.

---

## Install & run

```bash
npm install
npx playwright install chromium

# headful (needed for interactive challenges): run inside Xvfb
npm run start:xvfb
# headless-only (non-interactive sites, no display needed):
npm start
```

### Production (PM2)

```bash
pm2 start ecosystem.config.js && pm2 save && pm2 startup
```

`ecosystem.config.js` reference:

```js
env: {
  NODE_ENV: 'production',
  PORT: 6767,
  MODE: 'hybrid',              // headless | headful | hybrid
  POOL_SIZE: 50,              // warm contexts per lane
  MAX_CONCURRENT_HEADLESS: 20, // non-interactive lane limit
  MAX_CONCURRENT_HEADFUL: 10   // interactive lane limit (10 = 8-vCPU optimum)
}
```

---

## Configuration reference

| Flag | Env | Default | Meaning |
|---|---|---|---|
| `--mode` | `MODE` | `hybrid` | `headless` (cheap, no display), `headful` (Xvfb, solves interactive), `hybrid` (headless-first, auto-escalate) |
| `--pool` | `POOL_SIZE` | 5 | Warm contexts per lane. Sensible: 2–3× the concurrency limit. Bigger = warm identity inventory, not speed. |
| `--max-concurrent-headless` | `MAX_CONCURRENT_HEADLESS` | 20 | Non-interactive lane queue limit |
| `--max-concurrent-headful` | `MAX_CONCURRENT_HEADFUL` | `MAX_CONCURRENT` (3) | Interactive lane queue limit. **10 on 8 vCPU; keep low on small boxes** |
| `--timeout` | `TIMEOUT` | 45 | Solve deadline seconds. 45 lets Cloudflare's rare heavy-challenge variant finish instead of dying as `timeout` |
| `--port` | `PORT` | 6767 | API port |
| `--clear-cookies` | `CLEAR_COOKIES` | false | Wipe cookies after every solve (strict isolation) instead of keeping warm identities |
| `--headless` | `HEADLESS` | false | Legacy: `true` → headless mode |

---

## API

### `GET /solve?url=<site>&sitekey=<key>[&action=..&cdata=..&timeout=..]`

```json
{
  "success": true,
  "token": "1.ABCD...",
  "time": 3.42,
  "interactive": true,
  "lane": "headful",
  "escalated": true
}
```

### `GET /health`

```json
{"ok":true,"mode":"hybrid","pool_headless":50,"pool_headful":49,"interactive_sites":1}
```

Official test keys (`1x00000000000000000000AA` always passes) work — use one
solve against a test key as a **meaningful health check** (~2s).

---

## How to use it according to your load

| Your pattern | Do this | Expect |
|---|---|---|
| **Occasional single token** | `GET /solve` on demand | ~4s per token |
| **Steady trickle** (one every few seconds) | Just call `/solve` each time | each ~4s, never queues |
| **Bursts of 10–50** | Fire them all at once — the queue handles it | ~1 token/s; all succeed; first tokens in ~10s |
| **Massive floods (hundreds+)** | Fire away — queue absorbs everything | ~1 token/s sustained, ~100% accuracy |
| **Mostly non-interactive sites** | Nothing to change; hybrid sends them to the headless lane | 4.4 tokens/s |
| **Real-time app, latency critical** | Keep `MAX_CONCURRENT_HEADFUL` low (4–8) | each solve stays near solo speed |

**Hardware sizing** (interactive challenges, measured):

| vCPU | `MAX_CONCURRENT_HEADFUL` | Throughput |
|---|---|---|
| 4 | 3–5 | ~0.5/s |
| 8 | **10** | ~0.9/s (12+ collapses — measured) |
| 16 | ~15 (validate first) | ~1.5/s |

Do not raise limits above what the CPU can render: every extra simultaneous
page stretches *all* solves and eventually kills them. The queue is the
protection; the pool is not a speed dial.

---



## Reliability & self-healing

- **Browser crash** → next solve relaunches the browser and rebuilds the pool. One shared in-flight launch per lane (concurrent escalations can't spawn duplicate browsers).
- **Dead pooled context** → discarded automatically, a fresh one is taken.
- **Timeouts** → returned as `{"success":false,"err":"timeout"}` — retry; the rare heavy-challenge variant is why the default deadline is 45s.
- Escalation releases its headless slot before taking a headful slot — exactly one slot per request at any time.

## Monitoring

```bash
curl -s localhost:6767/health                      # pools, mode, learned sitekeys
curl -s "localhost:6767/solve?url=x&sitekey=1x00000000000000000000AA"   # ~2s health probe
pm2 logs turnstile-solver
```

## Troubleshooting

- **`Target page, context or browser has been closed` ~1–2s into every solve** — missing fonts (containers): install `fontconfig` + `fonts-dejavu-core` or run `npx playwright install-deps`, or point `FONTCONFIG_FILE` at a config listing your font dir.
- **Interactive challenges time out in pure headless** — expected; headless cannot pass them (verified against plain Playwright and rebrowser-patched drivers). Use hybrid/headful with Xvfb.
- **GPU aborts under Xvfb** — the launch args already include `--disable-gpu`; keep it.
- **Solves stretch to 15–20s+** — concurrency limit above the CPU's capacity; lower `MAX_CONCURRENT_HEADFUL`.
- **50 simultaneous requests → slow / failures** — never disable the queue; the no-queue result is 86% @ 21GB (measured).
- **First solve after restart ~6s** — the escalation learning step; subsequent solves for that site go direct.

## Measured limits (8 vCPU, 32GB, live Cloudflare)

- Interactive throughput ceiling: **~0.9 tokens/s** (CPU-bound; RAM/pool irrelevant — pool 50 and pool 1000 measured identical)
- Non-interactive: **4.4 tokens/s** at headless limit 20
- Both lanes at once contend for the same CPU: batch by challenge type for best totals
- Unqueued 50-wide: 43/50, 69s each, 21.6GB — the anti-pattern

License: MIT. Built on Playwright.
