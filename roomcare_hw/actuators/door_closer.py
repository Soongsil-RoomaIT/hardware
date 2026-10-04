"""Door-closing prototype and optional 600-second standalone policy.

Production policy belongs to C/A; do not run this controller alongside Edge policy.
"""

from __future__ import annotations

import math
import threading
import time

from gpiozero import AngularServo

from .. import pins
from ..types import DOOR, HardwareFault


class DoorCloserServo:
    name = DOOR

    def __init__(
        self,
        sensor,
        pin=pins.DOOR_SERVO,
        rest_angle=-60.0,
        push_angle=60.0,
        hold_seconds=1.0,
        *,
        return_seconds=0.8,
        servo=None,
        obstruction=None,
    ):
        if not all(math.isfinite(x) and -90 <= x <= 90 for x in (rest_angle, push_angle)):
            raise ValueError("angles must be within -90..90")
        if not all(math.isfinite(x) and x > 0 for x in (hold_seconds, return_seconds)):
            raise ValueError("durations must be positive")
        self._sensor = sensor
        self._servo = servo if servo is not None else AngularServo(pin, initial_angle=None)
        self._rest, self._push = rest_angle, push_angle
        self._hold, self._return = hold_seconds, return_seconds
        self._obstruction = obstruction
        self._lock = threading.RLock()
        self._quit = threading.Event()
        self._wake = threading.Event()
        self._busy = False
        self._closed = False
        self._issued = False
        self.fault = None
        self._servo.detach()
        self._thread = threading.Thread(target=self._run, daemon=True, name="roomcare-door")
        self._thread.start()

    @property
    def is_on(self):
        return self._sensor.is_open

    @property
    def is_moving(self):
        with self._lock:
            return self._busy

    def set(self, on: bool):
        if type(on) is not bool:
            raise ValueError("on must be bool")
        if on:
            raise HardwareFault("door closer cannot open the door")
        with self._lock:
            if self._closed or self.fault:
                raise HardwareFault(self.fault or "door driver closed")
            if not self._sensor.is_open:
                self._issued = False
                return
            if self._issued:
                return
            if self.push():
                self._issued = True

    def push(self):
        """Explicit single attempt (also used by bounded retry policy)."""
        with self._lock:
            if self._closed or self.fault:
                raise HardwareFault(self.fault or "door driver closed")
            if self._obstruction and self._obstruction():
                raise HardwareFault("door obstruction")
            if self._busy:
                return False
            self._busy = True
            self._wake.set()
            return True

    def reset_fault(self):
        with self._lock:
            if self._closed or self._busy:
                raise HardwareFault("cannot reset closed/moving driver")
            if self._obstruction and self._obstruction():
                raise HardwareFault("remove obstruction first")
            self.fault = None
            self._issued = False

    def _run(self):
        while not self._quit.is_set():
            self._wake.wait(0.05)
            if self._quit.is_set():
                break
            if not self._wake.is_set():
                try:
                    if not self._sensor.is_open:
                        with self._lock:
                            self._issued = False
                except Exception:
                    pass  # unknown position cannot trigger a movement
                continue
            self._wake.clear()
            try:
                self._servo.angle = self._push
                until = time.monotonic() + self._hold
                while time.monotonic() < until:
                    if self._quit.wait(min(0.02, max(0, until - time.monotonic()))):
                        break
                    if self._obstruction and self._obstruction():
                        raise HardwareFault("door obstruction during movement")
                    if not self._sensor.is_open:
                        break
                if not self._quit.is_set():
                    self._servo.angle = self._rest
                    self._quit.wait(self._return)
            except Exception as exc:
                self.fault = str(exc)
            finally:
                try:
                    self._servo.detach()
                except Exception as exc:
                    self.fault = f"servo release failed: {exc}"
                with self._lock:
                    self._busy = False

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._quit.set()
            self._wake.set()
        self._thread.join()
        self._busy = False
        try:
            self._servo.detach()
        finally:
            self._servo.close()


class DoorAutoCloser:
    """Standalone demonstration: continuously open for 600s, max 3 attempts.

    Ambiguous 'recent 10 minutes' requirement is interpreted as continuously open.
    Sensor exceptions disable this controller; stop() permanently disarms it.
    """

    def __init__(
        self,
        sensor,
        closer,
        close_delay=600.0,
        retry_delay=3.0,
        max_attempts=3,
        *,
        poll_interval=0.05,
    ):
        if not all(math.isfinite(x) and x > 0 for x in (close_delay, retry_delay, poll_interval)):
            raise ValueError("delays must be finite and positive")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self._sensor, self._closer = sensor, closer
        self._delay, self._retry = close_delay, retry_delay
        self._maximum, self._poll = max_attempts, poll_interval
        self._quit = threading.Event()
        self._lock = threading.RLock()
        self._enabled = True
        self._opened_at = None
        self._retry_at = None
        self._waiting = False
        self.attempts = 0
        self.last_error = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="roomcare-door-demo")
        self._thread.start()

    @property
    def enabled(self):
        return self._enabled and not self._quit.is_set()

    @enabled.setter
    def enabled(self, value):
        with self._lock:
            self._enabled = bool(value)
            self._reset()

    def _reset(self):
        self._opened_at = self._retry_at = None
        self._waiting = False
        self.attempts = 0

    def _run(self):
        while not self._quit.wait(self._poll):
            with self._lock:
                try:
                    self._tick(time.monotonic())
                except Exception as exc:
                    self.last_error = str(exc)
                    self._enabled = False
                    self._reset()

    def _tick(self, now):
        if not self.enabled or not self._sensor.is_open:
            self._reset()
            return
        if self._opened_at is None:
            self._opened_at = now
        if self._closer.is_moving:
            return
        if self._waiting:
            self._waiting = False
            self._retry_at = now + self._retry  # retry delay starts AFTER motion completes
        if self.attempts >= self._maximum:
            self.last_error = "door remains open after maximum attempts"
            return
        if now - self._opened_at < self._delay or (self._retry_at and now < self._retry_at):
            return
        if self._closer.push():
            self.attempts += 1
            self._waiting = True

    def stop(self):
        self._quit.set()
        self._thread.join()

    close = stop
