#!/usr/bin/env bash
set -euo pipefail
# Paths can be overridden for staging installations without changing HOME.
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_prefix="${TOUCHGESTURE_PREFIX:-$HOME/.local}"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
manage_service=true
mode=preserve
for option in "$@"; do
  case "$option" in
    --no-systemd) manage_service=false ;;
    --dry-run) mode=dry-run ;;
    --execute) mode=execute ;;
    --help|-h)
      echo '사용법: ./install.sh [--dry-run|--execute] [--no-systemd]'
      echo '기본: 필요한 패키지와 권한 설정, 설치, 로그인 자동 실행. 새 설정은 실제 실행 모드.'
      echo '재설치 시 기존 설정 보존. --no-systemd: 시스템 설정/확장/자동 실행 없이 파일만 설치.'
      exit 0 ;;
    *) echo "알 수 없는 옵션: $option" >&2; exit 2 ;;
  esac
done
if [[ $(id -u) == 0 && "$manage_service" == true ]]; then
  echo 'sudo 없이 ./install.sh를 실행하세요. 필요한 단계에서만 비밀번호를 요청합니다.' >&2
  exit 1
fi
if [[ "$manage_service" == true ]]; then
  systemctl --user show-environment >/dev/null
  if ! command -v gnome-shell >/dev/null || [[ "$(gnome-shell --version)" != 'GNOME Shell 50'* ]]; then
    echo 'GNOME 50 데스크톱에서 실행하세요.' >&2
    exit 1
  fi
  packages=()
  for package in python3 python3-venv python3-evdev python3-yaml python3-dbus-next python3-setuptools python3-wheel acl; do
    if [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != 'install ok installed' ]]; then
      packages+=("$package")
    fi
  done
  if [[ ${#packages[@]} -gt 0 ]]; then
    sudo apt-get install -y "${packages[@]}"
  fi
fi
venv_dir="$install_prefix/share/touchgesture/venv"
launcher="$install_prefix/bin/touchgesture"
if [[ -e "$launcher" || -L "$launcher" ]]; then
  if [[ ! -L "$launcher" || "$(readlink "$launcher")" != "$venv_dir/bin/touchgesture" ]]; then
    echo "Refusing to replace unrelated file: $launcher" >&2
    exit 1
  fi
fi
mkdir -p "$install_prefix/bin" "$config_root/touchgesture" "$config_root/systemd/user"
if [[ "$manage_service" == true ]]; then
  # Ubuntu packages supply native evdev and other dependencies; no local C build.
  /usr/bin/python3 -m venv --system-site-packages "$venv_dir"
  "$venv_dir/bin/python" -m pip install --disable-pip-version-check --no-deps --no-build-isolation "$project_dir"
else
  python3 -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install --disable-pip-version-check "$project_dir"
fi
ln -sfn "$venv_dir/bin/touchgesture" "$launcher"
if [[ -e "$config_root/touchgesture/config.yaml" ]]; then
  "$launcher" --config "$config_root/touchgesture/config.yaml" --check-config
fi
"$venv_dir/bin/python" "$project_dir/scripts/configure-install.py" \
  "$project_dir/src/touchgesture/default.yaml" "$config_root/touchgesture/config.yaml" "$mode" "$manage_service"
python3 - "$project_dir/systemd/touchgesture.service" "$config_root/systemd/user/touchgesture.service" "$launcher" "$config_root/touchgesture/config.yaml" <<'PY'
from pathlib import Path
import sys
source, target, launcher, config = sys.argv[1:]
def quote(value):
    if any(c in value for c in '\n\r\x00'):
        raise SystemExit('Installation paths may not contain newlines')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
text = Path(source).read_text().replace('@EXEC_START@', quote(launcher) + ' --config ' + quote(config))
Path(target).write_text(text)
PY
"$launcher" --config "$config_root/touchgesture/config.yaml" --check-config
if [[ "$manage_service" == true ]]; then
  sudo bash "$project_dir/scripts/device-access.sh" install
  "$project_dir/install-overlay.sh"
  systemctl --user daemon-reload
  systemctl --user enable touchgesture.service
  systemctl --user reset-failed touchgesture.service || true
  systemctl --user restart touchgesture.service
  sleep 1
  if ! systemctl --user is-active --quiet touchgesture.service; then
    echo '서비스가 실행되지 않았습니다. 아래 로그를 확인하세요.' >&2
    journalctl --user -u touchgesture.service -n 20 --no-pager
    exit 1
  fi
fi
printf '설치 완료: %s\n설정 파일: %s\n' "$launcher" "$config_root/touchgesture/config.yaml"
if [[ "$manage_service" == true ]]; then
  echo '현재 실행 중이며, 다음 로그인부터 자동 실행합니다. try.sh는 동시에 실행하지 마세요.'
  echo '관리: systemctl --user status touchgesture / 삭제: ./uninstall.sh'
fi
