#!/usr/bin/env bash
set -euo pipefail
data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
gnome-extensions disable hap-linux@local 2>/dev/null || true
/usr/bin/python3 - <<'PY'
from gi.repository import Gio
s = Gio.Settings.new('org.gnome.shell')
s.set_strv('enabled-extensions', [x for x in s.get_strv('enabled-extensions') if x != 'hap-linux@local'])
Gio.Settings.sync()
PY
rm -f -- "$data_dir/dbus-1/services/io.github.haplinux.Controller.service"
rm -rf -- "$data_dir/gnome-shell/extensions/hap-linux@local" "$data_dir/hap-linux"
echo '삭제 완료. 실행 중인 컨트롤러와 Shell 모듈은 로그아웃할 때 종료됩니다.'
echo '다른 접근성 앱을 위해 toolkit-accessibility 설정은 유지했습니다.'
