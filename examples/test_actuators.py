"""액추에이터 수동 테스트.

    python examples/test_actuators.py window open
    python examples/test_actuators.py window close
    python examples/test_actuators.py purifier on
    python examples/test_actuators.py purifier off

처음에는 모터를 창문에서 떼어놓고 회전 방향과 리밋 스위치 동작부터 확인할 것.
"""

import logging
import sys
import time

from roomcare_hw.actuators import ServoButtonPurifier, WindowActuator


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    target, action = sys.argv[1], sys.argv[2]
    on = action in ("open", "on")

    if target == "window":
        window = WindowActuator()
        window.set(on)
        try:
            while window.is_moving:  # 리밋 스위치나 타임아웃으로 멈출 때까지 대기
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("stopping")  # Ctrl+C = 비상 정지
        finally:
            print("fully open:", window.is_on)
            window.close()

    elif target == "purifier":
        # 테스트할 때는 현재 공기청정기 상태의 반대로 초기화해야 버튼이 눌린다
        purifier = ServoButtonPurifier(initially_on=not on)
        purifier.set(on)
        time.sleep(1.5)
        purifier.close()

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
