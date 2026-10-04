"""DFR0030/TTP223 input; touch is only a position sensor AFTER installation validation."""

from __future__ import annotations

from typing import Callable

from gpiozero import DigitalInputDevice

from .. import pins
from ..types import HardwareFault


class TouchDoorSensor:
    def __init__(
        self,
        pin=pins.DOOR_TOUCH,
        touched_means_closed=True,
        debounce=0.05,
        *,
        verified=False,
        device=None,
    ):
        self._dev = (
            device
            if device is not None
            else DigitalInputDevice(pin, pull_up=None, active_state=True, bounce_time=debounce)
        )
        self._touched_means_closed = touched_means_closed
        self.verified = verified
        self.when_opened: Callable[[], None] | None = None
        self.when_closed: Callable[[], None] | None = None
        self._dev.when_activated = self._on_touch
        self._dev.when_deactivated = self._on_release

    @property
    def touched(self) -> bool:
        return bool(self._dev.is_active)

    @property
    def is_open(self) -> bool:
        if not self.verified:
            raise HardwareFault("touch installation not verified; position is unknown")
        return not self.touched if self._touched_means_closed else self.touched

    @property
    def position(self) -> str:
        return ("open" if self.is_open else "closed") if self.verified else "unknown"

    def close(self):
        self._dev.when_activated = None
        self._dev.when_deactivated = None
        self._dev.close()

    def _on_touch(self):
        self._fire(self.when_closed if self._touched_means_closed else self.when_opened)

    def _on_release(self):
        self._fire(self.when_opened if self._touched_means_closed else self.when_closed)

    def _fire(self, callback):
        if self.verified and callback is not None:
            callback()


class TouchWindowSensor(TouchDoorSensor):
    def __init__(self, pin=pins.WINDOW_TOUCH, **kwargs):
        super().__init__(pin=pin, **kwargs)
