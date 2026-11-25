"""B-1/B-2/B-4 regression tests. GPIO mock/fake only, not physical acceptance."""

import time
from types import SimpleNamespace

import pytest
from conftest import FakeServo, wait_for

from roomcare_hw import pins
from roomcare_hw.actuators import DehumidifierLED, DoorCloserServo, PurifierLED, WindowLED
from roomcare_hw.bundle import HardwareBundle
from roomcare_hw.sensors import MagneticDoorSensor, MQ2GasSensor
from roomcare_hw.types import (
    AIR_PURIFIER,
    DEHUMIDIFIER,
    DOOR,
    WINDOW,
    HardwareFault,
    PartialReading,
)


@pytest.mark.parametrize(
    "cls,pin",
    [
        (WindowLED, pins.LED_WINDOW),
        (PurifierLED, pins.LED_PURIFIER),
        (DehumidifierLED, pins.LED_DEHUMIDIFIER),
    ],
)
def test_led_persistent_state_and_50_cycles(gpio, cls, pin):
    device = cls()
    try:
        assert device.state_source == "COMMANDED"
        assert not device.is_on
        for _ in range(50):
            device.set(True)
            device.set(True)
            assert device.is_on and gpio.pin(pin).state
            assert not device.is_moving
            device.set(False)
            device.set(False)
            assert not device.is_on and not gpio.pin(pin).state
        device.set(True)
        if isinstance(device, WindowLED):
            assert device.position == "open"
            device.set(False)
            assert device.position == "closed"
            device.set(True)
    finally:
        device.close()
    assert not gpio.pin(pin).state
    assert device.state == "unknown"
    with pytest.raises(HardwareFault):
        device.set(True)


def test_led_error_latches():
    class BadLED:
        is_lit = False
        closed = False

        def on(self):
            raise OSError("GPIO failure")

        def off(self):
            pass

        def close(self):
            self.closed = True

    fake = BadLED()
    device = WindowLED(led=fake)
    try:
        with pytest.raises(HardwareFault, match="GPIO failure"):
            device.set(True)
        assert device.fault and device.position == "unknown"
        with pytest.raises(HardwareFault):
            device.set(False)
    finally:
        device.close()
    assert fake.closed


def test_mc38_active_low_and_callbacks(gpio):
    sensor = MagneticDoorSensor(debounce=None)
    try:
        assert sensor.position == "unknown"
        with pytest.raises(HardwareFault):
            _ = sensor.is_open
        sensor.verified = True
        events = []
        sensor.when_closed = lambda: events.append("closed")
        sensor.when_opened = lambda: events.append("open")
        assert sensor.is_open  # internal pull-up, contact open
        gpio.pin(pins.DOOR_MAGNETIC).drive_low()
        assert sensor.magnet_present and not sensor.is_open
        gpio.pin(pins.DOOR_MAGNETIC).drive_high()
        assert sensor.is_open and not sensor.magnet_present
        wait_for(lambda: events == ["closed", "open"])
    finally:
        sensor.close()


def test_mc38_door_servo_close_only(gpio):
    sensor = MagneticDoorSensor(debounce=None, verified=True)
    servo = FakeServo()
    closer = DoorCloserServo(sensor, servo=servo, hold_seconds=0.1, return_seconds=0.03)
    try:
        gpio.pin(pins.DOOR_MAGNETIC).drive_high()
        with pytest.raises(HardwareFault):
            closer.set(True)
        closer.set(False)
        wait_for(lambda: len(servo.history) >= 1)
        gpio.pin(pins.DOOR_MAGNETIC).drive_low()
        wait_for(lambda: not closer.is_moving)
        assert not closer.is_on
        before = len(servo.history)
        closer.set(False)
        assert not closer.is_moving and len(servo.history) == before
    finally:
        closer.close()
        sensor.close()
    assert servo.closed


@pytest.mark.parametrize("active_low", [True, False])
def test_mq2_polarity_warmup_and_transitions(gpio, active_low):
    sensor = MQ2GasSensor(active_low=active_low, warmup_seconds=60, poll_seconds=0.01)
    try:
        pin = gpio.pin(pins.MQ2_DO)
        normal, detected = (
            (pin.drive_high, pin.drive_low) if active_low else (pin.drive_low, pin.drive_high)
        )
        events = []
        sensor.when_detected = lambda: events.append("detected")
        sensor.when_cleared = lambda: events.append("cleared")
        detected()
        assert sensor.warming_up and sensor.gas_detected is None
        assert events == []
        normal()
        # Advance only this mock sensor's warm-up deadline, no physical bypass.
        sensor._ready_at = time.monotonic() - 1
        wait_for(lambda: sensor.gas_detected is False)
        detected()
        wait_for(lambda: events == ["detected"])
        assert sensor.gas_detected is True
        time.sleep(0.03)
        assert events == ["detected"]
        normal()
        wait_for(lambda: events == ["detected", "cleared"])
        assert sensor.gas_detected is False
    finally:
        sensor.close()
    assert sensor.gas_detected is None


def test_mq2_error_is_unknown_not_false():
    class Input:
        fail = False
        closed = False

        @property
        def is_active(self):
            if self.fail:
                raise OSError("read failed")
            return True

        def close(self):
            self.closed = True

    dev = Input()
    sensor = MQ2GasSensor(device=dev, warmup_seconds=0, poll_seconds=0.01)
    try:
        wait_for(lambda: sensor.gas_detected is True)
        dev.fail = True
        wait_for(lambda: sensor.last_error is not None)
        assert sensor.gas_detected is None
        dev.fail = False
        wait_for(lambda: sensor.gas_detected is True)
    finally:
        sensor.close()
    assert dev.closed


@pytest.mark.parametrize(
    "opts",
    [
        {"window_led": True, "window_motor": True},
        {"purifier_led": True, "button_panel": True},
        {"purifier_led": True, "purifier": True},
        {"dehumidifier_led": True, "dehumidifier": True},
        {"door_magnetic": True},
        {"door_magnetic": True, "door_sensor": True, "door_closer": True},
    ],
)
def test_conflicting_profiles_rejected_before_gpio(opts):
    with pytest.raises(ValueError):
        HardwareBundle(**opts)


def test_v14_bundle_dht_only_leds_mc38_and_gas(monkeypatch, gpio):
    dht = SimpleNamespace(read=lambda: PartialReading(time.time(), 24, 55), close=lambda: None)
    monkeypatch.setattr("roomcare_hw.bundle.DHTReader", lambda **_: dht)

    def forbidden(**_):
        raise AssertionError("CO2/PM sensors must not be initialized")

    monkeypatch.setattr("roomcare_hw.bundle.RoomSensorReader", forbidden)
    with HardwareBundle(
        starter=True,
        temperature_model="DHT11",
        window_led=True,
        purifier_led=True,
        dehumidifier_led=True,
        door_sensor=True,
        door_magnetic=True,
        door_verified=True,
        door_closer=True,
        gas_sensor=True,
        gas_warmup_seconds=0,
    ) as hw:
        assert set(hw.actuators) == {WINDOW, AIR_PURIFIER, DEHUMIDIFIER, DOOR}
        assert isinstance(hw.door_sensor, MagneticDoorSensor)
        wait_for(lambda: hw.sensor.last_error is None)
        reading = hw.sensor.read()
        assert reading.co2 is reading.pm25 is reading.pm10 is None
        gpio.pin(pins.MQ2_DO).drive_low()
        wait_for(lambda: hw.gas_detected is True)
        assert hw.status()["gas"]["gas_detected"] is True
        for name in (WINDOW, AIR_PURIFIER, DEHUMIDIFIER):
            hw.actuators[name].set(True)
        assert hw.status()["actuators"][WINDOW]["state"] == "open"
    for pin in (pins.LED_WINDOW, pins.LED_PURIFIER, pins.LED_DEHUMIDIFIER):
        assert not gpio.pin(pin).state
    assert hw.gas_detected is None
