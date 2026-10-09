#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_prefix="${TOUCHGESTURE_PREFIX:-$HOME/.local}"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
manage_service=true
purge=false
for option in "$@"; do
  case "$option" in
    --no-systemd) manage_service=false ;;
    --purge) purge=true ;;
    --help|-h)
      echo '사용법: ./uninstall.sh [--purge] [--no-systemd]'
      echo '기본: 서비스/앱/확장/자동 권한 설정 제거, 사용자 설정 보존.'
      echo '--purge: 설정과 설치기가 만든 설정 백업도 삭제.'
      exit 0 ;;
    *) echo "알 수 없는 옵션: $option" >&2; exit 2 ;;
  esac
done
if [[ $(id -u) == 0 && "$manage_service" == true ]]; then
  echo 'sudo 없이 ./uninstall.sh를 실행하세요.' >&2
  exit 1
fi
if [[ "$manage_service" == true ]]; then
  systemctl --user show-environment >/dev/null
  if [[ -e "$config_root/systemd/user/touchgesture.service" ]]; then
    systemctl --user disable --now touchgesture.service
  fi
  if [[ -e /etc/udev/rules.d/70-touchgesture-auto.rules || -e /etc/modules-load.d/touchgesture-auto.conf ]]; then
    sudo bash "$project_dir/scripts/device-access.sh" remove
  fi
fi
launcher="$install_prefix/bin/touchgesture"
venv_dir="$install_prefix/share/touchgesture/venv"
if [[ -L "$launcher" && "$(readlink "$launcher")" == "$venv_dir/bin/touchgesture" ]]; then
  rm -- "$launcher"
fi
rm -f -- "$config_root/systemd/user/touchgesture.service"
rm -rf -- "$venv_dir"
rmdir -- "$install_prefix/share/touchgesture" 2>/dev/null || true
if [[ "$manage_service" == true ]]; then
  systemctl --user daemon-reload
fi
if [[ "$manage_service" == true ]]; then
  "$project_dir/uninstall-overlay.sh"
fi
if [[ "$purge" == true ]]; then
  rm -f -- "$config_root/touchgesture/config.yaml"
  shopt -s nullglob
  backups=("$config_root/touchgesture/"config.yaml.[0-9]*.bak)
  if [[ ${#backups[@]} -gt 0 ]]; then
    rm -f -- "${backups[@]}"
  fi
  rmdir -- "$config_root/touchgesture" 2>/dev/null || true
  echo 'touchgesture와 설정을 삭제했습니다.'
else
  printf 'touchgesture 삭제 완료. 설정 보존: %s\n' "$config_root/touchgesture/config.yaml"
fi
echo '프로젝트 원본과 공용 Ubuntu 패키지는 유지됩니다.'
