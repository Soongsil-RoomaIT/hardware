"""Full set: SHT31/DHT + SCD41 + PMS7003. Failures never become zero readings."""

import argparse
import json
import time
from dataclasses import asdict

from roomcare_hw.sensors import CachedSensorReader, RoomSensorReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--temperature-model", choices=["SHT31", "DHT11", "DHT22"], default="SHT31")
    args = parser.parse_args()
    reader = CachedSensorReader(RoomSensorReader(temperature_model=args.temperature_model))
    try:
        while True:
            try:
                print(json.dumps(asdict(reader.read()), allow_nan=False), flush=True)
            except IOError as exc:
                print("read unavailable:", exc, flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()


if __name__ == "__main__":
    main()
