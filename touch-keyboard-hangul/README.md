# 터치 키보드 한/영 키

우분투 기본 터치 키보드의 스페이스바 오른쪽에 **한/영** 키를 추가하는
GNOME 확장입니다. Ubuntu 26.04.1 / GNOME Shell 50.1 / Wayland /
IBus Hangul 환경에서 실제 터치 전환을 확인했습니다.

## 파일

```text
touch-keyboard-hangul/
├── README.md
├── install.sh
└── extension/
    ├── extension.js
    └── metadata.json
```

압축파일 없이 이 폴더 전체를 다른 컴퓨터나 USB에 복사하면 됩니다.

## 재설치 후 설정

1. 한글 입력기가 없으면 설치합니다.

   ```bash
   sudo apt install ibus-hangul
   ```

2. 이 폴더에서 설치 스크립트를 일반 사용자로 실행합니다.

   ```bash
   bash install.sh
   ```

3. 작업을 저장하고 로그아웃한 뒤 다시 로그인합니다.
4. 설정 → 키보드 → 입력 소스에서 **한국어(Hangul)**를 추가하고 선택합니다.
5. 화면 하단을 쓸어 올려 기본 터치 키보드를 열고 **한/영** 키를 누릅니다.

한국어(Hangul) 입력 소스 안에서 한글/영어 모드를 전환합니다.
별도 English (US) 입력 소스를 선택한 상태에서는 이 키가 표시되지 않습니다.

이 버전은 **GNOME 50용**입니다. 다른 GNOME 버전에서는 내부 키보드 API의
호환성을 먼저 확인해야 합니다. 현재 버전은 `gnome-shell --version`으로 확인합니다.

## 작동 원리

기본 화면 키보드의 Shift는 대문자/쌍자음 배열만 바꾸므로 실제
Shift+Space 단축키를 만들지 않습니다. 이 확장은 `_addRowKeys`에 기능을
추가해 실제 Hangul 키심 `0xff31`을 보내는 한/영 키를 넣습니다.

IBus가 입력 모드를 바꾸면 GNOME이 한글/영어 배열을 갱신합니다.
추가한 키의 너비만큼 스페이스바를 줄여 행의 전체 너비를 유지합니다.
기존 언어 메뉴도 유지됩니다.

설치 스크립트는 확장 파일을 현재 사용자의 데이터 폴더에 복사하고 확장을
활성화합니다. 입력 소스, IBus 전환키, 터치 제스처, 화면 위치 설정은 바꾸지 않습니다.
이미 같은 확장이 있으면 이 폴더의 코드로 갱신합니다.

기본 설치 위치:

```text
~/.local/share/gnome-shell/extensions/surface-hangul-key@local/
```

## 끄기 / 제거

```bash
gnome-extensions disable surface-hangul-key@local
gnome-extensions uninstall surface-hangul-key@local
```
