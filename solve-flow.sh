#!/usr/bin/env bash
# solve-flow.sh — full Turnstile pipeline around the solver API:
#
#   1. HARVEST  fetch the target page with a real browser fingerprint (tlsreq)
#               and extract the Turnstile sitekey
#   2. SOLVE    call the local solver API (Turnstile_Solver.js) for a token
#   3. SUBMIT   (optional) POST the token to the target form/API on the same
#               fingerprinted session
#
# Why tlsreq for steps 1/3: sites that use Turnstile are behind Cloudflare,
# so a plain curl/wget/requests fetch of the page gets 403'd or challenge-
# walled before the sitekey is ever visible.
#
# Usage:
#   ./solve-flow.sh https://target.com/login
#   ./solve-flow.sh https://target.com/login --submit https://target.com/login \
#          --data "username=me" --data "password=s3cret" --cookie "cf_clearance=..."
#
# Requires: tlsreq on PATH, solver API running (default http://127.0.0.1:6767)

set -euo pipefail

TARGET=""
SUBMIT_URL=""
FIELD="cf-turnstile-response"
ACTION=""
CDATA=""
PROFILE="chrome_154"
SOLVER="http://127.0.0.1:6767"
TIMEOUT=""
declare -a COOKIES=() DATA=()

die() { echo "solve-flow: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --submit)   SUBMIT_URL="$2"; shift 2 ;;
        --field)    FIELD="$2"; shift 2 ;;
        --action)   ACTION="$2"; shift 2 ;;
        --cdata)    CDATA="$2"; shift 2 ;;
        --profile)  PROFILE="$2"; shift 2 ;;
        --solver)   SOLVER="$2"; shift 2 ;;
        --timeout)  TIMEOUT="$2"; shift 2 ;;
        --cookie)   COOKIES+=(-b "$2"); shift 2 ;;
        --data)     DATA+=("$2"); shift 2 ;;
        -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
        *)          [ -n "$TARGET" ] && die "unexpected argument: $1"; TARGET="$1"; shift ;;
    esac
done
[ -n "$TARGET" ] || die "missing target URL (see --help)"
command -v tlsreq >/dev/null || die "tlsreq not found on PATH"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# ── 1. HARVEST ────────────────────────────────────────────────────────────
echo "[1/3] fetching target with fingerprinted client ($PROFILE)..." >&2
tlsreq -p "$PROFILE" --max-time 30 ${COOKIES[@]+"${COOKIES[@]}"} "$TARGET" -o "$TMP/page.html" \
    || die "harvest fetch failed (is the target up / do you need --cookie cf_clearance=... ?)"

if grep -qiE 'just a moment|cf-chl|challenge-platform' "$TMP/page.html"; then
    echo "solve-flow: WARNING: page looks like a Cloudflare challenge, not the real page." >&2
    echo "  Solve the clearance first (cloudflare-invisible-solver) and pass" >&2
    echo "  --cookie \"cf_clearance=<value>\" to retry with the clearance." >&2
fi

SITEKEY=$(grep -oE 'data-sitekey="[^"]+"' "$TMP/page.html" | head -1 | cut -d'"' -f2)
[ -n "$SITEKEY" ] || SITEKEY=$(grep -oE "sitekey['\"]?\s*[:=]\s*['\"][0-9A-Za-zx]{20,}['\"]" "$TMP/page.html" \
                    | head -1 | grep -oE '[0-9A-Za-zx]{20,}' | head -1)
[ -n "$SITEKEY" ] || die "no Turnstile sitekey found in the page HTML"
echo "[1/3] sitekey: $SITEKEY" >&2

# ── 2. SOLVE ──────────────────────────────────────────────────────────────
echo "[2/3] requesting token from solver API..." >&2
API="$SOLVER/solve?url=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1],safe=""))' "$TARGET")&sitekey=$SITEKEY"
[ -n "$ACTION" ] && API="$API&action=$ACTION"
[ -n "$CDATA"  ] && API="$API&cdata=$CDATA"
[ -n "$TIMEOUT" ] && API="$API&timeout=$TIMEOUT"

if command -v curl >/dev/null; then
    RESP=$(curl -fsS --max-time 180 "$API") || die "solver API call failed"
else
    RESP=$(python3 -c "
import sys, urllib.request
print(urllib.request.urlopen(sys.argv[1], timeout=180).read().decode())" "$API") || die "solver API call failed"
fi

TOKEN=$(printf '%s' "$RESP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tok = d.get('token', '')
ok = bool(d.get('success') and tok)
print(tok)
sys.exit(0 if ok else 1)") || die "solver returned failure: $RESP"
[ -n "$TOKEN" ] || die "solver returned an empty token"
echo "[2/3] token: ${TOKEN:0:40}..." >&2

# ── 3. SUBMIT (optional) ──────────────────────────────────────────────────
if [ -n "$SUBMIT_URL" ]; then
    echo "[3/3] submitting token to $SUBMIT_URL..." >&2
    FORM="$FIELD=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$TOKEN")"
    for d in "${DATA[@]}"; do FORM="$FORM&$d"; done
    OUT=$(tlsreq -p "$PROFILE" --max-time 30 -X POST --form -d "$FORM" \
              ${COOKIES[@]+"${COOKIES[@]}"} "$SUBMIT_URL" -o "$TMP/submit.html" -v 2>&1) || die "submit failed"
    echo "$OUT" >&2
    cat "$TMP/submit.html"
else
    echo "[3/3] no --submit given; printing token" >&2
    printf '%s\n' "$TOKEN"
fi
