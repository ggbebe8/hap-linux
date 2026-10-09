#!/usr/bin/env bash
set -euo pipefail
extension_uuid=touchgesture-overlay@local
extension_target="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$extension_uuid"
disable=true
if [[ "${1:-}" == --no-disable && $# == 1 ]]; then
  disable=false
elif [[ $# != 0 ]]; then
  echo '사용법: ./uninstall-overlay.sh [--no-disable]' >&2
  exit 2
fi
if [[ "$disable" == true ]] && command -v gnome-extensions >/dev/null; then
  gnome-extensions disable "$extension_uuid" 2>/dev/null || true
fi
# Only remove our own known extension files.
for file in metadata.json extension.js stylesheet.css; do
  rm -f -- "$extension_target/$file"
done
if [[ -d "$extension_target" ]]; then
  rmdir -- "$extension_target"
fi
echo '중앙 UI 확장을 제거했습니다.'
