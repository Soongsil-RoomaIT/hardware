"""Composition boundary for A: one owner releases every GPIO/bus resource."""

from contextlib import ExitStack

from .actuators import DoorCloserServo, ServoButtonDehumidifier, ServoButtonPurifier, WindowActuator
from .sensors import (
    CachedSensorReader,
    DHTReader,
    RoomSensorReader,
    TouchDoorSensor,
    TouchWindowSensor,
)
from .types import AIR_PURIFIER, DEHUMIDIFIER, DOOR, WINDOW


class HardwareBundle:
    """No actuators by default. Construction never sends a movement command.

    starter=True is for standalone learning, not Edge's numeric Reading contract.
    Every enable flag means wiring and mechanics have been checked by the operator.
    """

    def __init__(
        self,
        *,
        starter=False,
        temperature_model="SHT31",
        window_touch=False,
        touch_verified=False,
        door_sensor=False,
        door_verified=False,
        window_motor=False,
        purifier=False,
        purifier_initial=None,
        dehumidifier=False,
        dehumidifier_initial=None,
        door_closer=False,
    ):
        if door_closer and (not door_sensor or not door_verified):
            raise ValueError("door closer requires verified door sensor")
        if starter and temperature_model not in ("DHT11", "DHT22"):
            raise ValueError("starter profile requires DHT11 or DHT22")
        self._stack = ExitStack()
        self.actuators = {}
        self.door_sensor = self.window_sensor = None
        self._closed = False
        try:
            source = (
                DHTReader(model=temperature_model)
                if starter
                else RoomSensorReader(temperature_model=temperature_model)
            )
            # Transfer source ownership to the background reader only after successful construction.
            try:
                self.sensor = CachedSensorReader(source)
            except BaseException:
                source.close()
                raise
            self._stack.callback(self.sensor.close)
            if window_touch:
                self.window_sensor = self._own(TouchWindowSensor(verified=touch_verified))
            if door_sensor:
                self.door_sensor = self._own(TouchDoorSensor(verified=door_verified))
            if window_motor:
                self.actuators[WINDOW] = self._own(WindowActuator())
            if purifier:
                self.actuators[AIR_PURIFIER] = self._own(
                    ServoButtonPurifier(initially_on=purifier_initial)
                )
            if dehumidifier:
                self.actuators[DEHUMIDIFIER] = self._own(
                    ServoButtonDehumidifier(initially_on=dehumidifier_initial)
                )
            if door_closer:
                self.actuators[DOOR] = self._own(DoorCloserServo(self.door_sensor))
        except BaseException:
            self._stack.close()
            raise

    def _own(self, device):
        self._stack.callback(device.close)
        return device

    def status(self):
        result = {"sensor_error": self.sensor.last_error, "actuators": {}}
        for label, sensor in (("window", self.window_sensor), ("door", self.door_sensor)):
            if sensor is not None:
                try:
                    result[label] = {"position": sensor.position, "touch": sensor.touched}
                except Exception as exc:
                    result[label] = {"position": "unknown", "error": str(exc)}
        for name, device in self.actuators.items():
            try:
                if name == WINDOW:
                    state = device.position
                elif name == DOOR:
                    state = "open" if device.is_on else "closed"
                else:
                    state = device.state
                result["actuators"][name] = {
                    "state": state,
                    "moving": device.is_moving,
                    "fault": device.fault,
                }
            except Exception as exc:
                result["actuators"][name] = {"state": "unknown", "fault": str(exc)}
        return result

    def close(self):
        if not self._closed:
            self._closed = True
            self._stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
