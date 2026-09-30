"""센서 3개를 묶어 edge_agent 가 쓰는 SensorReader 인터페이스로 제공한다.

- SHT31  : 온도, 습도 (I2C 0x44)
- SCD41  : CO2 (I2C 0x62)  * 전원 인가 후 수 분간 값이 안정되지 않음
- PMS7003: PM2.5 (UART)
"""

from __future__ import annotations

import time

import adafruit_scd4x
import adafruit_sht31d
import board

from .. import pins
from ..types import Reading
from .pms7003 import PMS7003


class RoomSensorReader:
    def __init__(self, pms_port: str = pins.PMS_SERIAL_PORT) -> None:
        i2c = board.I2C()
        self._sht = adafruit_sht31d.SHT31D(i2c)
        self._scd = adafruit_scd4x.SCD4X(i2c)
        self._scd.start_periodic_measurement()  # SCD41 은 5초마다 새 값을 만든다
        self._pms = PMS7003(pms_port)
        self._last_co2: float | None = None

    def read(self) -> Reading:
        # SCD41 은 측정 주기(5s)보다 자주 읽으면 새 값이 없으므로 직전 값을 재사용
        if self._scd.data_ready:
            self._last_co2 = float(self._scd.CO2)
        if self._last_co2 is None:
            raise IOError("SCD41: first measurement not ready yet")

        return Reading(
            measured_at=time.time(),
            temperature=round(self._sht.temperature, 1),
            humidity=round(self._sht.relative_humidity, 1),
            co2=self._last_co2,
            pm25=self._pms.read_pm25(),
        )

    def close(self) -> None:
        self._scd.stop_periodic_measurement()
        self._pms.close()
