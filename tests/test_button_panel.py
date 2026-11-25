import threading

import pytest
from conftest import FakeServo, wait_for

from roomcare_hw import pins
from roomcare_hw.actuators.button_panel import ButtonServoPanel, ServoButtonWindow, button_devices
from roomcare_hw.bundle import HardwareBundle
from roomcare_hw.types import AIR_PURIFIER, DEHUMIDIFIER, WINDOW

FAST = dict(press_seconds=0.03, settle_seconds=0.03)


class FakeLed:
    def __init__(self, name, log):
        self.name = name
        self.log = log
        self.is_lit = False
        self.closed = False

    def on(self):
        self.is_lit = True
        self.log.append(("on", self.name))

    def off(self):
        self.is_lit = False
        self.log.append(("off", self.name))

    def close(self):
        self.closed = True


class LoggingServo(FakeServo):
    def __init__(self, log):
        super().__init__()
        self.log = log

    @FakeServo.angle.setter
    def angle(self, value):
        FakeServo.angle.fset(self, value)
        self.log.append(("angle", value))

    def detach(self):
        super().detach()
        self.log.append(("detach",))


def make_panel():
    log = []
    leds = {name: FakeLed(name, log) for name in (WINDOW, AIR_PURIFIER, DEHUMIDIFIER)}
    servo = LoggingServo(log)
    panel = ButtonServoPanel(servo=servo, leds=leds)
    log.clear()  # 생성 시 LED off / detach 기록은 빼고 본다
    return panel, servo, leds, log


def test_led_is_lit_only_while_servo_moves():
    panel, servo, leds, log = make_panel()
    purifier = button_devices(panel, purifier=True, purifier_initial=False, **FAST)[AIR_PURIFIER]

    purifier.set(True)
    wait_for(lambda: not purifier.is_moving)

    assert log == [
        ("on", AIR_PURIFIER),
        ("angle", 35.0),
        ("angle", 0.0),
        ("detach",),
        ("off", AIR_PURIFIER),
    ]
    assert purifier.state == "on"
    assert not any(led.is_lit for led in leds.values())
    purifier.close()
    panel.close()


def test_every_device_uses_the_same_servo_with_its_own_led():
    panel, servo, leds, log = make_panel()
    devices = button_devices(
        panel,
        window=True,
        window_initial=False,
        purifier=True,
        purifier_initial=False,
        dehumidifier=True,
        dehumidifier_initial=True,
        **FAST,
    )

    devices[WINDOW].set(True)
    wait_for(lambda: not devices[WINDOW].is_moving)
    devices[DEHUMIDIFIER].set(False)
    wait_for(lambda: not devices[DEHUMIDIFIER].is_moving)

    lit = [name for action, *rest in log if action == "on" for name in rest]
    assert lit == [WINDOW, DEHUMIDIFIER]
    assert servo.history == [35.0, 0.0, 35.0, 0.0]  # 기기와 상관없이 같은 동작
    assert devices[WINDOW].state == "on" and devices[DEHUMIDIFIER].state == "off"
    for device in devices.values():
        device.close()
    panel.close()


def test_overlapping_commands_press_one_at_a_time():
    panel, servo, leds, log = make_panel()
    devices = button_devices(
        panel, window=True, window_initial=True, purifier=True, purifier_initial=False, **FAST
    )
    max_lit = []

    def watch():
        while not done.is_set():
            max_lit.append(sum(led.is_lit for led in leds.values()))

    done = threading.Event()
    watcher = threading.Thread(target=watch)
    watcher.start()
    devices[WINDOW].set(False)
    devices[AIR_PURIFIER].set(True)
    wait_for(lambda: not devices[WINDOW].is_moving and not devices[AIR_PURIFIER].is_moving)
    done.set()
    watcher.join()

    assert max(max_lit) == 1  # LED(=서보 사용 중인 기기)는 한 번에 하나만
    assert servo.history == [35.0, 0.0, 35.0, 0.0]
    assert devices[WINDOW].state == "off" and devices[AIR_PURIFIER].state == "on"
    for device in devices.values():
        device.close()
    panel.close()


def test_same_state_does_not_press():
    panel, servo, leds, log = make_panel()
    window = button_devices(panel, window=True, window_initial=True, **FAST)[WINDOW]

    window.set(True)
    wait_for(lambda: not window.is_moving)

    assert servo.history == [] and log == []
    window.close()
    panel.close()


def test_unknown_initial_state_is_not_pressed():
    panel, servo, leds, log = make_panel()
    window = button_devices(panel, window=True, **FAST)[WINDOW]

    assert window.state == "unknown"
    with pytest.raises(Exception, match="unknown"):
        window.set(True)
    assert servo.history == []
    window.close()
    panel.close()


def test_closing_one_device_does_not_stop_another_press():
    panel, servo, leds, log = make_panel()
    devices = button_devices(
        panel, window=True, window_initial=False, purifier=True, purifier_initial=False, **FAST
    )
    devices[WINDOW].close()  # 잡고 있지 않은 채널의 detach 는 서보를 건드리지 않아야 함

    devices[AIR_PURIFIER].set(True)
    wait_for(lambda: not devices[AIR_PURIFIER].is_moving)

    assert devices[AIR_PURIFIER].state == "on"
    devices[AIR_PURIFIER].close()
    panel.close()
    assert servo.closed and all(led.closed for led in leds.values())


def test_window_button_has_window_name():
    assert ServoButtonWindow.name == WINDOW


# --- HardwareBundle (gpiozero mock 핀) ----------------------------------------


def test_bundle_button_panel_uses_planned_pins(gpio, monkeypatch):
    monkeypatch.setattr("roomcare_hw.bundle.RoomSensorReader", lambda **_: _NoSensor())
    with HardwareBundle(
        button_panel=True,
        window_button=True,
        window_initial=False,
        purifier=True,
        purifier_initial=False,
        dehumidifier=True,
        dehumidifier_initial=False,
    ) as hw:
        assert set(hw.actuators) == {WINDOW, AIR_PURIFIER, DEHUMIDIFIER}
        assert isinstance(hw.actuators[WINDOW], ServoButtonWindow)
        opened = {name for info in gpio.pins for name in info.names}
        used = {pins.BUTTON_SERVO, pins.LED_WINDOW, pins.LED_PURIFIER, pins.LED_DEHUMIDIFIER}
        assert {f"GPIO{n}" for n in used} <= opened
        assert f"GPIO{pins.DEHUMIDIFIER_SERVO}" not in opened  # 가전별 서보는 만들지 않음
        assert hw.status()["actuators"][WINDOW]["state"] == "off"


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (dict(button_panel=True, window_motor=True), "window_motor"),
        (dict(window_button=True), "button_panel"),
    ],
)
def test_bundle_rejects_conflicting_options(kwargs, message):
    with pytest.raises(ValueError, match=message):
        HardwareBundle(**kwargs)


class _NoSensor:
    def read(self):
        raise OSError("no sensor in test")

    def close(self):
        pass
