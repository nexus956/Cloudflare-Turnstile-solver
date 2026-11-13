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
