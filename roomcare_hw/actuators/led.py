"""SAD v1.4: directly commanded, persistent LED state (no toggle servo)."""

from __future__ import annotations

import threading

from gpiozero import LED

from .. import pins
from ..types import AIR_PURIFIER, DEHUMIDIFIER, WINDOW, HardwareFault


class LEDActuator:
    """Logical state equals the GPIO output, not independent optical feedback."""

    state_source = "COMMANDED"
    is_moving = False

    def __init__(self, name: str, pin: int, *, led=None):
        self.name = name
        self._lock = threading.RLock()
        self._closed = False
        self.fault = None
        self._led = led if led is not None else LED(pin, initial_value=False)
        try:
            self._led.off()
        except BaseException:
            self._led.close()
            raise

    @property
    def is_on(self) -> bool:
        with self._lock:
            if self._closed or self.fault:
                raise HardwareFault(self.fault or "LED driver closed")
            try:
                return bool(self._led.is_lit)
            except Exception as exc:
                self.fault = f"LED read failed: {exc}"
                raise HardwareFault(self.fault) from exc

    @property
    def state(self) -> str:
        try:
            return "on" if self.is_on else "off"
        except HardwareFault:
            return "unknown"

    def set(self, on: bool) -> None:
        if type(on) is not bool:
            raise ValueError("on must be bool")
        with self._lock:
            # Direct set is idempotent: duplicate ON never toggles OFF.
            if self.is_on == on:
                return
            try:
                if on:
                    self._led.on()
                else:
                    self._led.off()
                if bool(self._led.is_lit) != on:
                    raise OSError("output did not reach requested state")
            except Exception as exc:
                self.fault = f"LED write failed: {exc}"
                raise HardwareFault(self.fault) from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._led.off()
            finally:
                self._led.close()


class WindowLED(LEDActuator):
    def __init__(self, pin=pins.LED_WINDOW, *, led=None):
        super().__init__(WINDOW, pin, led=led)

    @property
    def position(self) -> str:
        state = self.state
        return {"on": "open", "off": "closed", "unknown": "unknown"}[state]


class PurifierLED(LEDActuator):
    def __init__(self, pin=pins.LED_PURIFIER, *, led=None):
        super().__init__(AIR_PURIFIER, pin, led=led)


class DehumidifierLED(LEDActuator):
    def __init__(self, pin=pins.LED_DEHUMIDIFIER, *, led=None):
        super().__init__(DEHUMIDIFIER, pin, led=led)
