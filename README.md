# Cloudflare Turnstile Solver

A fast, high-performance automated Cloudflare Turnstile token resolver built with Playwright and Express. Designed for local development and headless Linux / Ubuntu CLI servers.

---

## Features

- **Sub-2-second token resolution**: Uses target origin route interception to avoid downloading bloat from the target website.
- **Automated interactive challenge detection**: Listens for Cloudflare's `interactiveBegin` event and dispatches human-modeled mouse clicks.
- **Pre-warmed browser context pooling**: High throughput with reusable browser contexts and automatic cookie cleanup.
- **Headless & Headful with Xvfb**: Works seamlessly on headless Ubuntu CLI servers via `xvfb-run` without GUI/display popups.
- **Dual Interface**: Includes an embedded web UI dashboard and REST API endpoint.
- **PM2 Ready**: Includes `ecosystem.config.js` for 24/7 background service management.

---

## Getting Started

### 1. Install Dependencies
```bash
npm install
npx playwright install chromium
npx playwright install-deps
```

### 2. Start the Solver Server

```bash
# Standard launch:
npm start

# Or with virtual display (headless Linux servers, no desktop popups):
npm run start:xvfb

# Or directly:
./start.sh
```

---

## Configuration

You can configure the server via **CLI Flags**, **Environment Variables**, or **ecosystem.config.js**:

### 1. CLI Flags
```bash
node Turnstile_Solver.js --pool 10 --port 6767
./start.sh --pool 10
```

### 2. Environment Variables
| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `6767` | Port for the Express server to listen on |
| `POOL_SIZE` | `5` | Number of pre-warmed browser contexts in memory |
| `HEADLESS` | `false` | Set to `true` to force headless mode (default: false / headless OFF) |

### 3. PM2 Ecosystem File
Edit `POOL_SIZE` or `PORT` directly in `ecosystem.config.js`.

---

## API Usage

### Endpoint: `GET /solve`

**Parameters:**
- `url` (required): The target URL where the Turnstile challenge is used.
- `sitekey` (required): The Cloudflare Turnstile site key (`0x4AAAAAA...`).
- `timeout` (optional): Maximum seconds to wait (default: `30`).

**Example Request:**
```bash
curl -s "http://localhost:6767/solve?url=https://dashboard.proxyscrape.com/v2/login&sitekey=0x4AAAAAAAFWUVCKyusT9T8r"
```

**Example Response:**
```json
{
  "success": true,
  "token": "1.R7ndzAHG4U-ldkPbQYX7ppOv-g97N0iIy-hhA3YrQz8z1jPlJGI_ufjaUZeQfBNQ2AmKDvkzsYMvmk2GryHqsUPhRP812ggR464A2m28NAylYducdXtEa_G9d2oUnd2ksoCz8htS0pn6DpV04RZ5ywNV3EfBfI_2NUI9sYrmxOuBiu4Fs1olW9eX_p_caYZb_Ro9Z87rq535HAzuhG3y3OEdK0zg1iMcCRcMTMR5nUmzZuHxrz4llg3e5xhiqlRZuSqKw5Bti7JUU3YQw0RF3dpI6c7yBDf0LB_ZiAs3k24LvE-ijftvBG7PHRclPESvhEaDG7yLIQR2TshD2ChEwvjgemmGHcLft1Jkk-HLKsTTZpi1aQSgzUxh6-ryrnSEeUvXI7YVzOSsht4jvfJZNL1hYYY7GkHbensALi1EFvzJQ-Tf3mzv0os8cR2AD_ujI0i6WmFGfnwux54V1qqSCjJtZuOYnLtdKTW-xqaVYTdGSuyJCGR6LAJjp--bfGmHgF-U1w43Osd1vT5wRV4WheFwIMb-r4d2SJrCBzOnSFxNTvCzXUH-vIGMOhwxQj0tUm9AtD--nh6zdJvTlaw-uxy4-vxN0KCVr92fY-7eRf4nrBC5XFixNlYGVGwntl9k.k8aaAUNUMP0sdZnlom6OEw.eb6899a49bd7ac8a6cb04870efe0d46c7ef06cf9dd68bfb7a6df08928408cbd3",
  "time": 1.82
}
```

### Healthcheck: `GET /health`
```bash
curl -s http://localhost:6767/health
```
```json
{"ok": true, "pool": 5}
```

---

## Ubuntu Server Deployment (CLI / No GUI)

On a headless Ubuntu Server without a physical monitor or desktop:

```bash
# 1. Install Xvfb and Playwright dependencies
sudo apt-get update && sudo apt-get install -y xvfb
npx playwright install chromium
npx playwright install-deps

# 2. Install PM2
sudo npm install -g pm2

# 3. Start the service
pm2 start ecosystem.config.js

# 4. Enable auto-restart on reboot
pm2 startup
pm2 save
```

**PM2 Management Commands:**
```bash
pm2 logs turnstile-solver    # View real-time logs
pm2 status                  # Check process status
pm2 restart ecosystem.config.js # Restart service
pm2 stop turnstile-solver    # Stop service
```

---

## Full Flow: Harvest → Solve → Submit (`solve-flow.sh`)

The `/solve` API requires a sitekey, and a solved token only matters once it is
POSTed back to the target. Sites that use Turnstile sit behind Cloudflare, so
the page fetch before the solve and the form submit after it both need a
fingerprinted HTTP client — a plain `curl`/`requests` gets 403'd or
challenge-walled before the sitekey is ever visible.

`solve-flow.sh` chains the whole thing around the running solver API:

```
1. HARVEST  fetch the target page with a real browser TLS/HTTP2 fingerprint
            (tlsreq, Chrome 154) and extract the Turnstile sitekey
2. SOLVE    call this solver's /solve endpoint for a token
3. SUBMIT   POST the token to the target form on the same fingerprinted session
```

Requires `tlsreq` on PATH and the solver API running (default
`http://127.0.0.1:6767`).

```bash
# Just harvest + solve, print the token
./solve-flow.sh https://target.com/login

# Harvest → solve → submit with extra form fields and a clearance cookie
./solve-flow.sh https://target.com/login \
    --submit https://target.com/login \
    --data "username=me" --data "password=..." \
    --cookie "cf_clearance=..."

# Options
#   --submit URL      endpoint to POST the token to (prints token if omitted)
#   --field NAME      token form field (default: cf-turnstile-response)
#   --action/--cdata   forwarded to the solver
#   --profile P       tlsreq browser profile (default: chrome_154)
#   --solver URL      solver API base URL
#   --cookie k=v      cookie passed to harvest and submit (repeatable)
#   --data k=v        extra form fields for submit (repeatable)
#   --timeout N       solver timeout seconds
```

If the harvested page looks like a Cloudflare challenge instead of the real
page, the script warns and suggests solving the clearance first (see
[cloudflare-invisible-solver](https://github.com/nexus956/cloudflare-invisible-solver))
and passing `--cookie "cf_clearance=..."`.

---

## Performance & Reliability (solver core)

- **~3s warm solves** on interactive challenges (was a fixed 150ms CDP poll
  loop; token detection now polls inside the page every 100ms with no
  round-trip, and the tab is brought to front first).
- **Official test keys work**: Cloudflare's dummy token
  (`XXXX.DUMMY.TOKEN.XXXX`, 20 chars) previously failed the `>30` length
  check — the threshold is now `>= 20`.
- **Cookie retention (default)**: pooled contexts keep their
  `challenges.cloudflare.com` cookies between solves, so repeat solves skip
  straight past the interactive step. Use `--clear-cookies` / `CLEAR_COOKIES=true`
  to restore per-solve isolation.
- **Crash recovery**: if the browser process dies (OOM, GPU abort), the next
  solve relaunches it and rebuilds the pool automatically — the service no
  longer returns 500s until a manual restart.
- `--disable-gpu` is passed to Chromium: under Xvfb there is no real GLX, and
  without it the GPU process can take the whole browser down mid-challenge.

### Troubleshooting: page closes ~1-2s into every solve

The renderer aborts on first text draw when the container has **no fonts**:
logs show `SkFontMgr ... Not implemented` or repeated `TextRunHarfBuzz`
errors. Install `fontconfig` + `fonts-dejavu-core` (or run
`npx playwright install-deps`), or point `FONTCONFIG_FILE` at a config that
lists your font directory. Symptom without it: solves fail with
`Target page, context or browser has been closed` within two seconds.

---

## Hybrid mode (default): headless-first with on-demand escalation

Cloudflare's **interactive** challenges cannot be solved headless — verified
against plain Playwright *and* rebrowser-patched drivers (rebrowser 1.64 +
Chrome 156): the widget presents the challenge, the click is dispatched, and
no token is ever issued. Non-interactive (managed) challenges and the official
test keys pass headless in ~1.9s.

So the solver now runs in **hybrid** mode by default:

1. Every solve starts on the **headless lane** — fast, no display needed.
2. The moment a challenge turns interactive, the attempt is aborted and the
   solve is **escalated to the headful lane** (Xvfb), which passes it 100%.
3. The sitekey is remembered — subsequent solves for that site go **straight
   to headful**, no wasted headless attempt.
4. The headful browser launches **lazily** on first escalation. If your
   targets never serve interactive challenges, the headful lane (and its RAM)
   never exists.

Modes: `--mode headless | headful | hybrid` (env `MODE`, default `hybrid`).

**RAM (measured, POOL_SIZE=5):**

| State | Chromium RSS |
|---|---|
| Hybrid idle / non-interactive targets (headless lane only) | **~520 MB** |
| After first escalation (headful lane spawned) | ~1.2 GB |

That is the "less RAM, faster" answer for headless-capable targets: half the
memory of an always-headful setup, ~1.9s solves, and full interactive
capability kept in reserve. `/health` reports both pool sizes and the number
of interactive sitekeys learned.

**Note for deployments without a display:** the headless lane works with no
Xvfb at all; only the escalation lane needs one (`npm run start:xvfb`).

---

## Concurrency & queueing

Solve limits are **per lane** (requests beyond the limit **queue** and are
served in waves):

- `--max-concurrent-headless` (env `MAX_CONCURRENT_HEADLESS`, default **20**)
  — the headless lane (non-interactive challenges). Pages are ~5x lighter;
  measured 4.4 tokens/s at 20 concurrent on an 8-vCPU box.
- `--max-concurrent-headful` (env `MAX_CONCURRENT_HEADFUL`, default
  `MAX_CONCURRENT`, itself default **3**) — the headful lane (interactive
  challenges). CPU-bound: measured peak is 10 on 8 vCPU (15 and 20 are
  slower AND less accurate); keep it low on small boxes.

Do not raise limits without validating on your hardware. Above the box's real
capacity, every solve stretches and pages start dying. The queue exists so a
request burst degrades into a line — not a meltdown (measured: 50
simultaneous unqueued → 86% success, 21GB RAM; queued at the right limit →
100%, 2GB, and *faster overall*).
