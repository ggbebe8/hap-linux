# HAP Linux

Ubuntu 26.04 / GNOME Shell 50 / Wayland용 Hunt-and-Peck 스타일 키보드 탐색 MVP입니다.
현재 활성 창의 접근성 트리에서 실행 가능한 요소를 찾아 힌트를 표시하고, 선택한 요소의 **AT-SPI Action**을 우선 실행합니다.
GTK 파일 목록처럼 열기 Action 없이 `listitem.scroll-to`만 제공하는 항목은 Shell의 Wayland 가상 포인터로 클릭합니다.

## 설치와 사용

현재 프로젝트 디렉터리(`doc`)에서 일반 사용자로 실행합니다.

```bash
./install.sh
```

필수 배포판 패키지가 없으면 스크립트가 `sudo apt-get`으로 설치합니다. 설치 스크립트 자체에는 `sudo`를 붙이지 마세요.
설치 후 **로그아웃하고 다시 로그인**합니다. Wayland 세션에서 GNOME Shell 확장을 처음 등록하거나 코드를 갱신할 때 필요한 절차입니다.

1. 탐색할 앱 창을 활성화합니다.
2. **Super+Shift+F**를 누릅니다. Super는 보통 Windows 키입니다.
3. 화면의 `A`, `S`, `D`, `F`, `J`, `K`, `L` 힌트를 입력합니다. 요소가 많으면 `AA`, `AS`처럼 여러 글자를 입력합니다. `AS`는 A 다음 S를 누릅니다. Enter는 필요 없습니다. 팝업에 현재 입력과 필요한 글자 수가 표시됩니다.
4. **Backspace**로 한 글자를 지우거나 **Esc**로 취소합니다. 오버레이에서 마우스를 눌러도 취소됩니다.

선택 즉시 오버레이와 키보드 grab을 해제하고 Action을 실행합니다. 창 이동·크기 변경·활성 창 전환·잠금 또는 25초 경과 시 취소됩니다.
동적으로 화면이 변경되었다면 Esc를 누르고 다시 탐색하세요.

## 구성과 설치 위치

| 구성 | 역할 | 설치 위치 |
| --- | --- | --- |
| `extension/` | 전역 단축키, 활성 창 정보, Shell 오버레이, 키보드 입력 | `$XDG_DATA_HOME/gnome-shell/extensions/hap-linux@local` |
| `hap/` | AT-SPI 탐색, 창 식별, Action 실행, 세션 D-Bus 서비스 | `$XDG_DATA_HOME/hap-linux` |
| D-Bus activation 파일 | 첫 단축키 사용 시 컨트롤러 자동 시작 | `$XDG_DATA_HOME/dbus-1/services/io.github.haplinux.Controller.service` |

`XDG_DATA_HOME` 기본값은 `~/.local/share`입니다. Python pip 패키지나 가상 환경, root 데몬은 필요하지 않습니다.
설치 시 `org.gnome.desktop.interface toolkit-accessibility`를 켜고 확장 활성화 목록에 HAP를 추가합니다.

필수 패키지: `python3`, `python3-gi`, `gir1.2-atspi-2.0`, `at-spi2-core`, `libglib2.0-bin`, `gnome-shell`.
통합 테스트에는 `gir1.2-gtk-4.0`, `gjs`, `dbus-daemon`, `dbus-bin`, `nautilus`도 필요합니다.

## 실행·진단

설치 후 컨트롤러는 자동으로 시작합니다. 설치하지 않고 Python 컨트롤러의 로그를 보려면 다음을 실행합니다.
이미 설치된 컨트롤러가 실행 중이면 로그아웃 후 개발용 컨트롤러를 먼저 실행하세요.

```bash
./run.sh
```

```bash
# 설치된 서비스 응답 확인 (필요 시 D-Bus가 자동 시작)
gdbus call --session --dest io.github.haplinux.Controller \
  --object-path /io/github/haplinux/Controller \
  --method io.github.haplinux.Controller.Ping

gnome-extensions info hap-linux@local
journalctl --user -b --no-pager | rg 'HAP|hap-linux|atspi|AT-SPI'
```

단축키 변경:

```bash
gsettings --schemadir "${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/hap-linux@local/schemas" \
  set org.gnome.shell.extensions.hap-linux show-hints "['<Super><Shift>h']"
```

단축키가 반응하지 않으면 GNOME 확장이 활성화되어 있는지, 전체 사용자 확장이 비활성화되어 있지 않은지 확인하세요.
GNOME 기본 입력기 전환과 겹치는 `Super+Shift+Space`는 피하세요.
요소가 없다고 나오면 접근성을 켠 후 해당 앱을 완전히 종료하고 다시 실행해 보세요. Chromium/Electron 계열은 접근성 트리를 켜야 합니다. Chromium은 `chromium --force-renderer-accessibility`, VSCode는 `code --force-renderer-accessibility`로 실행하거나 해당 옵션을 실행 프로필에 추가하세요. 이미 실행 중인 프로세스는 완전히 종료한 뒤 다시 시작해야 합니다.
샌드박스 앱은 접근성 버스가 허용되어야 합니다. Chromium/Electron 등은 접근성 트리 노출 여부가 실행 설정과 배포 방식에 따라 다릅니다.

## 테스트

```bash
./test.sh
./integration.sh
```

`test.sh`는 힌트 충돌·접두사, 좌표 clipping, 창 식별, Action 우선순위를 검사하고 Python/GJS 문법, GSettings 스키마, 스테이징 설치를 검증합니다.

`integration.sh`는 `.build/` 아래에 설치본·설정·런타임 디렉터리를 만들고 별도 D-Bus 세션과 **headless GNOME Wayland compositor**를 실행합니다.
GTK4 테스트 창을 탐색해 실제 버튼의 `clicked` 신호를 확인합니다. 테스트 전용 Shell 드라이버가 가상 키보드로 단축키·Esc·힌트 문자를 입력해 오버레이와 grab 해제까지 검증합니다.
Nautilus에서는 테스트용 빈 폴더의 힌트를 입력하고 실제 폴더가 열리는지도 확인합니다.
이 드라이버는 테스트용 복사본에만 추가되며 `install.sh`로 설치되는 확장에는 포함되지 않습니다.
테스트 D-Bus의 AppArmor 중재만 끄는 설정을 사용하며 시스템 AppArmor나 실제 사용자 버스 설정은 변경하지 않습니다.
로그는 실행 시 출력되는 `.build/integration.*/`와 표준 출력에 남습니다.

수동 확인할 항목: 다른 GTK/Qt/브라우저 앱, 다중 모니터, fractional scaling, 동일 제목의 여러 창, 전체 화면, 화면 잠금 후 복귀.

## 삭제

```bash
./uninstall.sh
# 또는 소스 폴더를 삭제한 경우
"${XDG_DATA_HOME:-$HOME/.local/share}/hap-linux/uninstall.sh"
```

삭제 후 로그아웃하면 실행 중이던 컨트롤러와 Shell 모듈도 종료됩니다. 다른 접근성 앱에 영향을 주지 않도록 시스템 접근성 설정은 유지합니다.

## MVP 범위와 제한

- 현재 활성 창만 대상으로 하며, PID와 창 제목·ACTIVE 상태로 연결합니다. 여러 후보를 구별하지 못하면 오류로 종료합니다.
- Button, Link, Menu, Tab 등에서 click, press, activate 등 실행 의미가 있는 Action을 우선 선택합니다. Electron/Chromium처럼 Action 대신 역할과 Component만 노출하는 앱은 버튼·링크·메뉴·탭·트리/목록 항목 등을 Wayland 가상 포인터로 보완합니다. 알 수 없는 첫 Action을 임의로 실행하지 않습니다. 비활성·숨김·창 밖 요소는 제외합니다.
- 열기 Action 없이 `listitem.scroll-to`를 제공하는 GTK 목록 항목에 한해 좌표 클릭을 사용합니다. Nautilus는 사용자의 한 번/두 번 클릭 설정을 따르고, 다른 앱은 한 번 클릭합니다. 실행 직전에 요소의 위치·이름·상태와 활성 창을 다시 확인합니다. Action이 없는 canvas·게임·일부 커스텀 UI에는 힌트를 제공하지 못합니다.
- Wayland에서 앱의 전역 좌표를 가정하지 않습니다. AT-SPI WINDOW 좌표를 창 크기로 정규화하고 Shell의 실제 창 위치로 변환합니다. 툴킷이 보고하는 창 영역과 Shell frame이 다르거나 서버 측 장식이 있는 경우 위치 오차가 날 수 있습니다.
- 한 번의 스냅샷에서 최대 4,000개 노드·500개 힌트를 처리합니다. 제한에 도달하면 `(일부)`를 표시합니다. 탐색 시간 제한은 약 4초이며 진행 중인 개별 AT-SPI 호출이 끝나는 시간은 추가될 수 있습니다.
- 동일한 위치에 있는 요소들의 힌트는 겹칠 수 있습니다. UI의 Action 자체가 지원하지 않는 기능은 실행할 수 없습니다.
- AT-SPI에 노출되지 않는 앱, 중복된 창 제목과 ACTIVE 정보 부재, 앱 재시작·창 내용 변경 등은 재탐색이 필요할 수 있습니다.
- GNOME 50만 지원 대상으로 선언했습니다. 다른 데스크톱과 X11 전용 도구는 사용하지 않습니다.

기술 조사와 설계 근거는 [docs/architecture.md](docs/architecture.md), 검증 기록은 [docs/verification.md](docs/verification.md)를 참고하세요.
