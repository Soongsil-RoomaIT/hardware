"""Standalone tabletop door prototype. Do NOT run alongside Edge's policy."""

import argparse
import time
from contextlib import ExitStack

from roomcare_hw.actuators import DoorAutoCloser, DoorCloserServo
from roomcare_hw.sensors import TouchDoorSensor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=600.0)
    parser.add_argument("--push", action="store_true", help="서보 한 번 시험")
    parser.add_argument("--verified", action="store_true", help="센서 지속감지 및 기구 안전 확인")
    args = parser.parse_args()
    if not args.verified:
        parser.error("탁상 모형에서 센서와 기구를 확인한 뒤 --verified를 사용하세요")
    with ExitStack() as stack:
        sensor = TouchDoorSensor(verified=True)
        stack.callback(sensor.close)
        closer = DoorCloserServo(sensor)
        stack.callback(closer.close)
        try:
            if args.push:
                closer.push()
                while closer.is_moving:
                    time.sleep(0.05)
                if closer.fault:
                    raise RuntimeError(closer.fault)
                return
            auto = DoorAutoCloser(sensor, closer, close_delay=args.delay)
            stack.callback(auto.stop)
            while True:
                print(
                    "door:", sensor.position, "attempts:", auto.attempts, "error:", auto.last_error
                )
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
