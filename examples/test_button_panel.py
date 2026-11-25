"""버튼 서보 + LED 확인. 서보는 기구(버튼)에서 떼어 놓고 실행한다.

python examples/test_button_panel.py window --bench-confirmed       # 창문 LED 켜고 한 번 누름
python examples/test_button_panel.py all --bench-confirmed          # 창문 -> 공기청정기 -> 제습기 차례로
python examples/test_button_panel.py all --together --bench-confirmed  # 세 명령을 동시에 (하나씩 눌러야 정상)
"""

import argparse
import time

from roomcare_hw.actuators.button_panel import ButtonServoPanel, button_devices
from roomcare_hw.types import AIR_PURIFIER, DEHUMIDIFIER, WINDOW

NAMES = {"window": WINDOW, "purifier": AIR_PURIFIER, "dehumidifier": DEHUMIDIFIER}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device", choices=[*NAMES, "all"])
    parser.add_argument("--together", action="store_true", help="여러 기기 명령을 동시에 보냄")
    parser.add_argument("--bench-confirmed", action="store_true", help="서보를 기구에서 분리함")
    args = parser.parse_args()
    if not args.bench_confirmed:
        parser.error("서보를 버튼에서 떼어 놓은 뒤 --bench-confirmed 를 붙이세요")

    targets = list(NAMES.values()) if args.device == "all" else [NAMES[args.device]]
    panel = ButtonServoPanel()
    # 시험이라 모두 꺼져/닫혀 있다고 보고 켜기(열기) 명령을 보낸다 -> 기기마다 한 번씩 누름
    devices = button_devices(
        panel,
        window=WINDOW in targets,
        window_initial=False,
        purifier=AIR_PURIFIER in targets,
        purifier_initial=False,
        dehumidifier=DEHUMIDIFIER in targets,
        dehumidifier_initial=False,
    )
    try:
        if args.together:
            for device in devices.values():
                device.set(True)
        for name, device in devices.items():
            if not args.together:
                device.set(True)
            while device.is_moving:
                time.sleep(0.02)
            print(f"{name}: {device.state}" + (f" (fault: {device.fault})" if device.fault else ""))
    except KeyboardInterrupt:
        print("중단")
    finally:
        for device in devices.values():
            device.close()
        panel.close()


if __name__ == "__main__":
    main()
