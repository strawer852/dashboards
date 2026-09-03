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

install -m 644 "$SRC"/macro-refresh-*.service "$SRC"/macro-refresh-*.timer "$DEST/"
systemctl --user daemon-reload

for t in employment jolts sweep; do
  systemctl --user enable --now "macro-refresh-$t.timer"
done

systemctl --user list-timers 'macro-refresh-*' --all
