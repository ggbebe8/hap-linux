#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
extension_uuid=touchgesture-overlay@local
extension_source="$project_dir/gnome-extension/$extension_uuid"
extension_target="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$extension_uuid"
activate=true
if [[ "${1:-}" == --no-enable && $# == 1 ]]; then
  activate=false
elif [[ $# != 0 ]]; then
  echo '사용법: ./install-overlay.sh [--no-enable]' >&2
  exit 2
fi
if [[ "$activate" == true ]]; then
  if ! command -v gnome-extensions >/dev/null; then
    echo 'GNOME Shell 확장 도구가 없습니다. GNOME 데스크톱에서 실행하세요.' >&2
    exit 1
  fi
  shell_version="$(gnome-shell --version)"
  case "$shell_version" in
    'GNOME Shell 50'|'GNOME Shell 50.'*) ;;
    *) echo "현재 지원 대상은 GNOME 50입니다: $shell_version" >&2; exit 1 ;;
  esac
fi
changed=false
existing=false
[[ -d "$extension_target" ]] && existing=true
mkdir -p "$extension_target"
for file in metadata.json extension.js stylesheet.css; do
  if ! cmp -s "$extension_source/$file" "$extension_target/$file"; then
    install -m 644 "$extension_source/$file" "$extension_target/$file"
    changed=true
  fi
done
if [[ "$activate" == false ]]; then
  printf '중앙 UI 확장 파일 설치: %s\n' "$extension_target"
  exit 0
fi
if ! gnome-extensions enable "$extension_uuid" 2>/dev/null; then
  # Newly copied extensions may only be discovered at the next Wayland login.
  python3 - "$extension_uuid" <<'PY'
import ast
import subprocess
import sys
value = subprocess.check_output(['gsettings','get','org.gnome.shell','enabled-extensions'],text=True).strip()
if value.startswith('@as '):
    value = value[4:]
enabled = ast.literal_eval(value)
if sys.argv[1] not in enabled:
    enabled.append(sys.argv[1])
    subprocess.run(['gsettings','set','org.gnome.shell','enabled-extensions',str(enabled)],check=True)
PY
fi
# Shell keeps imported extension code until logout, even after files are copied.
# Check the loaded version on every run, not only when files change.
installed_version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$extension_source/metadata.json")"
loaded_version="$(LC_ALL=C gnome-extensions info "$extension_uuid" 2>/dev/null | sed -n 's/^[[:space:]]*Version: //p' || true)"
if [[ -n "$loaded_version" && "$loaded_version" != "$installed_version" ]]; then
  printf '중앙 UI는 아직 이전 버전(%s)으로 실행 중입니다. 설치된 버전: %s\n' "$loaded_version" "$installed_version"
  echo '적용하려면 로그아웃 후 로그인하세요. 프로그램 재실행만으로는 확장이 바뀌지 않습니다.'
elif [[ "$existing" == true && "$changed" == true ]]; then
  echo '중앙 UI 확장을 업데이트했습니다. 새 코드를 적용하려면 로그아웃 후 로그인하세요.'
elif gdbus introspect --session --dest org.gnome.Shell --object-path /org/gnome/Shell/Extensions/Touchgesture 2>/dev/null | grep -q 'org.gnome.Shell.Extensions.Touchgesture'; then
  echo '중앙 UI 사용 준비 완료.'
else
  echo '중앙 UI 확장을 설치했습니다. 로그아웃 후 다시 로그인하면 활성화됩니다.'
  echo '로그인 후 ./try.sh --execute 를 실행하세요. 현재 세션에서는 UI가 안 보일 수 있습니다.'
fi
