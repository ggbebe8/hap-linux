#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
staging=0
if [[ ${1:-} == --stage ]]; then
    [[ $# == 2 && $2 == /* ]] || { echo 'Usage: ./install.sh --stage /absolute/path'; exit 2; }
    data_dir=$2
    staging=1
else
    [[ $# == 0 && $EUID != 0 ]] || { echo 'sudo 없이 ./install.sh를 실행하세요.'; exit 2; }
    data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
    missing=()
    for package in gnome-shell gjs libglib2.0-bin; do
        dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package")
    done
    if ((${#missing[@]})); then
        sudo apt-get update
        sudo apt-get install -y "${missing[@]}"
    fi
fi
[[ $data_dir == /* ]] || { echo '데이터 디렉터리는 절대 경로여야 합니다.'; exit 2; }
ext=$data_dir/gnome-shell/extensions/grid-click@local
mkdir -p "$ext/schemas"
cp extension/*.js extension/metadata.json extension/stylesheet.css "$ext/"
cp extension/schemas/*.xml "$ext/schemas/"
cp uninstall.sh "$ext/"
glib-compile-schemas --strict "$ext/schemas"
if ((staging)); then
    echo "Staged: $ext"
    exit 0
fi
gjs -c '
const {Gio} = imports.gi;
const settings = new Gio.Settings({schema_id: "org.gnome.shell"});
const enabled = settings.get_strv("enabled-extensions");
if (!enabled.includes("grid-click@local"))
    settings.set_strv("enabled-extensions", [...enabled, "grid-click@local"]);
Gio.Settings.sync();'
gnome-extensions enable grid-click@local 2>/dev/null || true
echo '설치 완료. 로그아웃 후 다시 로그인하고 Super+Shift+G를 누르세요.'
echo "삭제: $ext/uninstall.sh"
