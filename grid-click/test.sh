#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
gjs -m tests/grid.test.js
gjs -c 'const {GLib}=imports.gi; for (const file of ARGV) {const [, bytes]=GLib.file_get_contents(file); Reflect.parse(new TextDecoder().decode(bytes), {target: "module"});}' extension/extension.js extension/grid.js tests/shell-driver.js
bash -n install.sh uninstall.sh test.sh integration.sh tests/session.sh
glib-compile-schemas --strict --dry-run extension/schemas
./install.sh --stage "$PWD/.build/stage"
echo 'All Grid Click local checks passed.'
