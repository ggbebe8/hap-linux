#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ ${1:-} == --stage ]]; then
    [[ $# == 2 && $2 == /* ]] || { echo 'Usage: ./install.sh --stage /absolute/path'; exit 2; }
    data_dir=$2
    staging=1
else
    [[ $# == 0 ]] || { echo 'Usage: ./install.sh [--stage /absolute/path]'; exit 2; }
    [[ $EUID != 0 ]] || { echo 'sudo 없이 일반 사용자로 실행하세요.'; exit 1; }
    data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
    staging=0
    missing=()
    for package in python3 python3-gi gir1.2-atspi-2.0 at-spi2-core libglib2.0-bin gnome-shell; do
        dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package")
    done
    if ((${#missing[@]})); then
        sudo apt-get update
        sudo apt-get install -y "${missing[@]}"
    fi
fi
dest=$data_dir/hap-linux
ext=$data_dir/gnome-shell/extensions/hap-linux@local
mkdir -p "$dest/hap" "$ext/schemas" "$data_dir/dbus-1/services"
cp hap/*.py "$dest/hap/"
cp run.sh uninstall.sh "$dest/"
cp extension/extension.js extension/metadata.json extension/stylesheet.css "$ext/"
cp extension/schemas/*.xml "$ext/schemas/"
glib-compile-schemas --strict "$ext/schemas"
# Generate a quoted D-Bus Exec line even when the user's path contains spaces.
/usr/bin/python3 - "$dest" "$data_dir" <<'PY'
import pathlib, sys
dest, data = map(pathlib.Path, sys.argv[1:])
executable = str(dest / 'run.sh').replace('\\', '\\\\').replace('"', '\\"')
(data / 'dbus-1/services/io.github.haplinux.Controller.service').write_text(
    '[D-BUS Service]\nName=io.github.haplinux.Controller\nExec="' + executable + '"\n')
PY
if ((staging)); then
    echo "Staged: $data_dir"
    exit 0
fi
gsettings set org.gnome.desktop.interface toolkit-accessibility true
# Preserve other enabled extensions. A fresh Shell discovers this extension at login.
/usr/bin/python3 - <<'PY'
from gi.repository import Gio
s = Gio.Settings.new('org.gnome.shell')
extensions = list(s.get_strv('enabled-extensions'))
if 'hap-linux@local' not in extensions:
    s.set_strv('enabled-extensions', extensions + ['hap-linux@local'])
Gio.Settings.sync()
PY
gnome-extensions enable hap-linux@local 2>/dev/null || true
echo '설치 완료. 로그아웃 후 다시 로그인하고 Super+Shift+F를 누르세요.'
echo "삭제: $dest/uninstall.sh"
