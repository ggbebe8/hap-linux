Ubuntu 26.04 GNOME 50 Wayland에서 동작하는
Hunt-and-Peck / Vimium 스타일의 키보드 UI navigation 프로그램을 만들어줘.

목표:
- 전역 단축키를 누르면 현재 활성 창의 클릭 가능한 UI 요소를 탐색한다.
- 각 요소 위에 A, S, D, F, J, K 등의 hint label을 표시한다.
- 해당 키를 입력하면 그 UI 요소를 실행한다.
- 가능하면 마우스 좌표 클릭 대신 AT-SPI Action을 사용한다.
- AT-SPI Action이 없는 경우에만 fallback 방법을 고려한다.
- Wayland를 기본 환경으로 한다.
- X11 전용 솔루션은 사용하지 않는다.

환경:
- Ubuntu 26.04
- GNOME 50
- Wayland
- Python 사용 가능
- GNOME Shell Extension 사용 가능

구조는 필요하면 다음처럼 구성해도 된다:
- Python daemon/controller
- AT-SPI integration
- GNOME Shell Extension overlay

요구사항:
1. 먼저 현재 Ubuntu/GNOME/Wayland 환경에서 가능한 기술을 조사한다.
2. 최소 동작 가능한 MVP를 설계한다.
3. 필요한 패키지를 확인한다.
4. 코드를 직접 생성한다.
5. 실행 및 설치 스크립트를 만든다.
6. 가능하면 테스트도 작성하고 실행한다.
7. 실행 중 에러가 발생하면 원인을 분석하고 직접 수정한다.
8. README에 설치/실행/삭제 방법을 작성한다.
9. 내가 중간에 설계 결정을 할 필요가 없도록 합리적인 선택은 스스로 결정한다.
10. 완료될 때까지 구현-테스트-수정 과정을 반복한다.

MVP 우선순위:
- 현재 활성 창만 대상으로 한다.
- Button / Link / Menu / Tab 등 Action 가능한 요소를 찾는다.
- hint overlay를 표시한다.
- 키 입력으로 하나를 선택한다.
- Esc로 취소한다.
- 선택된 요소는 AT-SPI Action으로 실행한다.

처음부터 완벽한 범용성을 목표로 하지 말고,
실제로 실행되는 MVP를 먼저 완성해라.

작업을 시작하기 전에 긴 설명을 하지 말고,
필요한 파일을 만들고 실제 구현을 진행해라.


시스템 영역이나 ~/.local/share 등에 직접 설치하지 말고,
필요한 설치 과정을 install.sh 하나로 만들어라.

개발과 테스트는 현재 repository 안에서 최대한 수행하고,
최종적으로 내가 ./install.sh만 실행하면 설치되도록 구성해라.
