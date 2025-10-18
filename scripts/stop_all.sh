#!/usr/bin/env bash
# Stop all trading bot processes (runbot.py) launched from this repo
# Usage:
#   ./scripts/stop_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Scanning for bot processes (runbot.py) under: $REPO_ROOT"

# Find PIDs whose cmdline includes both repo root and runbot.py
PIDS=$(ps aux | grep -E "runbot\.py" | grep -F "$REPO_ROOT" | grep -v grep | awk '{print $2}' || true)

if [[ -z "${PIDS:-}" ]]; then
  echo "No matching bot processes found."
else
  for pid in $PIDS; do
    echo "Stopping PID=$pid"
    kill "$pid" 2>/dev/null || true
  done
  # Give them a moment, then force kill remaining
  sleep 1
  REMAIN=$(ps aux | awk '{print $2}' | grep -x -E "$(echo $PIDS | sed 's/ /|/g')" || true)
  if [[ -n "${REMAIN:-}" ]]; then
    echo "Force stopping: $REMAIN"
    kill -9 $REMAIN 2>/dev/null || true
  fi
fi

# Clean up common pid files
rm -f bot.pid bot_*.pid 2>/dev/null || true

echo "Done."
