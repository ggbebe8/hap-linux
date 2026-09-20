#!/usr/bin/env bash
set -euo pipefail
export AT_SPI_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS
export WAYLAND_DISPLAY=hap-test
export GDK_BACKEND=wayland GTK_A11Y=atspi
dbus-update-activation-environment AT_SPI_BUS_ADDRESS WAYLAND_DISPLAY GDK_BACKEND GTK_A11Y
if [[ ${WAYLAND_DEBUG:-} ]]; then
    dbus-update-activation-environment WAYLAND_DEBUG
fi
gnome-shell --headless --wayland --no-x11 --wayland-display=hap-test --virtual-monitor 1280x720 > "$HAP_TEST_DIR/shell.log" 2>&1 &
shell_pid=$!
trap 'kill "$shell_pid" 2>/dev/null || true; wait "$shell_pid" 2>/dev/null || true' EXIT
for _ in {1..60}; do
    [[ -S $XDG_RUNTIME_DIR/hap-test ]] && break
    kill -0 "$shell_pid" || { cat "$HAP_TEST_DIR/shell.log"; exit 1; }
    sleep .2
done
sleep 3
/usr/bin/python3 tests/integration.py
