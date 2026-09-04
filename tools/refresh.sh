#!/usr/bin/env bash
# Cron entry point. Loads secrets, runs the refresh, appends to a rotating log.
set -euo pipefail

ROOT="$HOME/dashboards"
LOG="$ROOT/logs/refresh.log"
mkdir -p "$ROOT/logs"

# One refresh at a time. A manual run and a timer's would otherwise ingest
# concurrently against the same tables. Non-blocking: the next window is ten
# minutes away, so queueing buys nothing, but the skip is logged rather than
# silent -- a collision that looks like "nothing to do" is worse than one that
# says so. fd 9 survives the exec below (bash redirections are not
# close-on-exec), so the lock is held for the whole run, not just the shell.
exec 9>"$ROOT/logs/.refresh.lock"
if ! flock -n 9; then
  echo "$(date -u "+%Y-%m-%d %H:%M:%SZ")  refresh skipped: another run holds the lock" >>"$LOG"
  exit 0
fi

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
