"""SAD v1.4: MQ-2 digital output only. Never reports a concentration or CO2."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable

from gpiozero import DigitalInputDevice

from .. import pins

log = logging.getLogger(__name__)


class MQ2GasSensor:
    """Tri-state gas detection, independent of the DHT reader.

    None = warming up, unreadable, stale or closed. The GPIO input must already
    be level-shifted to safe 3.3 V logic. Do not connect a 5 V DO directly.
    """

    def __init__(
        self,
        pin=pins.MQ2_DO,
        *,
        active_low=True,
        warmup_seconds=180.0,
        poll_seconds=0.1,
        device=None,
    ):
        if type(active_low) is not bool:
            raise ValueError("active_low must be bool")
        if not math.isfinite(warmup_seconds) or warmup_seconds < 0:
            raise ValueError("warmup_seconds must be finite and nonnegative")
        if not math.isfinite(poll_seconds) or poll_seconds <= 0:
            raise ValueError("poll_seconds must be finite and positive")
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._ready_at = time.monotonic() + warmup_seconds
        self._poll = poll_seconds
        self._max_age = max(1.0, 3 * poll_seconds)
        self._value = None
        self._last_known = None
        self._sample_at = None
        self._error = None
        self.when_detected: Callable[[], None] | None = None
        self.when_cleared: Callable[[], None] | None = None
        # External module drives DO. Pull configuration is floating, active level explicit.
        self._device = (
            device
            if device is not None
            else DigitalInputDevice(pin, pull_up=None, active_state=not active_low)
        )
        self._thread = threading.Thread(target=self._run, daemon=True, name="roomcare-mq2")
        try:
            self._thread.start()
        except BaseException:
            self._device.close()
            raise

    @property
    def warming_up(self) -> bool:
        return not self._stop.is_set() and time.monotonic() < self._ready_at

    @property
    def last_error(self) -> str | None:
        with self._lock:
            if self._stop.is_set():
                return "MQ-2 closed"
            if self.warming_up:
                return None
            if self._sample_at is not None and time.monotonic() - self._sample_at > self._max_age:
                return "MQ-2 sample is stale"
            return self._error

    @property
    def gas_detected(self) -> bool | None:
        with self._lock:
            if self._stop.is_set() or self.warming_up or self.last_error is not None:
                return None
            return self._value

    def read(self) -> bool | None:
        return self.gas_detected

    def _poll_once(self) -> None:
        if self._stop.is_set() or self.warming_up:
            return
        try:
            value = bool(self._device.is_active)
        except Exception as exc:
            with self._lock:
                self._value = None
                self._error = f"MQ-2 read failed: {exc}"
                self._sample_at = time.monotonic()
            return
        with self._lock:
            previous = self._last_known
            self._value = self._last_known = value
            self._sample_at = time.monotonic()
            self._error = None
            callback = None
            if value and previous is not True:
                callback = self.when_detected
            elif not value and previous is True:
                callback = self.when_cleared
        # A callback must be quick; polling remains usable if callback raises.
        if callback is not None and not self._stop.is_set():
            try:
                callback()
            except Exception:
                log.exception("MQ-2 callback failed")

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._poll_once()
                self._stop.wait(self._poll)
        finally:
            self._device.close()

    def close(self) -> None:
        self._stop.set()
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise TimeoutError("MQ-2 worker did not stop; GPIO will close on exit")
