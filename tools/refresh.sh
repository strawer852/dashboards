#!/usr/bin/env bash
# Cron entry point. Loads secrets, runs the refresh, appends to a rotating log.
set -euo pipefail

ROOT="$HOME/dashboards"
LOG="$ROOT/logs/refresh.log"
mkdir -p "$ROOT/logs"

# Keep the log bounded without needing logrotate or root.
if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 5242880 ]; then
  mv -f "$LOG" "$LOG.1"
fi

set -a
# shellcheck disable=SC1091
. "$ROOT/.env"
set +a

cd "$ROOT/macro"
exec "$ROOT/venv/bin/python" refresh.py "$@" >>"$LOG" 2>&1
