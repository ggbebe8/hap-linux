#!/usr/bin/env bash
set -euo pipefail
data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
[[ $data_dir == /* ]] || { echo '데이터 디렉터리는 절대 경로여야 합니다.'; exit 2; }
gnome-extensions disable grid-click@local 2>/dev/null || true
gjs -c '
const {Gio} = imports.gi;
const settings = new Gio.Settings({schema_id: "org.gnome.shell"});
settings.set_strv("enabled-extensions", settings.get_strv("enabled-extensions").filter(x => x !== "grid-click@local"));
Gio.Settings.sync();'
rm -rf -- "$data_dir/gnome-shell/extensions/grid-click@local"
echo 'Grid Click 삭제 완료. 로그아웃 후 다시 로그인하세요.'
