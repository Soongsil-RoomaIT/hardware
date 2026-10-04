"""Background sampling keeps Edge's network loop free of blocking I/O."""

from __future__ import annotations

import math
import threading
import time


class CachedSensorReader:
    """Owns source. read() fails until first valid sample; never returns stale cache."""

    def __init__(self, source, interval=2.0, max_age=4.0):
        if not all(math.isfinite(x) and x > 0 for x in (interval, max_age)):
            raise ValueError("interval and max_age must be finite and positive")
        self._source = source
        self._interval, self._max_age = interval, max_age
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sample = None
        self._sample_at = 0.0
        self.last_error = "first measurement pending"
        self._thread = threading.Thread(target=self._run, daemon=True, name="roomcare-sensors")
        self._thread.start()

    def read(self):
        with self._lock:
            if self._stop.is_set() or self._sample is None:
                raise IOError(self.last_error or "sensor reader closed")
            if time.monotonic() - self._sample_at > self._max_age:
                self.last_error = "cached sensor sample is stale"
                raise IOError(self.last_error)
            return self._sample

    def _run(self):
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    sample = self._source.read()
                    # Include the source's own acquisition age, including a reused CO2/DHT value.
                    age = max(0.0, time.time() - sample.measured_at)
                    with self._lock:
                        self._sample = sample
                        self._sample_at = time.monotonic() - age
                        self.last_error = None
                except Exception as exc:
                    with self._lock:
                        self.last_error = str(exc)
                        self._sample = None
                self._stop.wait(max(0, self._interval - (time.monotonic() - started)))
        finally:
            self._source.close()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=3)
        if self._thread.is_alive():
            raise TimeoutError("sensor I/O stuck; worker will close source when I/O returns")
