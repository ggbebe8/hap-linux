# Ubuntu Touchscreen Gesture Daemon 구현 지시서

## 1. 목표

Ubuntu 26 + GNOME + Wayland 환경에서 **터치스크린 한 손가락 제스처**를 감지하여 사용자가 지정한 키 입력 또는 명령을 실행하는 작은 백그라운드 프로그램을 구현한다.

이번 1차 목표는 아래 두 제스처다.

- `↓→` : 손가락을 떼지 않고 아래로 이동한 뒤 오른쪽으로 이동
  - 기본 동작: 현재 브라우저 탭 닫기
  - 키 입력: `Ctrl+W`

- `↑→` : 손가락을 떼지 않고 위로 이동한 뒤 오른쪽으로 이동
  - 기본 동작: 오른쪽/다음 브라우저 탭으로 이동
  - 키 입력: `Ctrl+Tab`

중요:

- `↓→`는 대각선 `↘`이 아니다.
- `↑→`는 대각선 `↗`이 아니다.
- 반드시 **두 개의 연속된 방향 segment**를 가진 꺾인 경로로 판정해야 한다.
- 두 segment 사이에서 손가락을 떼면 안 된다.
- 향후 제스처를 설정 파일에서 자유롭게 추가/변경할 수 있어야 한다.

---

# 2. 개발 우선순위

아래 순서대로 구현한다.

## Phase 1 — 터치 이벤트 읽기

1. 사용 가능한 touchscreen input device 탐색
2. 한 손가락 touch down / move / up 이벤트 수신
3. 한 번의 touch stroke 동안 좌표 `(x, y, timestamp)` 저장
4. 디버그 모드에서 실시간 좌표와 최종 path 출력

예:

```text
TOUCH_DOWN x=713 y=421

MOVE x=712 y=470
MOVE x=714 y=530
MOVE x=718 y=603
MOVE x=760 y=606
MOVE x=830 y=609
MOVE x=910 y=611

TOUCH_UP

Detected path:
DOWN -> RIGHT
```

이 단계에서는 키 입력을 발생시키지 않아도 된다.

---

# 3. 핵심 제스처 정의

## 3.1 방향 표현

내부적으로 다음 4방향을 기본으로 사용한다.

```text
UP
DOWN
LEFT
RIGHT
```

필요하면 향후 8방향으로 확장할 수 있다.

```text
UP
UP_RIGHT
RIGHT
DOWN_RIGHT
DOWN
DOWN_LEFT
LEFT
UP_LEFT
```

하지만 1차 구현에서는 4방향 segment 방식이 우선이다.

---

## 3.2 원하는 경로

### Gesture A

```text
DOWN -> RIGHT
```

시각적으로:

```text
Start
  |
  |
  |
  +------->
           End
```

기본 action:

```text
Ctrl+W
```

---

### Gesture B

```text
UP -> RIGHT
```

시각적으로:

```text
  +------->
  |
  |
  |
Start
```

기본 action:

```text
Ctrl+Tab
```

---

# 4. 절대 하지 말아야 할 판정

다음 경로는 `DOWN -> RIGHT`로 인식하면 안 된다.

## 대각선

```text
\
 \
  \
```

즉:

```text
↘
```

는 `DOWN -> RIGHT`가 아니다.

---

다음처럼 거의 직선인 움직임도 제외한다.

```text
Start --------> End
```

다음처럼 아래로만 이동한 것도 제외한다.

```text
Start
  |
  |
  |
 End
```

---

# 5. Gesture Recognition 설계

터치 좌표 전체를 그대로 방향으로 변환하지 말고 다음과 같은 처리 단계를 사용한다.

```text
Raw points
    ↓
Noise filtering
    ↓
Path simplification
    ↓
Segment extraction
    ↓
Direction classification
    ↓
Gesture matching
```

---

# 6. Noise Filtering

터치스크린은 좌표에 작은 흔들림이 발생할 수 있다.

예:

```text
(500, 500)
(501, 504)
(499, 511)
(502, 522)
```

작은 좌우 흔들림 때문에

```text
DOWN
LEFT
RIGHT
DOWN
```

처럼 잘못 분리하면 안 된다.

따라서 minimum movement threshold를 둔다.

예:

```yaml
min_point_distance: 8
```

직전 유효 point와 거리가 8px 미만이면 무시한다.

화면 해상도에 따라 pixel 대신 normalized coordinate 사용도 검토한다.

추천:

```text
x_norm = x / screen_width
y_norm = y / screen_height
```

설정값도 화면 비율 기반으로 사용할 수 있게 설계하면 좋다.

---

# 7. Path Simplification

가능하면 Ramer-Douglas-Peucker 같은 polyline simplification 또는 유사한 간단한 알고리즘을 사용한다.

목표:

```text
수십~수백 개의 raw point
```

를

```text
Start
Corner
End
```

정도로 단순화한다.

예:

```text
Raw:

(500,200)
(501,220)
(500,245)
(502,270)
(503,300)
(510,310)
(540,311)
(580,309)
(620,310)

Simplified:

(500,200)
(503,300)
(620,310)
```

이 결과는:

```text
DOWN -> RIGHT
```

로 판정할 수 있다.

---

# 8. Segment 판정

두 점의 차이를 사용한다.

```text
dx = end.x - start.x
dy = end.y - start.y
```

기본 판정 예:

```text
abs(dx) > abs(dy) * dominance_ratio
    => horizontal

abs(dy) > abs(dx) * dominance_ratio
    => vertical
```

추천 초기값:

```yaml
dominance_ratio: 1.7
```

예:

```text
dx = +12
dy = +140

=> DOWN
```

```text
dx = +130
dy = +15

=> RIGHT
```

반대로:

```text
dx = +100
dy = +90
```

같은 경우는 방향성이 애매하므로 대각선/unknown 처리한다.

이것을 억지로 DOWN 또는 RIGHT로 분류하지 않는다.

---

# 9. Corner 판정

`DOWN -> RIGHT`는 실제로 방향 변화가 있어야 한다.

다음 조건을 권장한다.

```text
첫 segment:
  vertical dominance 만족
  minimum vertical distance 만족

두 번째 segment:
  horizontal dominance 만족
  minimum horizontal distance 만족
```

예시 초기값:

```yaml
min_segment_distance: 80
corner_min_angle_deg: 55
corner_max_angle_deg: 125
```

즉, 첫 segment와 두 번째 segment 사이 각도가 대략 직각이어야 한다.

너무 부드러운 대각선 곡선은 제외한다.

---

# 10. 제스처 종료

제스처는 기본적으로 `TOUCH_UP`에서 확정한다.

즉:

```text
TOUCH_DOWN
    ↓
trajectory recording
    ↓
TOUCH_UP
    ↓
gesture recognition
    ↓
action execution
```

초기 버전에서는 touch 중간에 바로 action을 실행하지 않는다.

오인식을 방지하기 위함이다.

---

# 11. 시간 조건

너무 느린 움직임은 일반 터치/스크롤 동작일 가능성이 있다.

설정:

```yaml
max_gesture_duration_ms: 1500
```

예:

```text
0 ~ 1500ms
```

내에서 완료된 stroke만 gesture 후보로 인정한다.

나중에 조정 가능하게 한다.

---

# 12. 최소 이동거리

작은 손 움직임으로 제스처가 실행되면 안 된다.

추천 초기값:

```yaml
min_segment_distance_px: 100
min_total_distance_px: 220
```

단, 실제 touchscreen 해상도에 따라 조정해야 한다.

가능하면 normalized distance 옵션도 제공한다.

예:

```yaml
distance_mode: normalized

min_segment_distance: 0.08
```

화면 높이/너비의 약 8% 수준을 의미한다.

---

# 13. Gesture configuration

제스처는 소스코드에 하드코딩하지 않는다.

사용자가 config file로 변경할 수 있게 한다.

추천 위치:

```text
~/.config/touchgesture/config.yaml
```

예:

```yaml
device:
  auto_detect: true

recognition:
  min_point_distance: 8
  dominance_ratio: 1.7
  min_segment_distance: 100
  min_total_distance: 220
  max_gesture_duration_ms: 1500
  corner_min_angle_deg: 55
  corner_max_angle_deg: 125

gestures:

  - name: close_tab
    sequence:
      - DOWN
      - RIGHT
    action:
      type: key
      keys:
        - CTRL
        - W

  - name: next_tab
    sequence:
      - UP
      - RIGHT
    action:
      type: key
      keys:
        - CTRL
        - TAB
```

---

# 14. 향후 확장 가능한 config 구조

아래처럼 자유롭게 확장할 수 있어야 한다.

```yaml
gestures:

  - name: previous_tab
    sequence:
      - UP
      - LEFT
    action:
      type: key
      keys:
        - CTRL
        - SHIFT
        - TAB

  - name: reopen_tab
    sequence:
      - DOWN
      - LEFT
    action:
      type: key
      keys:
        - CTRL
        - SHIFT
        - T

  - name: volume_up
    sequence:
      - RIGHT
      - UP
    action:
      type: command
      command: "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+"

  - name: volume_down
    sequence:
      - RIGHT
      - DOWN
    action:
      type: command
      command: "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"
```

---

# 15. Action 지원

최소 두 종류를 지원한다.

## Key action

예:

```yaml
action:
  type: key
  keys:
    - CTRL
    - W
```

---

## Command action

예:

```yaml
action:
  type: command
  command: "notify-send 'gesture detected'"
```

또는:

```yaml
action:
  type: command
  command: "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+"
```

---

# 16. Wayland 키 입력

Ubuntu 26 + GNOME + Wayland를 대상으로 한다.

X11 전용 방식에 의존하지 않는다.

다음 중 Wayland에서 실제 동작 가능한 방법을 조사 후 선택한다.

우선 후보:

```text
uinput
ydotool
직접 /dev/uinput 사용
```

가능하면 외부 프로그램 의존성을 최소화한다.

추천 우선순위:

```text
1. 직접 uinput 사용 가능 여부 검토
2. 너무 복잡하면 ydotool 활용
```

키 입력 backend는 인터페이스를 분리한다.

예:

```text
ActionExecutor
  ├── UInputExecutor
  └── YdotoolExecutor
```

향후 쉽게 교체할 수 있도록 한다.

---

# 17. 입력 장치 처리

`/dev/input/event*` 중 touchscreen을 찾아야 한다.

가능하면 다음 정보를 사용한다.

```text
EV_ABS
ABS_MT_POSITION_X
ABS_MT_POSITION_Y
BTN_TOUCH
INPUT_PROP_DIRECT
```

`INPUT_PROP_DIRECT`인 장치를 우선 touchscreen 후보로 판단한다.

터치패드와 혼동하지 않는다.

프로그램 시작 시 후보 device를 출력한다.

예:

```text
Detected touchscreen:

/dev/input/event12
Name:
  ELAN Touchscreen

Properties:
  INPUT_PROP_DIRECT

Resolution:
  X: 0 - 1920
  Y: 0 - 1200
```

---

# 18. Device 수동 지정

auto-detection이 실패할 수 있으므로 설정으로 지정할 수 있게 한다.

```yaml
device:
  auto_detect: false
  path: "/dev/input/event12"
```

또는 가능하면 device name 기반 지정도 지원한다.

```yaml
device:
  name_contains: "ELAN"
```

---

# 19. Multi-touch 처리

이번 버전은 one-finger gesture가 목적이다.

두 번째 touch contact가 감지되면 현재 gesture를 취소한다.

예:

```text
finger count > 1
    => cancel current gesture
```

향후 multi-touch gesture 기능을 추가할 수 있도록 구조는 확장 가능하게 작성한다.

---

# 20. 가장 중요한 문제: 일반 터치와 충돌

이 프로젝트의 핵심 난점이다.

한 손가락 터치는 GNOME/browser에서 원래 다음 용도로 사용된다.

```text
scroll
click
drag
selection
```

gesture daemon이 단순히 input event를 관찰하는 방식이면 브라우저가 동시에 원래 touch 이벤트를 받을 수 있다.

예:

```text
사용자 ↓→ 수행

gesture daemon:
  Ctrl+W 실행

browser:
  동시에 페이지 scroll
```

이 문제를 인지하고 설계해야 한다.

---

# 21. 1차 버전 정책

처음부터 input event interception까지 구현하지 않는다.

먼저 passive monitor 방식으로 동작시킨다.

즉:

```text
Touchscreen event
      ├── GNOME/browser
      └── gesture daemon
```

gesture daemon이 별도로 경로를 감지한다.

목표:

```text
제스처 인식 정확도 검증
```

---

# 22. 2차 버전에서 검토할 사항

제스처가 제대로 인식되는 것이 확인되면 아래 기능을 검토한다.

```text
Touch input grab
    ↓
gesture candidate 판단
    ↓
gesture면 consume
    ↓
gesture가 아니면 일반 touch 전달
```

가능한 기술:

```text
EVIOCGRAB
uinput virtual touchscreen
```

구조 예:

```text
Physical Touchscreen
       ↓
Gesture Proxy
       ↓
Virtual Touchscreen
       ↓
GNOME
```

Gesture Proxy가 실제 touchscreen을 grab하고 virtual touchscreen을 만들어 일반 이벤트는 재전송한다.

이 구조는 복잡도가 높으므로 **Phase 1에서는 구현하지 않는다.**

단, architecture 상 나중에 추가 가능하게 작성한다.

---

# 23. 오작동 방지

아래 경우 action을 실행하지 않는다.

### 너무 짧음

```text
total distance < threshold
```

### 너무 느림

```text
duration > max_gesture_duration
```

### 방향이 명확하지 않음

```text
UNKNOWN -> RIGHT
```

### 대각선

```text
DOWN_RIGHT
```

### corner가 없음

```text
DOWN
```

### segment가 너무 많음

```text
DOWN -> RIGHT -> DOWN -> LEFT
```

설정된 exact sequence matching을 기본으로 한다.

---

# 24. Gesture matching

내부적으로 다음 형태로 변환한다.

```text
[DOWN, RIGHT]
```

config:

```text
[DOWN, RIGHT]
```

와 정확히 비교한다.

추후 필요하면 fuzzy matching을 추가할 수 있다.

하지만 최초 버전에서는 exact matching 위주로 작성한다.

---

# 25. Debug mode

반드시 제공한다.

실행 예:

```bash
touchgesture --debug
```

출력:

```text
Device: ELAN Touchscreen

Touch started
Start: (542, 311)

Segment 1:
  dx=9
  dy=221
  direction=DOWN

Segment 2:
  dx=260
  dy=14
  direction=RIGHT

Sequence:
  DOWN -> RIGHT

Matched gesture:
  close_tab

Executing:
  CTRL+W
```

gesture recognition을 튜닝하기 위해 중요하다.

---

# 26. Dry-run

action을 실행하지 않고 인식 결과만 확인하는 옵션을 추가한다.

```bash
touchgesture --dry-run
```

예:

```text
Detected:
DOWN -> RIGHT

Matched:
close_tab

Action:
CTRL+W

DRY RUN — action skipped
```

---

# 27. Device list command

가능하면 다음 명령을 제공한다.

```bash
touchgesture --list-devices
```

출력:

```text
[0] ELAN Touchscreen
    /dev/input/event12
    touchscreen: yes

[1] ELAN Touchpad
    /dev/input/event7
    touchscreen: no
```

---

# 28. Config check

다음 명령도 가능하면 제공한다.

```bash
touchgesture --check-config
```

잘못된 설정이면:

```text
ERROR:

gesture "close_tab"
unknown direction:
DOWM

Did you mean:
DOWN
```

---

# 29. 로그

기본 실행 시 로그는 최소화한다.

정상 상태:

```text
touchgesture started
Device: ELAN Touchscreen
Loaded gestures: 2
```

action 발생 시:

```text
Gesture: DOWN -> RIGHT
Action: close_tab
```

---

# 30. systemd user service

최종적으로 로그인하면 자동 실행되게 한다.

예:

```text
~/.config/systemd/user/touchgesture.service
```

예시:

```ini
[Unit]
Description=Touchscreen Gesture Daemon
After=graphical-session.target

[Service]
ExecStart=%h/.local/bin/touchgesture
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
```

설치 스크립트에서 가능하면 자동으로 생성한다.

---

# 31. 설치 구조

추천:

```text
touchgesture/
├── README.md
├── LICENSE
├── config.example.yaml
├── install.sh
├── uninstall.sh
├── src/
└── systemd/
    └── touchgesture.service
```

설치 후:

```text
~/.local/bin/touchgesture
~/.config/touchgesture/config.yaml
~/.config/systemd/user/touchgesture.service
```

---

# 32. 제거

쉽게 지울 수 있어야 한다.

```bash
./uninstall.sh
```

수행:

```text
systemctl --user disable --now touchgesture

remove:
~/.local/bin/touchgesture

remove service:
~/.config/systemd/user/touchgesture.service
```

config는 사용자에게 물어보거나 기본적으로 보존한다.

---

# 33. 구현 언어

우선 시스템에서 안정적으로 동작하는 언어를 선택한다.

추천:

```text
Rust
```

이유:

```text
evdev
uinput
daemon
low-level input
```

처리에 적합하다.

다만 빠른 프로토타입을 위해 Python을 사용하는 것도 허용한다.

Python을 사용할 경우:

```text
python-evdev
```

등을 검토한다.

중요한 것은 언어보다 실제 Ubuntu 26 + Wayland에서 안정적으로 동작하는 것이다.

---

# 34. Codex 작업 지침

작업을 한 번에 너무 크게 하지 않는다.

다음 milestone 단위로 진행한다.

---

## Milestone 1

Touchscreen event reader

목표:

```text
touch down
move
touch up
```

좌표 출력.

완료 조건:

```text
실제 touchscreen을 손가락으로 움직이면
좌표가 CLI에 표시됨.
```

---

## Milestone 2

Stroke recorder

한 번의 touch stroke를 배열로 저장.

예:

```text
[
  (500,200),
  (501,250),
  (502,300),
  (550,303),
  (600,305)
]
```

---

## Milestone 3

Gesture recognizer

아래를 구분한다.

```text
DOWN -> RIGHT
UP -> RIGHT
DOWN
RIGHT
diagonal
unknown
```

---

## Milestone 4

Dry-run

```text
↓→
```

수행 시:

```text
Matched: close_tab
```

출력.

---

## Milestone 5

Key action

```text
DOWN -> RIGHT
```

발생 시:

```text
Ctrl+W
```

실행.

```text
UP -> RIGHT
```

발생 시:

```text
Ctrl+Tab
```

실행.

---

## Milestone 6

YAML config

제스처와 action을 config에서 로드.

소스코드 수정 없이 변경 가능해야 한다.

---

## Milestone 7

systemd user service

로그인 시 자동 실행.

---

# 35. 초기 acceptance test

## Test 1

동작:

```text
손가락을 아래로 충분히 내림
손을 떼지 않음
오른쪽으로 충분히 이동
손을 뗌
```

예상:

```text
Ctrl+W
```

---

## Test 2

동작:

```text
손가락을 위로 충분히 이동
손을 떼지 않음
오른쪽으로 충분히 이동
손을 뗌
```

예상:

```text
Ctrl+Tab
```

---

## Test 3

동작:

```text
↘ 대각선
```

예상:

```text
아무 동작 없음
```

---

## Test 4

동작:

```text
↓
```

예상:

```text
아무 동작 없음
```

---

## Test 5

동작:

```text
→
```

예상:

```text
아무 동작 없음
```

---

## Test 6

동작:

```text
짧은 ↓→
```

예상:

```text
아무 동작 없음
```

---

# 36. 첫 실행 시 안전 설정

초기 default config에서는 가능하면 action 실행을 끈다.

예:

```yaml
dry_run: true
```

사용자가 인식 정확도를 확인한 뒤:

```yaml
dry_run: false
```

로 바꿀 수 있도록 한다.

이유:

```text
Ctrl+W
```

는 실제 탭을 닫기 때문에 초기 튜닝 과정에서 오작동하면 불편하다.

---

# 37. 브라우저 한정 여부

1차 버전에서는 특정 앱 감지를 필수 요구사항으로 하지 않는다.

즉:

```text
DOWN -> RIGHT
```

가 발생하면 foreground application과 관계없이 `Ctrl+W`가 실행될 수 있다.

단, architecture 상 다음 기능을 향후 추가할 수 있게 한다.

```yaml
application:
  only:
    - firefox
    - chromium
    - google-chrome
```

Wayland에서는 foreground app 식별 방법이 제한될 수 있으므로 이 기능을 1차 구현 blocker로 만들지 않는다.

---

# 38. 향후 확장

다음 기능을 고려하되 최초 버전에는 넣지 않아도 된다.

```text
3 segment gesture

DOWN -> RIGHT -> UP
```

```text
edge gesture

RIGHT_EDGE -> LEFT
```

```text
hold gesture

HOLD -> RIGHT
```

```text
multi-touch

2 fingers:
LEFT
```

```text
per-application mapping
```

```text
GUI configuration
```

GUI는 매우 후순위다.

먼저 안정적인 daemon + YAML을 완성한다.

---

# 39. 성능 목표

daemon은 항상 실행되므로 다음을 지향한다.

```text
CPU idle:
거의 0%

memory:
최소 수준

polling:
busy loop 금지
```

input event 기반 blocking 방식 사용.

---

# 40. 권한

`/dev/input/event*`와 `/dev/uinput` 접근 권한이 필요할 수 있다.

필요 권한을 최소화하고 README에 정확한 설정 방법을 작성한다.

가능하면 프로그램 자체를 root로 실행하지 않는다.

예:

```text
input group
udev rule
uinput permission
```

등의 방식을 검토한다.

단, 보안상 과도하게 넓은 권한을 주지 않는다.

특히:

```text
chmod 777 /dev/input/*
```

같은 방법은 사용하지 않는다.

---

# 41. README에 반드시 포함

다음 내용을 작성한다.

```text
지원 환경

Ubuntu 26
GNOME
Wayland
Touchscreen
```

설치 방법

실행 방법

device 확인 방법

debug 방법

dry-run 방법

config 변경 방법

systemd 등록 방법

제거 방법

permission 문제 해결 방법

일반 touch와 gesture가 동시에 전달될 수 있다는 현재 제한사항
```

---

# 42. 중요 설계 원칙

## 제스처 엔진과 action 엔진 분리

다음 구조를 유지한다.

```text
Input
 ↓
Stroke Recorder
 ↓
Gesture Recognizer
 ↓
Gesture Name
 ↓
Action Mapper
 ↓
Action Executor
```

예:

```text
DOWN -> RIGHT
     ↓
close_tab
     ↓
CTRL+W
```

recognizer가 직접 `Ctrl+W`를 호출하지 않도록 한다.

---

# 43. 추천 내부 모델

예:

```text
TouchPoint
  x
  y
  timestamp

Stroke
  points[]

Segment
  start
  end
  direction
  distance
  angle

Gesture
  sequence[]

GestureConfig
  name
  sequence
  action
```

---

# 44. 테스트 가능한 구조

hardware input 부분과 gesture recognition 부분을 분리한다.

gesture recognizer는 실제 touchscreen 없이도 unit test 가능해야 한다.

예:

```text
input:

(0,0)
(0,100)
(100,100)

expected:

DOWN -> RIGHT
```

다음 테스트도 작성한다.

```text
diagonal
noise
short stroke
slow stroke
multiple corners
```

---

# 45. 테스트 샘플

### DOWN -> RIGHT

```text
[
  (500,100),
  (503,150),
  (501,220),
  (502,300),
  (550,302),
  (630,303),
  (720,305)
]
```

expected:

```text
DOWN -> RIGHT
```

---

### UP -> RIGHT

```text
[
  (500,500),
  (502,430),
  (501,350),
  (503,280),
  (560,282),
  (640,280),
  (720,281)
]
```

expected:

```text
UP -> RIGHT
```

---

### diagonal

```text
[
  (500,100),
  (550,150),
  (600,200),
  (650,250)
]
```

expected:

```text
UNKNOWN
```

또는:

```text
DIAGONAL
```

절대로:

```text
DOWN -> RIGHT
```

가 되면 안 된다.

---

# 46. 완료 기준

프로젝트의 1차 완료 기준:

1. Ubuntu 26 + Wayland에서 실제 touchscreen event 감지
2. 한 손가락 stroke 추적
3. `DOWN -> RIGHT` 정확히 인식
4. `UP -> RIGHT` 정확히 인식
5. 대각선과 구분
6. YAML config 지원
7. key action 지원
8. command action 지원
9. debug mode
10. dry-run mode
11. systemd user service
12. 설치/삭제 스크립트
13. README 작성
14. unit test 작성

---

# 47. 최우선 성공 시나리오

Firefox 또는 Chromium 계열 브라우저에서:

```text
손가락 ↓→
```

하면:

```text
현재 탭 닫힘
```

그리고:

```text
손가락 ↑→
```

하면:

```text
오른쪽 탭으로 이동
```

---

# 48. 개발 중 사용자에게 확인할 정보

가능하면 프로그램이 직접 진단 정보를 출력하도록 한다.

아래 명령들의 결과를 확인할 수 있게 한다.

```bash
echo $XDG_SESSION_TYPE
```

예상:

```text
wayland
```

그리고 touchscreen 장치 식별.

가능하면 아래 도구를 활용한다.

```bash
libinput list-devices
```

또는:

```bash
sudo libinput debug-events
```

단, 사용자가 수동으로 장치 번호를 찾지 않아도 되도록 auto detection을 우선 구현한다.

---

# 49. 작업 방식

Codex는 먼저 현재 프로젝트 디렉터리를 확인하고, 기존 파일이 없다면 새 프로젝트를 생성한다.

불필요하게 복잡한 GUI를 만들지 않는다.

우선:

```text
CLI
daemon
YAML
systemd
```

에 집중한다.

각 milestone 완료 후 직접 실행 가능한 상태를 유지한다.

테스트되지 않은 거대한 코드를 한 번에 작성하지 않는다.

---

# 50. 최종 방향

이 프로젝트의 목적은 단순히 두 개의 shortcut을 만드는 것이 아니다.

최종적으로는 다음과 같은 **사용자 정의 touchscreen gesture engine**을 만드는 것이다.

```text
손가락으로 경로 입력

↓→
↑→
↑←
↓←
→↑
→↓

        ↓

사용자 정의 action

keyboard shortcut
shell command
application launch
volume
browser control
window control
```

단, 최초 버전에서는 반드시 다음 두 개부터 안정화한다.

```text
DOWN -> RIGHT
    => Ctrl+W

UP -> RIGHT
    => Ctrl+Tab
```

이 두 동작의 인식 정확도가 충분히 확보되기 전에는 기능을 과도하게 확장하지 않는다.
