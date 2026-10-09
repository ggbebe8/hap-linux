#!/usr/bin/env bash
# One-command foreground test, without installing a service or user config.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
execute=false
debug=false
preview=true
rotation=auto
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) execute=true; shift ;;
    --no-preview) preview=false; shift ;;
    --debug) debug=true; shift ;;
    --rotation)
      case "${2:-}" in
        auto|0|90|180|270) rotation="$2"; shift 2 ;;
        *) echo '--rotation: auto, 0, 90, 180, 270 중 하나를 지정하세요.' >&2; exit 2 ;;
      esac ;;
    --help|-h)
      echo '사용법: ./try.sh [--execute] [--debug] [--no-preview] [--rotation auto|0|90|180|270]'
      echo '기본: GNOME 회전 자동 감지, 인식만 테스트. --execute: 실제 키 전송.'
      exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
  esac
done
if [[ $(id -u) == 0 ]]; then
  echo 'sudo 없이 ./try.sh로 실행하세요. 필요한 단계에서만 비밀번호를 요청합니다.' >&2
  exit 1
fi
if ! command -v udevadm >/dev/null; then
  echo 'udevadm이 없습니다. Ubuntu 터치스크린 PC의 터미널에서 실행하세요.' >&2
  exit 1
fi
candidates=()
shopt -s nullglob
for device in /dev/input/event*; do
  properties="$(udevadm info --query=property --name="$device" 2>/dev/null || true)"
  if [[ $'\n'"$properties"$'\n' == *$'\nID_INPUT_TOUCHSCREEN=1\n'* ]]; then
    candidates+=("$device")
  fi
done
if [[ ${#candidates[@]} == 0 ]]; then
  echo '터치스크린을 찾지 못했습니다. 실제 Ubuntu 터치스크린 PC에서 실행하세요.' >&2
  exit 1
fi
selected_device="${candidates[0]}"
if [[ ${#candidates[@]} -gt 1 ]]; then
  echo '테스트할 터치스크린을 선택하세요:'
  PS3='장치 번호: '
  select selected_device in "${candidates[@]}"; do
    [[ -n "$selected_device" ]] && break
  done
  [[ -n "$selected_device" ]] || exit 1
fi
# Prefer the already prepared project environment; otherwise use Ubuntu packages.
python_bin="$project_dir/.venv/bin/python"
packages=()
if [[ ! -x "$python_bin" ]] || ! "$python_bin" -c 'import evdev, yaml' 2>/dev/null; then
  python_bin=/usr/bin/python3
  if [[ ! -x "$python_bin" ]] || ! "$python_bin" -c 'import evdev, yaml' 2>/dev/null; then
    packages+=(python3 python3-evdev python3-yaml)
  fi
fi
if ! "$python_bin" -c 'import dbus_next' 2>/dev/null; then
  if [[ "$python_bin" == "$project_dir/.venv/bin/python" ]]; then
    "$python_bin" -m pip install 'dbus-next>=0.2.3,<0.3'
  else
    packages+=(python3-dbus-next)
  fi
fi
if ! command -v setfacl >/dev/null; then
  packages+=(acl)
fi
if [[ ${#packages[@]} -gt 0 ]]; then
  echo '빠른 테스트에 필요한 Ubuntu 패키지를 설치합니다.'
  sudo apt-get install -y "${packages[@]}"
fi
if [[ "$preview" == true ]]; then
  "$project_dir/install-overlay.sh" || echo '중앙 UI 설치를 확인하세요. 제스처 인식은 계속 실행합니다.' >&2
fi
if [[ ! -r "$selected_device" ]]; then
  sudo setfacl -m "u:$(id -u):r" "$selected_device"
fi
if [[ "$execute" == true ]]; then
  if [[ ! -e /dev/uinput ]]; then
    sudo modprobe uinput
  fi
  if [[ ! -w /dev/uinput ]]; then
    sudo setfacl -m "u:$(id -u):rw" /dev/uinput
  fi
  echo '실제 키 입력 모드: ↓→는 현재 앱에 Ctrl+W, ↑→는 Ctrl+Tab, ↑←는 Ctrl+Shift+Tab, 두 손가락 ↓는 Alt+F4를 보냅니다.'
else
  echo '인식 테스트 모드: 실제 키는 전송하지 않습니다.'
fi
printf '장치: %s | 종료: Ctrl+C\n' "$selected_device"
PYTHONPATH="$project_dir/src${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" - "$selected_device" "$execute" "$rotation" "$debug" "$preview" <<'PY'
from importlib.resources import files
from pathlib import Path
import sys
import tempfile
import yaml
from touchgesture.cli import main

config = yaml.safe_load(files('touchgesture').joinpath('default.yaml').read_text())
config['device']['path'] = sys.argv[1]
config['dry_run'] = sys.argv[2] != 'true'
config['device']['rotation'] = sys.argv[3]
config['preview'] = sys.argv[5] == 'true'
# Avoid requiring screen resolution setup for the first experiment.
config['recognition'].update(distance_mode='normalized', min_point_distance=.005,
                             simplify_epsilon=.015, min_segment_distance=.08,
                             min_total_distance=.18)
with tempfile.TemporaryDirectory(prefix='touchgesture-test-') as folder:
    path = Path(folder)/'config.yaml'
    path.write_text(yaml.safe_dump(config))
    options = ['--config', str(path)]
    if sys.argv[4] == 'true':
        options.append('--debug')
    raise SystemExit(main(options))
PY
