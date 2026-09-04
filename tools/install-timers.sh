#!/usr/bin/env bash
# Install the refresh timers as user units. Idempotent.
#
# User units, not system units: this repo runs entirely as `strawer` and needs
# no root. That requires lingering, so the user manager survives logout --
# without it the timers only run while a session is open.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../systemd" && pwd)"
DEST="$HOME/.config/systemd/user"
mkdir -p "$DEST"

loginctl enable-linger "$USER"

# Retire units the repo no longer carries. install(1) copies and never removes,
# so consolidating three timers into one would have left the old three enabled
# in ~/.config, still firing, with nothing in the repo describing them. The
# repo is the source of truth; anything installed and not in it is stale.
for f in "$DEST"/macro-refresh-*.timer; do
  [ -e "$f" ] || continue
  n="$(basename "$f" .timer)"
  if [ ! -e "$SRC/$n.timer" ]; then
    echo "retiring $n (no longer in the repo)"
    systemctl --user disable --now "$n.timer" 2>/dev/null || true
    rm -f "$DEST/$n.timer" "$DEST/$n.service"
  fi
done

install -m 644 "$SRC"/macro-refresh-*.service "$SRC"/macro-refresh-*.timer "$DEST/"
systemctl --user daemon-reload

# Enabled by name from the repo's own unit files, so adding one is adding a file.
for f in "$SRC"/macro-refresh-*.timer; do
  systemctl --user enable --now "$(basename "$f")"
done

systemctl --user list-timers 'macro-refresh-*' --all
