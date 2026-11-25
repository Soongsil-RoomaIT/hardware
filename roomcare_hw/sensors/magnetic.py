"""MC-38 dry-contact reed switch: GPIO pull-up, LOW = magnet present/closed."""

from gpiozero import DigitalInputDevice

from .. import pins
from .door import TouchDoorSensor


class MagneticDoorSensor(TouchDoorSensor):
    """Preserve the existing door interface; verify the physical contact polarity first.

    A broken/disconnected wire looks like an open door with a two-wire switch.
    The driver cannot independently diagnose that condition.
    """

    state_source = "SENSOR"

    def __init__(self, pin=pins.DOOR_MAGNETIC, debounce=0.05, *, verified=False, device=None):
        # With internal pull-up, gpiozero's logical active state is LOW.
        dev = (
            device
            if device is not None
            else DigitalInputDevice(pin, pull_up=True, bounce_time=debounce)
        )
        try:
            super().__init__(device=dev, verified=verified, touched_means_closed=True)
        except BaseException:
            dev.close()
            raise

    @property
    def magnet_present(self) -> bool:
        return self.touched
