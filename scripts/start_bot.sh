#!/usr/bin/env bash
# Start trading bot in background and log output
# Usage:
#   ./scripts/start_bot.sh lighter ETH 0.01 0.02 40 450 5000
# Params:
#   $1 = EXCHANGE (e.g., lighter | extended | paradex ...)
#   $2 = TICKER (e.g., ETH)
#   $3 = QUANTITY (e.g., 0.01)
#   $4 = TAKE_PROFIT (percent, e.g., 0.02)
#   $5 = MAX_ORDERS (e.g., 40)
#   $6 = WAIT_TIME seconds (e.g., 450)
#   $7 = STOP_PRICE (e.g., 5000)
# Notes:
# - Loads .env from repo root if present
# - Writes logs to ./logs/
# - Stores PID in ./bot.pid

set -euo pipefail

# Repo root is parent of this script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

EXCHANGE="${1:-lighter}"
TICKER="${2:-ETH}"
QUANTITY="${3:-0.01}"
TAKE_PROFIT="${4:-0.02}"
MAX_ORDERS="${5:-40}"
WAIT_TIME="${6:-450}"
STOP_PRICE="${7:-5000}"

# Load .env if exists
if [[ -f .env ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | xargs -0 -I{} bash -c 'echo {}' 2>/dev/null | xargs)
fi

mkdir -p logs
LOG_FILE="logs/${EXCHANGE}_${TICKER}_$(date +%F_%H%M%S).log"
CMD=(python3 runbot.py \
  --exchange "$EXCHANGE" \
  --ticker "$TICKER" \
  --quantity "$QUANTITY" \
  --take-profit "$TAKE_PROFIT" \
  --max-orders "$MAX_ORDERS" \
  --wait-time "$WAIT_TIME" \
  --stop-price "$STOP_PRICE")

# Start in background with nohup, redirect stdout/stderr to log
nohup "${CMD[@]}" >>"$LOG_FILE" 2>&1 &
PID=$!
echo $PID > bot.pid

echo "Started bot (PID=$PID). Logs: $LOG_FILE"
