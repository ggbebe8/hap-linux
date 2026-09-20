#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
uuid='keyd-visual-mode@local'
target="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$uuid"

if (( EUID == 0 )); then
    echo 'sudo 없이 데스크톱에 로그인한 사용자로 실행하세요.' >&2
    exit 1
fi
for cmd in gnome-shell gnome-extensions gjs keyd timeout; do
    command -v "$cmd" >/dev/null || { echo "필요한 명령을 찾을 수 없습니다: $cmd" >&2; exit 1; }
done
version=$(gnome-shell --version)
if [[ ! $version =~ GNOME\ Shell\ 50([.]|$) ]]; then
    echo "이 확장은 GNOME 50용입니다. 현재 버전: $version" >&2
    exit 1
fi
for file in metadata.json extension.js monitor.js stylesheet.css; do
    [[ -r extension/$file ]] || { echo "누락된 파일: extension/$file" >&2; exit 1; }
done

echo 'keyd 연결 확인 중…'
# A healthy listener stays blocked; timeout terminates the probe after one second.
result=0
timeout 1s keyd listen >/dev/null || result=$?
if [[ $result != 124 ]]; then
    echo 'keyd listen 연결에 실패했습니다.' >&2
    if command -v systemctl >/dev/null && ! systemctl is-active --quiet keyd; then
        echo 'keyd 서비스가 실행 중인지 확인하세요: systemctl status keyd' >&2
        echo '서비스 시작: sudo systemctl start keyd' >&2
    elif command -v getent >/dev/null && getent group keyd >/dev/null; then
        keyd_gid=$(getent group keyd | cut -d: -f3)
        if [[ " $(id -G) " != *" $keyd_gid "* ]]; then
            echo '현재 로그인 세션에 keyd 그룹 권한이 없습니다.' >&2
            echo '사용자를 keyd 그룹에 추가하세요 (keyd 제어 권한 부여):' >&2
            printf '  sudo usermod -aG keyd %q\n' "$(id -un)" >&2
            echo '그다음 데스크톱에서 로그아웃 → 다시 로그인 → ./install.sh 를 실행하세요.' >&2
            echo '터미널만 다시 열거나 newgrp를 실행해도 GNOME Shell의 그룹 권한은 갱신되지 않습니다.' >&2
        else
            echo 'keyd 그룹 권한은 있습니다. 소켓 상태를 확인하세요: ls -l /run/keyd.socket' >&2
            echo '자세한 확인 방법은 README의 연결 오류 항목을 참고하세요.' >&2
        fi
    else
        echo 'keyd 그룹/서비스 설치 상태를 확인하세요. README의 연결 오류 항목을 참고하세요.' >&2
    fi
    exit 1
fi

# Disable the old instance before replacing its files.
gnome-extensions disable "$uuid" >/dev/null 2>&1 || true
mkdir -p -- "$target"
for file in metadata.json extension.js monitor.js stylesheet.css; do
    install -m 644 -- "extension/$file" "$target/$file"
done
gjs -m scripts/extension-settings.js enable
if gnome-extensions enable "$uuid" 2>/dev/null; then
    echo '확장 활성화를 요청했습니다.'
else
    echo '새 확장은 현재 GNOME 세션에서 아직 발견되지 않을 수 있습니다.'
fi
echo "설치 완료: $target"
echo '처음 설치하거나 업데이트했다면 로그아웃 후 다시 로그인하세요.'
echo 'CapsLock + v: 상단 바가 빨간색 / Esc 또는 v 또는 CapsLock: 원래 색'
