# Keyd Visual Mode

Surface / Ubuntu GNOME 50에서 `CapsLock + v`로 `caps_locked` 레이어를 켜면
**상단 바가 짙은 빨간색으로 바뀌고 오른쪽에 작은 `V`가 표시**됩니다.
레이어를 해제하면 원래 테마로 돌아갑니다. Dock은 변경하지 않습니다.

## 설치

데스크톱에 로그인한 사용자로 프로젝트 폴더에서 실행하세요. `sudo`는 사용하지 않습니다.

```bash
./install.sh
```

**처음 설치하거나 업데이트한 뒤에는 로그아웃 후 다시 로그인하세요.**
Wayland에서는 GNOME Shell을 세션 안에서 재시작할 수 없고,
이미 로드한 확장 코드는 캐시될 수 있습니다. 이후 로그인할 때 자동으로 켜집니다.

필요 조건: GNOME Shell 50, `gjs`, `gnome-extensions`, `keyd listen`을 지원하는 keyd,
GNU `timeout`. 현재 개발 환경은 GNOME 50.1 / keyd 2.6.0입니다.
설치 스크립트는 버전과 keyd 연결을 확인한 뒤 사용자 확장 디렉터리에 파일을 복사합니다.
패키지를 자동으로 설치하거나 시스템 권한을 바꾸지 않습니다.

설치 위치: `${XDG_DATA_HOME:-~/.local/share}/gnome-shell/extensions/keyd-visual-mode@local`.
같은 명령으로 업데이트할 수 있습니다. GNOME의 확장 전체 스위치가 꺼져 있다면
‘확장’ 앱에서 켜야 합니다.

## 사용

저장소의 `defualt.conf`에 있는 `caps_locked` 이름을 기준으로 동작합니다.
설치 스크립트는 이 파일이나 `/etc/keyd`를 수정하지 않습니다.
해당 키 매핑이 이미 keyd에 적용되어 있어야 합니다.

| 입력 / 상태 | 표시 |
| --- | --- |
| `CapsLock + v`로 고정 레이어 활성화 | 빨간 상단 바 + `V` |
| `Esc`, `v`, `CapsLock`으로 고정 레이어 해제 | 원래 상단 바, `V` 숨김 |
| CapsLock만 누르거나 `d` 보조 레이어 사용 | `caps_locked` 활성 여부에 따라서만 표시 |
| keyd 연결 오류 | 빨간색 해제 + 노란 `!` |

`!` 또는 `V`를 클릭하면 상태와 **keyd 다시 연결** 메뉴가 나옵니다.
확장이 시작할 때 keyd가 보내는 현재 레이어 목록도 처리합니다.
잠금 화면에서는 일반 사용자 확장이 비활성화되며, 잠금 해제 후 재연결합니다.
전체 화면 앱이 상단 바를 숨기면 이 표시도 보이지 않습니다.

## 배터리와 동작 방식

GNOME 확장이 `keyd listen` 프로세스 하나를 실행하고 비동기로 줄 입력을 기다립니다.
정상 연결 중에는 상태 확인 타이머, 반복 명령 실행, 애니메이션이 없습니다.
`+caps_locked` / `-caps_locked` 이벤트가 왔을 때만 스타일을 바꿉니다.
상주 메모리는 사용하지만 배터리 영향은 작을 것으로 예상합니다. 실제 전력 소비는 측정하지 않았습니다.

연결이 끊기면 원래 색으로 복원하고 1, 2, 4, 8, 16초 간격으로 최대 5번 재연결합니다.
확장을 켜거나 메뉴에서 재연결한 시점부터의 총 재시도 횟수이며, 소진 후에는 자동 재시도를 멈춥니다.
keyd가 다시 실행되었는데 `!`가 남으면 메뉴에서 재연결하세요.
확장을 끄거나 삭제하면 입력 대기, 재시도 타이머, 자식 프로세스를 정리합니다.

## 삭제

```bash
./uninstall.sh
```

확장을 끄고, 자동 활성화 목록과 설치 파일에서 이 확장만 제거합니다.
반복 실행해도 됩니다. keyd, keyd 설정, 다른 확장은 유지됩니다.
프로젝트 소스 폴더는 남습니다.

## 문제 해결

### 설치 시 keyd 연결 실패 / 노란 `!`

일반 사용자 터미널에서 다음 명령을 실행하세요.

```bash
keyd listen
```

연결되면 입력을 기다리며, 레이어를 켜고 끌 때 `+caps_locked`, `-caps_locked`가 나옵니다.
종료는 `Ctrl+C`입니다. 연결 오류라면 `systemctl status keyd`로 서비스 상태를 확인하세요.
`sudo keyd listen`만 되는 경우에는 keyd 소켓 접근 권한 문제입니다.
표준 keyd 설치는 `keyd` 그룹에 소켓 접근 권한을 부여합니다.
현재 사용자를 이 그룹에 추가하세요:

```bash
sudo usermod -aG keyd "$(id -un)"
```

**데스크톱에서 로그아웃한 뒤 다시 로그인하고 `./install.sh`를 실행하세요.**
터미널만 새로 열거나 `newgrp`를 실행하면 이미 실행 중인 GNOME Shell의 그룹 권한은 바뀌지 않습니다.
설치 후 새 확장을 불러오기 위해 한 번 더 재로그인이 필요할 수 있습니다.
소켓을 모든 사용자에게 개방하면 안 됩니다.
keyd 소켓은 상태 읽기 외에 키 매핑 변경에도 쓰이므로 설치 스크립트가 임의로 권한을 넓히지 않습니다.
이 그룹 권한은 keyd 자체의 사용자 설정이므로 확장 삭제 시에도 유지됩니다.
그룹 가입 후에도 실패하면 `id -nG`와 `ls -l /run/keyd.socket`으로 권한을 확인하세요.
서비스가 실행 중인데 소켓의 그룹이 `keyd`가 아니라면 `sudo systemctl restart keyd` 후 다시 확인하세요.

### 표시가 안 바뀜 / 남아 있음

- 로그아웃 후 다시 로그인했는지, 확장 앱에서 Keyd Visual Mode가 켜져 있는지 확인하세요.
- `keyd listen`에서 정확히 `caps_locked` 이벤트가 나오는지 확인하세요.
- 일부 테마/패널 확장의 인라인 스타일이 배경색보다 우선할 수 있습니다. 오른쪽 `V` 표시도 확인하세요.
- keyd 2.6.0의 `reload`는 레이어 초기화 알림을 보내지 않을 수 있습니다.
  `keyd reload` 후에는 `V` 메뉴의 **keyd 다시 연결** 또는 확장 껐다 켜기를 사용하세요.
- keyd의 알림에는 키보드 ID가 없습니다. 서로 다른 설정을 쓰는 여러 키보드의 독립 레이어 상태를
  구별하지 못합니다. 현재 노트북의 단일 설정 사용을 대상으로 합니다.

확장 상태와 로그:

```bash
gnome-extensions info keyd-visual-mode@local
journalctl -b /usr/bin/gnome-shell | rg 'Keyd|keyd-visual-mode'
```

### 색상 변경

`extension/stylesheet.css`의 `#782323`을 원하는 상단 바 색으로 바꾼 뒤
`./install.sh`를 다시 실행하고 재로그인하세요. 레이어 이름은 `extension/monitor.js`의
기본값 `caps_locked`에서 변경할 수 있습니다.

## 개발 검증

```bash
bash -n install.sh uninstall.sh
gjs -m tests/monitor.test.js
python3 tests/install.test.py
```

테스트는 모의 keyd 프로세스로 실제 비동기 입력, 시작 시 활성 상태, 중첩 레이어,
연결 종료, 재시도 제한, 정지 시 프로세스 종료를 검사합니다.
설치 테스트는 임시 디렉터리와 모의 명령을 사용해 반복 설치·삭제 및 다른 확장 설정 보존을 검사합니다.
테스트에는 `python3`도 필요합니다.
GNOME Shell 안에서의 실제 렌더링과 배터리 수치는 별도 확인이 필요합니다.

구현 참고: [keyd 소스](https://github.com/rvaiya/keyd/blob/f564288/src/daemon.c),
[GNOME 확장 개발 문서](https://gjs.guide/extensions/development/creating.html),
[Gio 비동기 프로세스](https://gjs.guide/guides/gio/subprocesses.html).
