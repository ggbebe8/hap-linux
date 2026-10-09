#!/usr/bin/env bash
# Called through sudo by install.sh/uninstall.sh. Only these two owned files are managed.
set -euo pipefail
[[ $EUID == 0 ]] || { echo '관리자 권한이 필요합니다.' >&2; exit 1; }
operation="${1:-}"
[[ $# == 1 && ( "$operation" == install || "$operation" == remove ) ]] || exit 2
rules=/etc/udev/rules.d/70-touchgesture-auto.rules
module=/etc/modules-load.d/touchgesture-auto.conf
marker='# Managed by touchgesture installer'
for target in "$rules" "$module"; do
  if [[ -L "$target" || ( -e "$target" && "$(head -n 1 "$target")" != "$marker" ) ]]; then
    echo "다른 설정 파일을 덮어쓰거나 삭제하지 않습니다: $target" >&2
    exit 1
  fi
done
refresh_devices() {
  udevadm control --reload-rules
  udevadm trigger --action=change --subsystem-match=input --property-match=ID_INPUT_TOUCHSCREEN=1
  udevadm trigger --action=change --sysname-match=uinput
  udevadm settle
}
if [[ "$operation" == install ]]; then
  mkdir -p /etc/udev/rules.d /etc/modules-load.d
  cat > "$rules" <<'RULES'
# Managed by touchgesture installer
ACTION!="remove", SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_TOUCHSCREEN}=="1", TAG+="uaccess"
ACTION!="remove", SUBSYSTEM=="misc", KERNEL=="uinput", TAG+="uaccess"
RULES
  printf '%s\nuinput\n' "$marker" > "$module"
  chmod 644 "$rules" "$module"
  modprobe uinput
  refresh_devices
else
  had_rules=false
  [[ -f "$rules" ]] && had_rules=true
  rm -f -- "$rules" "$module"
  if [[ "$had_rules" == true ]]; then
    # Remove this user's live ACL left by our rules, then let other udev rules
    # reapply any independently granted access. No keyboard devices are touched.
    if [[ "${SUDO_UID:-}" =~ ^[0-9]+$ ]] && command -v setfacl >/dev/null; then
      shopt -s nullglob
      for device in /dev/input/event* /dev/uinput; do
        properties="$(udevadm info --query=property --name="$device" 2>/dev/null || true)"
        if [[ "$device" == /dev/uinput || $'\n'"$properties"$'\n' == *$'\nID_INPUT_TOUCHSCREEN=1\n'* ]]; then
          setfacl -x "u:$SUDO_UID" "$device" 2>/dev/null || true
        fi
      done
    fi
    refresh_devices
  fi
fi
