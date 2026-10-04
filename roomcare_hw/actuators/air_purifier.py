"""Serialized retrofit toggle button; unknown state must not trigger blind toggles."""

from __future__ import annotations

import math
import threading

from gpiozero import AngularServo

from .. import pins
from ..types import AIR_PURIFIER, DEHUMIDIFIER, HardwareFault


class ServoButtonPurifier:
    name = AIR_PURIFIER

    def __init__(
        self,
        rest_angle=0.0,
        press_angle=35.0,
        press_seconds=0.4,
        initially_on=None,
        *,
        pin=pins.PURIFIER_SERVO,
        settle_seconds=0.5,
        servo=None,
        feedback=None,
    ):
        if not all(math.isfinite(x) and -90 <= x <= 90 for x in (rest_angle, press_angle)):
            raise ValueError("servo angles must be within -90..90")
        if not all(math.isfinite(x) and x > 0 for x in (press_seconds, settle_seconds)):
            raise ValueError("press/settle duration must be positive")
        if initially_on is not None and type(initially_on) is not bool:
            raise ValueError("initially_on must be bool or None")
        self._servo = servo if servo is not None else AngularServo(pin, initial_angle=None)
        self._rest, self._press = rest_angle, press_angle
        self._press_seconds, self._settle = press_seconds, settle_seconds
        self._feedback = feedback
        self._on = initially_on  # None after restart until measured or explicitly confirmed
        self._target = None
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._quit = threading.Event()
        self._busy = False
        self._closed = False
        self.fault = None
        self._servo.detach()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"roomcare-{self.name}")
        self._thread.start()

    def _state(self):
        value = self._feedback() if self._feedback is not None else self._on
        if value is not None and type(value) is not bool:
            raise HardwareFault("feedback must return bool or None")
        return value

    @property
    def state(self):
        with self._lock:
            if self.fault or self._busy:
                return "unknown"
            value = self._state()
            return "unknown" if value is None else "on" if value else "off"

    @property
    def is_on(self):
        with self._lock:
            value = self._state()
            if value is None or self.fault or self._busy:
                raise HardwareFault("appliance state unknown; confirm state or add feedback")
            return value

    @property
    def is_moving(self):
        with self._lock:
            return self._busy or self._target is not None

    def confirm_state(self, on: bool):
        if type(on) is not bool:
            raise ValueError("on must be bool")
        with self._lock:
            if self._closed or self._busy:
                raise HardwareFault("cannot confirm state while closed/moving")
            self._on = on
            self._target = None
            self.fault = None

    def set(self, on: bool):
        if type(on) is not bool:
            raise ValueError("on must be bool")
        with self._lock:
            if self._closed or self.fault:
                raise HardwareFault(self.fault or "appliance driver closed")
            if not self._busy and self._state() is None:
                raise HardwareFault("initial state unknown; confirm actual state first")
            self._target = on  # latest desired state, no parallel button presses
            self._wake.set()

    def _run(self):
        while not self._quit.is_set():
            self._wake.wait(0.1)
            self._wake.clear()
            if self._quit.is_set():
                break
            with self._lock:
                if self._target is None or self.fault:
                    continue
                try:
                    before = self._state()
                    if before is None:
                        raise HardwareFault("feedback state unknown")
                    if before == self._target:
                        self._target = None
                        continue
                    self._busy = True
                except Exception as exc:
                    self.fault = str(exc)
                    self._target = None
                    continue
            try:
                self._servo.angle = self._press
                if self._quit.wait(self._press_seconds):
                    raise HardwareFault("button operation interrupted")
                self._servo.angle = self._rest
                if self._quit.wait(self._settle):
                    raise HardwareFault("button operation interrupted")
                self._servo.detach()
                with self._lock:
                    self._on = not before
                    if self._feedback is not None and self._state() != self._on:
                        raise HardwareFault("button press not confirmed by feedback")
            except Exception as exc:
                with self._lock:
                    self.fault = str(exc)
                    self._on = None
                    self._target = None
            finally:
                try:
                    self._servo.detach()
                except Exception as exc:
                    with self._lock:
                        self.fault = f"servo release failed: {exc}"
                        self._on = None
                        self._target = None
                with self._lock:
                    self._busy = False
                    if self._target is not None:
                        self._wake.set()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._target = None
            self._quit.set()
            self._wake.set()
        self._thread.join()
        self._busy = False
        try:
            self._servo.detach()
        finally:
            self._servo.close()


class ServoButtonDehumidifier(ServoButtonPurifier):
    name = DEHUMIDIFIER

    def __init__(self, *, pin=pins.DEHUMIDIFIER_SERVO, **kwargs):
        super().__init__(pin=pin, **kwargs)
