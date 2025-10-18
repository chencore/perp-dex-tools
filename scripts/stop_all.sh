#!/usr/bin/env bash
# Stop all trading bot processes (runbot.py) launched from this repo
# Usage:
#   ./scripts/stop_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "Scanning for bot processes (runbot.py) under: $REPO_ROOT"

# Collect candidate PIDs by matching command line
mapfile -t CANDIDATES < <(pgrep -af "python[^ ]* .*runbot\.py" | awk '{print $1}' || true)

if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
  echo "No matching bot processes found by name."
else
  TO_KILL=()
  for pid in "${CANDIDATES[@]}"; do
    # Prefer Linux: verify process CWD belongs to this repo via /proc/<pid>/cwd
    if [[ -e "/proc/$pid/cwd" ]]; then
      cwd_path="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo '')"
      if [[ -n "$cwd_path" && "$cwd_path" == "$REPO_ROOT"* ]]; then
        TO_KILL+=("$pid")
      fi
    else
      # macOS fallback: no /proc. If cmdline contains runbot.py, accept (best-effort).
      TO_KILL+=("$pid")
    fi
  done

  if [[ ${#TO_KILL[@]} -eq 0 ]]; then
    echo "No processes matched within repo root ($REPO_ROOT)."
  else
    echo "Stopping PIDs: ${TO_KILL[*]}"
    kill "${TO_KILL[@]}" 2>/dev/null || true
    sleep 1
    # Force kill any survivors
    SURVIVORS=()
    for pid in "${TO_KILL[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        SURVIVORS+=("$pid")
      fi
    done
    if [[ ${#SURVIVORS[@]} -gt 0 ]]; then
      echo "Force stopping: ${SURVIVORS[*]}"
      kill -9 "${SURVIVORS[@]}" 2>/dev/null || true
    fi
  fi
fi

# Clean up common pid files
rm -f bot.pid bot_*.pid 2>/dev/null || true

echo "Done."
