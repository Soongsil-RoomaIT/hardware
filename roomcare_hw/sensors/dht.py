"""DHT11/DHT22 starter reader; only temperature and humidity are available."""

from __future__ import annotations

import math
import time

from .. import pins
from ..types import PartialReading


class DHTReader:
    def __init__(self, pin: int = pins.DHT11_DATA, model: str = "DHT11", *, device=None):
        if model not in ("DHT11", "DHT22"):
            raise ValueError("model must be DHT11 or DHT22")
        if device is None:
            import adafruit_dht
            import board

            device = getattr(adafruit_dht, model)(getattr(board, f"D{pin}"), use_pulseio=False)
        self._device = device
        self._last_attempt = float("-inf")
        self._last = None
        self._closed = False

    def read(self) -> PartialReading:
        if self._closed:
            raise IOError("DHT: reader closed")
        now = time.monotonic()
        if now - self._last_attempt < 2.0:
            if self._last is None:
                raise IOError("DHT: wait at least 2 seconds before retry")
            return self._last  # timestamp is NOT refreshed for a cached reading
        self._last_attempt = now
        self._last = None
        try:
            t, h = float(self._device.temperature), float(self._device.humidity)
            if (
                not math.isfinite(t)
                or not math.isfinite(h)
                or not -40 <= t <= 80
                or not 0 <= h <= 100
            ):
                raise ValueError("out-of-range reading")
        except (RuntimeError, OSError, ValueError, TypeError) as exc:
            raise IOError(f"DHT: {exc}") from exc
        self._last = PartialReading(time.time(), t, h)
        return self._last

    def close(self):
        if not self._closed:
            self._closed = True
            self._device.exit()
