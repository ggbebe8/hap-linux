# 기술 조사와 MVP 설계

조사일: 2026-09-18. 개발 환경에서 Ubuntu 26.04.1, GNOME Shell 50.1, GJS 1.88.0, Python 3.14.4 및 Atspi GI 바인딩을 확인했다.

## 기술 선택

일반 Wayland 클라이언트가 다른 앱의 창 위치를 조회하고 그 위에 임의의 전역 오버레이와 키보드 grab을 만드는 구조 대신 GNOME Shell 내부 확장을 사용한다.
전역 단축키는 `Main.wm.addKeybinding`, 활성 창은 `global.display.focus_window`, 힌트는 `St.Label`과 `Main.layoutManager.addTopChrome`, 입력은 `Main.pushModal`/`Main.popModal`로 처리한다.
GNOME 50.1의 실제 설치된 Shell GResource 소스와 [공식 GNOME Shell main.js](https://github.com/GNOME/gnome-shell/blob/50.1/js/ui/main.js)의 반환값·모달 생명주기를 확인했다.
`pushModal`은 boolean이 아닌 `Clutter.Grab`을 반환하므로 GNOME 50의 `is_revoked()`를 확인하고 같은 grab을 `popModal`에 넘긴다.
GNOME 50에서 제거된 `affectsInputRegion` 옵션과 `get_seat_state()` API는 사용하지 않는다.

Python은 PyGObject의 Atspi 2.0 바인딩을 사용한다. 별도 pyatspi·pip 패키지는 필요하지 않다.
[Atspi Accessible API](https://docs.gtk.org/atspi2/class.Accessible.html)로 트리, 상태, Component, Action 인터페이스를 조회한다.
[Atspi Action.do_action](https://docs.gtk.org/atspi2/method.Action.do_action.html)의 성공 여부를 확인해 실패를 사용자에게 알린다.

[Ubuntu 26.04 Component 문서](https://ubuntu.com/desktop/docs/en/26.04/reference/accessibility/dbus/org.a11y.atspi.Component/)는 SCREEN과 WINDOW 좌표계를 구분한다.
MVP는 WINDOW extents를 사용한다. 앱이 화면 전체 위치를 알아야 할 필요가 없고, Shell에서 알고 있는 활성 창 frame과 결합할 수 있다.
일반 Action 실행에는 마우스 위치를 사용하지 않는다. GTK 목록 클릭 보완 처리에는 동일한 좌표 변환을 사용한다.

RemoteDesktop portal을 통한 입력 에뮬레이션은 사용자의 별도 세션 승인과 입력 주입 관리가 필요하므로 MVP에는 넣지 않았다.
클릭/열기 Action 없이 `listitem.scroll-to`만 제공하는 GTK 목록 항목은 Shell 내부의 Clutter 가상 포인터로 클릭한다.
[GTK Action 구현](https://raw.githubusercontent.com/GNOME/gtk/4.22.0/gtk/a11y/gtkatspiaction.c)은 매개변수가 필요한 동작을 AT-SPI Action 목록에서 제외하므로, Action 인터페이스가 존재해도 열기를 제공한다는 뜻은 아니다.
알 수 없는 첫 Action을 실행하던 처리를 제거했다. 그 외 지원하지 않는 요소는 건너뛴다. X11 전용 xdotool·Xlib·wmctrl을 사용하지 않는다.

## 데이터 흐름

1. Shell 확장이 단축키 입력 시 활성 Meta.Window의 PID·제목·위치를 확보하고 모달 오버레이를 연다.
2. 세션 D-Bus `Scan(pid, title)` 호출이 설치된 Python 서비스를 자동 시작한다.
3. 단일 AT-SPI 작업 스레드가 PID에 해당하는 앱의 최상위 창을 식별하고 표시·활성 요소를 탐색한다.
4. 동일 길이의 접두사 충돌 없는 힌트와 정규화된 위치를 JSON으로 반환한다. Accessible 객체는 Python에 보관한다.
5. 키 입력으로 접두사를 좁힌다. 완성된 힌트를 선택하면 Shell 오버레이를 먼저 닫고 `Activate(session, label)`를 호출한다.
6. Python이 세션 소유자·만료·요소 상태·이름·Action·위치가 일치하는지 확인하고 Action을 한 번 실행한다.
7. 클릭 보완 대상은 `PrepareClick(session, label)`로 같은 검증을 거쳐 좌표만 반환한다. Shell이 활성 창·제목·위치가 유지되는지 확인하고 클릭한다. Nautilus에서는 클릭 설정을 따르며 다른 GTK 목록에서는 한 번 클릭한다. 버튼 해제를 포함한 보완 처리의 타이머는 새 탐색·확장 해제 시 정리한다.

GLib 메인 루프와 AT-SPI 스레드를 나눠 탐색 중에도 D-Bus Cancel에 응답한다. 동시에 여러 탐색을 대기열에 쌓지 않는다.
확장은 generation 번호로 취소 후 돌아온 오래된 응답을 무시한다. Python은 취소 이벤트로 탐색·실행을 차단한다.
탐색 중 일반 키는 앱으로 전달하지 않으며 Esc는 즉시 취소한다.

## 설치 결정

시스템 Python과 배포판 GI 패키지를 사용하고 사용자 데이터 디렉터리에만 프로그램·확장을 설치한다.
사용자 systemd 환경변수 동기화와 상시 실행 서비스 대신 세션 D-Bus activation을 사용한다.
소스 변경을 설치본이 자동 반영하지 않도록 복사 설치한다. 업데이트는 `./install.sh` 재실행 및 재로그인이다.
개발 중에는 실제 사용자 설치를 실행하지 않고 `.build/`에 스테이징하고 격리된 compositor에서 검증한다.
