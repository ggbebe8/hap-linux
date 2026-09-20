#!/usr/bin/env bash
set -euo pipefail
export AT_SPI_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS
export WAYLAND_DISPLAY=grid-test GDK_BACKEND=wayland GTK_A11Y=none
dbus-update-activation-environment WAYLAND_DISPLAY GDK_BACKEND GTK_A11Y AT_SPI_BUS_ADDRESS
gnome-shell --headless --wayland --no-x11 --wayland-display=grid-test --virtual-monitor 1280x720 --virtual-monitor 1024x768 > "$GRID_TEST_DIR/shell.log" 2>&1 &
shell_pid=$!
trap 'kill "$shell_pid" 2>/dev/null || true; wait "$shell_pid" 2>/dev/null || true' EXIT
for _ in {1..60}; do
    [[ -S $XDG_RUNTIME_DIR/grid-test ]] && break
    kill -0 "$shell_pid" || { cat "$GRID_TEST_DIR/shell.log"; exit 1; }
    sleep .2
done
sleep 3
/usr/bin/python3 tests/integration.py
