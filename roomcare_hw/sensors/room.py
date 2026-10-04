"""Full SHT31 (or DHT) + SCD41 + PMS7003 reader. No fake values on failure."""

from __future__ import annotations

import math
import time
from contextlib import ExitStack

from .. import pins
from ..types import Reading
from .pms7003 import PMS7003


class RoomSensorReader:
    def __init__(
        self,
        pms_port: str = pins.PMS_SERIAL_PORT,
        *,
        temperature_model="SHT31",
        co2_max_age: float = 7.0,
        sht=None,
        scd=None,
        pms=None,
        dht=None,
    ):
        if temperature_model not in ("SHT31", "DHT11", "DHT22"):
            raise ValueError("unsupported temperature_model")
        if not math.isfinite(co2_max_age) or co2_max_age <= 0:
            raise ValueError("co2_max_age must be positive")
        self._stack = ExitStack()
        self._closed = False
        self._dht = None
        try:
            i2c = None
            if scd is None or (sht is None and temperature_model == "SHT31"):
                import board

                i2c = board.I2C()
                self._stack.callback(i2c.deinit)
            if temperature_model == "SHT31":
                if sht is None:
                    import adafruit_sht31d

                    sht = adafruit_sht31d.SHT31D(i2c)
                self._sht = sht
            else:
                from .dht import DHTReader

                self._dht = dht if dht is not None else DHTReader(model=temperature_model)
                self._stack.callback(self._dht.close)
            if scd is None:
                import adafruit_scd4x

                scd = adafruit_scd4x.SCD4X(i2c)
            self._scd = scd
            self._scd.start_periodic_measurement()
            self._stack.callback(self._scd.stop_periodic_measurement)
            self._pms = pms if pms is not None else PMS7003(pms_port)
            self._stack.callback(self._pms.close)
        except BaseException:
            self._stack.close()
            raise
        self._co2_max_age = co2_max_age
        self._last_co2 = None
        self._co2_at = float("-inf")
        self._co2_wall = 0.0

    def read(self) -> Reading:
        if self._closed:
            raise IOError("room reader closed")
        try:
            if self._scd.data_ready:
                co2 = float(self._scd.CO2)
                if not math.isfinite(co2) or co2 <= 0:
                    raise ValueError("SCD41 returned invalid CO2")
                self._last_co2 = co2
                self._co2_at = time.monotonic()
                self._co2_wall = time.time()
            if self._last_co2 is None or time.monotonic() - self._co2_at > self._co2_max_age:
                raise IOError("SCD41: warming up or stale measurement")
            if self._dht is not None:
                r = self._dht.read()
                t, h, th_at = r.temperature, r.humidity, r.measured_at
            else:
                th_at = time.time()
                t, h = float(self._sht.temperature), float(self._sht.relative_humidity)
            pm = self._pms.read_pm25()
            if (
                not all(math.isfinite(x) for x in (t, h, pm))
                or not -40 <= t <= 125
                or not 0 <= h <= 100
                or pm < 0
            ):
                raise ValueError("invalid sensor reading")
            # Oldest acquisition timestamp, so delayed components aren't presented as fresh.
            return Reading(min(th_at, self._co2_wall), round(t, 1), round(h, 1), self._last_co2, pm)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise IOError(f"room sensors: {exc}") from exc

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._stack.close()
