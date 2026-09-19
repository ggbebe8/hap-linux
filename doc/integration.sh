#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
mkdir -p .build
export HAP_TEST_DIR
HAP_TEST_DIR=$(mktemp -d "$PWD/.build/integration.XXXXXX")
export XDG_RUNTIME_DIR=$HAP_TEST_DIR/runtime XDG_CONFIG_HOME=$HAP_TEST_DIR/config
export XDG_CACHE_HOME=$HAP_TEST_DIR/cache XDG_DATA_HOME=$HAP_TEST_DIR/data
export GSETTINGS_BACKEND=keyfile LIBGL_ALWAYS_SOFTWARE=1
export HAP_TEST_MARKER=$HAP_TEST_DIR/activated
mkdir -p "$XDG_RUNTIME_DIR" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
chmod 700 "$XDG_RUNTIME_DIR"
./install.sh --stage "$XDG_DATA_HOME"
cat tests/shell-driver.js >> "$XDG_DATA_HOME/gnome-shell/extensions/hap-linux@local/extension.js"
gsettings set org.gnome.shell enabled-extensions "['hap-linux@local']"
gsettings set org.gnome.desktop.interface toolkit-accessibility true
echo "Isolated integration logs: $HAP_TEST_DIR"
timeout 60s dbus-run-session --config-file=tests/session.conf -- bash scripts/integration-session.sh
