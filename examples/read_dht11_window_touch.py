"""python examples/read_dht11_window_touch.py [--verified] [--model DHT22]"""

import argparse
import json
import time
from contextlib import ExitStack
from dataclasses import asdict

from roomcare_hw.sensors import DHTReader, TouchWindowSensor


def main():
    parser = argparse.ArgumentParser(
        description="온습도 + 창문 터치센서. 모터를 구동하지 않습니다."
    )
    parser.add_argument("--model", choices=["DHT11", "DHT22"], default="DHT11")
    parser.add_argument(
        "--verified", action="store_true", help="실제 창문에서 지속 감지를 검증했을 때만 사용"
    )
    parser.add_argument("--touch-means-open", action="store_true")
    args = parser.parse_args()
    with ExitStack() as stack:
        reader = DHTReader(model=args.model)
        stack.callback(reader.close)
        window = TouchWindowSensor(
            verified=args.verified, touched_means_closed=not args.touch_means_open
        )
        stack.callback(window.close)
        try:
            while True:
                result = {"touch": window.touched, "window": window.position}
                try:
                    reading = reader.read()
                    result.update(asdict(reading))
                    result["notice"] = (
                        "고온/다습 감지"
                        if reading.temperature >= 28 or reading.humidity >= 70
                        else "기준 미만"
                    )
                except IOError as exc:
                    result["sensor_error"] = str(exc)
                print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
                time.sleep(2)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
