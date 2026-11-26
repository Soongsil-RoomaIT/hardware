"""Composition boundary for A: one owner releases every GPIO/bus resource."""

from contextlib import ExitStack

from .actuators import DoorCloserServo, ServoButtonDehumidifier, ServoButtonPurifier, WindowActuator
from .actuators.button_panel import ButtonServoPanel, button_devices
from .actuators.led import DehumidifierLED, PurifierLED, WindowLED
from .sensors import (
    CachedSensorReader,
    DHTReader,
    MagneticDoorSensor,
    MQ2GasSensor,
    RoomSensorReader,
    TouchDoorSensor,
    TouchWindowSensor,
)
from .types import AIR_PURIFIER, DEHUMIDIFIER, DOOR, WINDOW


class HardwareBundle:
    """No actuators by default. Construction never sends a movement command.

    starter=True uses DHT-only readings supported by the nullable Edge contract.
    Every enable flag means wiring and mechanics have been checked by the operator.

    SAD v1.4 uses window_led/purifier_led/dehumidifier_led, door_magnetic and gas_sensor.
    No automatic-control timers are started by this bundle.

    Legacy (not the v1.4 demo):
    button_panel=True: 버튼 서보 하나(GPIO18)가 창문/공기청정기/제습기 버튼을 모두 누르고,
    누르는 동안 기기별 LED(GPIO17/27/22)를 켠다. window_button/purifier/dehumidifier 로 쓸 기기를 고른다.
    LED 핀이 창문 모터 핀과 겹쳐서 window_motor 와 같이 쓸 수 없다.
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
        button_panel=False,
        window_button=False,
        window_initial=None,
        window_led=False,
        purifier_led=False,
        dehumidifier_led=False,
        door_magnetic=False,
        gas_sensor=False,
        gas_active_low=True,
        gas_warmup_seconds=180.0,
        door_rest_angle=-60.0,
        door_push_angle=60.0,
        door_hold_seconds=1.0,
        door_return_seconds=0.8,
    ):
        any_led = window_led or purifier_led or dehumidifier_led
        if any_led and (button_panel or window_motor):
            raise ValueError("LED demo conflicts with button_panel/window_motor GPIOs")
        if (purifier and purifier_led) or (dehumidifier and dehumidifier_led):
            raise ValueError("choose one driver per appliance")
        if door_magnetic and not door_sensor:
            raise ValueError("door_magnetic requires door_sensor")
        if button_panel and window_motor:
            raise ValueError("button_panel uses GPIO17/27/22 for LEDs; window_motor cannot be used")
        if window_button and not button_panel:
            raise ValueError("window_button requires button_panel")
        if window_button and window_motor:
            raise ValueError("choose window_button or window_motor")
        if door_closer and (not door_sensor or not door_verified):
            raise ValueError("door closer requires verified door sensor")
        if starter and temperature_model not in ("DHT11", "DHT22"):
            raise ValueError("starter profile requires DHT11 or DHT22")
        self._stack = ExitStack()
        self.actuators = {}
        self.door_sensor = self.window_sensor = self.gas_sensor = None
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
                sensor_cls = MagneticDoorSensor if door_magnetic else TouchDoorSensor
                self.door_sensor = self._own(sensor_cls(verified=door_verified))
            if gas_sensor:
                self.gas_sensor = self._own(
                    MQ2GasSensor(active_low=gas_active_low, warmup_seconds=gas_warmup_seconds)
                )
            if window_led:
                self.actuators[WINDOW] = self._own(WindowLED())
            if purifier_led:
                self.actuators[AIR_PURIFIER] = self._own(PurifierLED())
            if dehumidifier_led:
                self.actuators[DEHUMIDIFIER] = self._own(DehumidifierLED())
            if window_motor:
                self.actuators[WINDOW] = self._own(WindowActuator())
            if button_panel:
                if window_button or purifier or dehumidifier:
                    # 패널은 먼저 등록해서 기기들보다 나중에 닫히게 한다 (ExitStack 은 역순)
                    panel = self._own(ButtonServoPanel())
                    devices = button_devices(
                        panel,
                        window=window_button,
                        window_initial=window_initial,
                        window_feedback=(
                            self._window_is_open
                            if self.window_sensor is not None and touch_verified
                            else None
                        ),
                        purifier=purifier,
                        purifier_initial=purifier_initial,
                        dehumidifier=dehumidifier,
                        dehumidifier_initial=dehumidifier_initial,
                    )
                    for name, device in devices.items():
                        self.actuators[name] = self._own(device)
            else:
                if purifier:
                    self.actuators[AIR_PURIFIER] = self._own(
                        ServoButtonPurifier(initially_on=purifier_initial)
                    )
                if dehumidifier:
                    self.actuators[DEHUMIDIFIER] = self._own(
                        ServoButtonDehumidifier(initially_on=dehumidifier_initial)
                    )
            if door_closer:
                self.actuators[DOOR] = self._own(
                    DoorCloserServo(
                        self.door_sensor,
                        rest_angle=door_rest_angle,
                        push_angle=door_push_angle,
                        hold_seconds=door_hold_seconds,
                        return_seconds=door_return_seconds,
                    )
                )
        except BaseException:
            self._stack.close()
            raise

    def _own(self, device):
        self._stack.callback(device.close)
        return device

    def _window_is_open(self) -> bool:
        return self.window_sensor.is_open

    @property
    def gas_detected(self):
        """Read independently of DHT availability; no sensor/unknown is None."""
        return self.gas_sensor.gas_detected if self.gas_sensor is not None else None

    def status(self):
        result = {"sensor_error": self.sensor.last_error, "actuators": {}}
        if self.gas_sensor is not None:
            result["gas"] = {
                "gas_detected": self.gas_detected,
                "warming_up": self.gas_sensor.warming_up,
                "error": self.gas_sensor.last_error,
            }
        for label, sensor in (("window", self.window_sensor), ("door", self.door_sensor)):
            if sensor is not None:
                try:
                    result[label] = {"position": sensor.position, "touch": sensor.touched}
                    if isinstance(sensor, MagneticDoorSensor):
                        result[label]["magnet_present"] = sensor.magnet_present
                except Exception as exc:
                    result[label] = {"position": "unknown", "error": str(exc)}
        for name, device in self.actuators.items():
            try:
                if name == WINDOW and hasattr(device, "position"):
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
