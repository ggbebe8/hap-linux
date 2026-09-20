#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m compileall -q hap tests
bash -n install.sh uninstall.sh run.sh test.sh integration.sh scripts/integration-session.sh
glib-compile-schemas --strict --dry-run extension/schemas
gjs scripts/check-js.js extension/extension.js
gjs scripts/test-geometry.js
./install.sh --stage "$PWD/.build/stage"
echo 'All local checks passed.'
