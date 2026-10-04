"""Manual detached-bench test. Appliance current state must be explicitly supplied."""

import argparse
import time

from roomcare_hw.actuators import ServoButtonDehumidifier, ServoButtonPurifier, WindowActuator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device", choices=["window", "purifier", "dehumidifier"])
    parser.add_argument("action", choices=["open", "close", "on", "off"])
    parser.add_argument("--current", choices=["on", "off"], help="눈으로 확인한 가전의 현재 상태")
    parser.add_argument(
        "--bench-confirmed", action="store_true", help="기구 분리·배선·회전 범위를 확인한 시험"
    )
    args = parser.parse_args()
    if not args.bench_confirmed:
        parser.error("기구를 분리해 안전하게 배치한 뒤 --bench-confirmed를 사용하세요")
    if args.device == "window":
        if args.action not in ("open", "close"):
            parser.error("window action must be open/close")
        device = WindowActuator()
    else:
        if args.action not in ("on", "off") or args.current is None:
            parser.error("appliance needs on/off and --current on/off")
        cls = ServoButtonPurifier if args.device == "purifier" else ServoButtonDehumidifier
        device = cls(initially_on=args.current == "on")
    try:
        device.set(args.action in ("open", "on"))
        while device.is_moving:
            time.sleep(0.02)
        if device.fault:
            raise RuntimeError(device.fault)
        print("state:", device.position if args.device == "window" else device.state)
    except KeyboardInterrupt:
        print("중단")
    finally:
        device.close()


if __name__ == "__main__":
    main()
