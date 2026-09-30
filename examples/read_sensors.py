"""센서 값 확인용. 2초마다 측정값을 출력한다.

    python examples/read_sensors.py
"""

import time

from roomcare_hw.sensors import RoomSensorReader


def main() -> None:
    reader = RoomSensorReader()
    print("SCD41 warm-up... (첫 CO2 값까지 약 5초)")
    try:
        while True:
            try:
                r = reader.read()
                print(
                    f"{time.strftime('%H:%M:%S')}  "
                    f"temp {r.temperature:5.1f} C  hum {r.humidity:5.1f} %  "
                    f"co2 {r.co2:6.0f} ppm  pm2.5 {r.pm25:5.1f} ug/m3"
                )
            except IOError as e:
                print("read failed:", e)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        reader.close()


if __name__ == "__main__":
    main()
