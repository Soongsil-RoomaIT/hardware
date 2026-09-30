"""문 자동 닫기 테스트: 터치센서로 열림 감지 -> N초 뒤 서보로 닫기.

    python examples/door_auto_close.py            # 10초 뒤 닫기
    python examples/door_auto_close.py --delay 3
    python examples/door_auto_close.py --push     # 센서 무시하고 서보 한 번만 스윙 (각도 조정용)
"""

import argparse
import logging
import time

from roomcare_hw.actuators import DoorAutoCloser, DoorCloserServo
from roomcare_hw.sensors import TouchDoorSensor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=10.0, help="열림 후 닫기까지 대기(초)")
    parser.add_argument("--push", action="store_true", help="서보 한 번만 스윙")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    sensor = TouchDoorSensor()
    closer = DoorCloserServo(sensor)

    if args.push:
        closer.push()
        time.sleep(2.5)
        closer.close()
        sensor.close()
        return

    auto = DoorAutoCloser(sensor, closer, close_delay=args.delay)
    print(f"door is {'OPEN' if sensor.is_open else 'CLOSED'}. Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        auto.stop()
        closer.close()
        sensor.close()


if __name__ == "__main__":
    main()
