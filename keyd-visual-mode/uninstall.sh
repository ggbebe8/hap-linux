#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
uuid='keyd-visual-mode@local'
target="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$uuid"
if (( EUID == 0 )); then
    echo 'sudo 없이 설치했던 사용자로 실행하세요.' >&2
    exit 1
fi
command -v gjs >/dev/null || { echo '삭제에 필요한 gjs를 찾을 수 없습니다.' >&2; exit 1; }
if command -v gnome-extensions >/dev/null; then
    gnome-extensions disable "$uuid" >/dev/null 2>&1 || true
fi
gjs -m scripts/extension-settings.js disable
rm -rf -- "$target"
echo 'Keyd Visual Mode 삭제 완료. keyd 설정은 변경하지 않았습니다.'
echo '화면에 표시가 남아 있다면 로그아웃 후 다시 로그인하세요.'
