# 검증 기록

## 2026-09-19 좌표 회귀 수정

파일 탐색기의 표시 좌표는 WINDOW 기준인데 클릭만 SCREEN 절대값을 사용하던 불일치를 제거했다.
VSCode 비최대화 창에서 접근성 루트 952×602와 보이는 창 920×560의 차이가 클라이언트 그림자 영역임을 실제 값과 화면으로 확인했다.
접근성 루트 크기와 일치하는 Shell 버퍼 영역을 선택하며, 힌트와 클릭은 같은 변환 함수를 사용한다.

- `./test.sh`: Python 테스트 15개, 실제 확장 좌표 변환 함수의 GJS 회귀 검사, 문법·스키마·스테이징 설치 통과.
- `HAP_TEST_CODE=1 ./integration.sh`: 종료 코드 0. 기존 GTK 버튼 실행·취소·힌트 입력 테스트 통과.
- Nautilus: 이웃 폴더 두 개를 둔 상태에서 지정한 폴더만 열리는지 확인했고, 클릭 포인터가 힌트 중심에 도달하는지 검사했다.
- VSCode: 격리된 프로필에서 창을 비최대화하고 이동·크기 변경 후 `Toggle Panel` 힌트 키를 입력했다. 클릭 위치가 표시 위치와 일치하고, 실제 Output 탭이 SHOWING 상태가 되는 것까지 확인했다.

실제 사용자 설치본은 변경하지 않았다. 적용은 `./install.sh` 실행 후 로그아웃·재로그인으로 한다.
추가 모니터와 fractional scaling은 별도 수동 검증 범위다.

## 초기 검증

2026-09-18, Ubuntu 26.04.1 / GNOME Shell 50.1 / GJS 1.88.0 / Python 3.14.4에서 실행했다.
실제 사용자 데이터 디렉터리에 설치하지 않고 현재 프로젝트의 `.build/`에 복사본을 만들었다.

## 자동 테스트 결과

`./test.sh`: 종료 코드 0.

- Python 단위 테스트 **10개 통과**: 힌트의 유일성·접두사 충돌, 좌표 clipping, 모호한 창 거부, Action 우선순위, 취소·위치 변경·요소 교체 시 실행 차단, Action 실패 처리.
- Python 컴파일, GJS 모듈 파싱, Bash 문법, GSettings strict 스키마 검사 통과.
- `install.sh --stage`로 Python 서비스·확장·D-Bus activation 파일 설치본 생성 성공.

`./integration.sh`: 종료 코드 0. GPU 없이 소프트웨어 렌더러를 쓰는 별도 GNOME 50.1 Wayland compositor와 GTK4 테스트 앱을 사용했다.

```text
PASS: real GTK4 Wayland scan (9 hints), disabled filtering, AT-SPI Action
PASS: replay rejected
PASS: cancellation rejected subsequent activation
PASS: real GNOME global shortcut, modal overlay (9 labels)
PASS: real Escape releases overlay and keyboard grab without action
PASS: prefix filtering and Backspace restores hints
PASS: real hint key -> overlay cleanup -> AT-SPI Action -> GTK clicked signal
```

컨트롤러를 미리 수동 시작하지 않아 D-Bus 자동 시작도 실제로 검증했다.
키 입력은 테스트 전용 확장 드라이버가 **격리된 compositor**에 만든 가상 키보드에서 발생시켰다.
Action 성공값만 검사한 것이 아니라 테스트 GTK 버튼의 `clicked` 핸들러가 만든 파일까지 확인했다.

## 실행 중 발견하고 수정한 문제

1. `Super+Shift+Space`가 GNOME 입력 소스 역방향 전환과 충돌하여 `Super+Shift+F`로 변경했다.
2. GNOME 50에서 삭제된 `addChrome`의 `affectsInputRegion` 옵션을 제거했다.
3. GNOME 50의 `Clutter.Grab`에는 `get_seat_state()`가 없어 `is_revoked()`로 변경했다.
4. GJS의 `Reflect.parse` 모듈 옵션은 `sourceType`이 아닌 `target`이므로 문법 검사기를 수정했다.
5. 테스트 샌드박스에서 기본 D-Bus의 AppArmor 정책 조회가 실패하여 테스트 전용 버스 설정을 사용했다. 시스템 정책은 변경하지 않았다.
6. 자동 시작 프로세스에 테스트 접근성 버스 환경이 전달되지 않아 `dbus-update-activation-environment`로 격리 세션에만 환경을 전달했다.

## 남아 있는 검증 범위

실제 로그인 세션의 수동 조작, 여러 앱·툴킷, 멀티 모니터·fractional scaling, 서버 측 창 장식, 화면 잠금은 별도 수동 확인 대상이다.
AT-SPI 접근성 트리 자체를 노출하지 않는 앱에는 자동 힌트를 제공할 수 없다. 모든 앱에서 동작한다고 보장하지 않는다.
격리된 Shell에는 PipeWire·Polkit·일부 portal이 없어 주변 서비스 경고가 발생하며, compositor 종료 시 Wayland 연결 종료 로그가 남는다.
이 경고와 구분하여 위 자동 테스트의 종료 코드와 GTK Action 결과를 확인했다.
