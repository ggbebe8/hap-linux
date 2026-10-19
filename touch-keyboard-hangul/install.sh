#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" == 0 ]]; then
    echo 'sudo 없이 일반 사용자로 실행하세요.' >&2
    exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
shell_version="$(gnome-shell --version)"
case "$shell_version" in
    'GNOME Shell 50'|'GNOME Shell 50.'*) ;;
    *)
        echo "이 확장은 GNOME 50용입니다. 현재 버전: $shell_version" >&2
        echo '다른 GNOME 버전은 호환성을 확인한 뒤 설치해야 합니다.' >&2
        exit 1
        ;;
esac

python3 -c 'from gi.repository import Gio'
case "$(dpkg-query -W -f='${Status}' ibus-hangul 2>/dev/null || true)" in
    'install ok installed') ;;
    *)
        echo '먼저 다음 명령으로 한글 입력기를 설치하세요: sudo apt install ibus-hangul' >&2
        exit 1
        ;;
esac

target_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/surface-hangul-key@local"
install -d "$target_dir"
install -m 644 "$script_dir/extension/metadata.json" "$script_dir/extension/extension.js" "$target_dir/"

python3 - <<'PY'
from gi.repository import Gio

uuid = 'surface-hangul-key@local'
settings = Gio.Settings.new('org.gnome.shell')
enabled = settings.get_strv('enabled-extensions')
if uuid not in enabled:
    if not settings.set_strv('enabled-extensions', enabled + [uuid]):
        raise SystemExit('확장 활성화 설정을 저장하지 못했습니다.')
disabled = settings.get_strv('disabled-extensions')
if uuid in disabled:
    if not settings.set_strv('disabled-extensions', [x for x in disabled if x != uuid]):
        raise SystemExit('확장 비활성화 목록을 갱신하지 못했습니다.')
Gio.Settings.sync()
sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
print('설치 완료. 작업을 저장하고 로그아웃한 뒤 다시 로그인하세요.')
if ('ibus', 'hangul') not in sources:
    print('설정 → 키보드 → 입력 소스에서 한국어(Hangul)를 추가하세요.')
print('입력 소스를 한국어(Hangul)로 선택하면 기본 화면 키보드에 한/영 키가 표시됩니다.')
PY
