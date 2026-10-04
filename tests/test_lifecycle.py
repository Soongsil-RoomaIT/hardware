from types import SimpleNamespace

import pytest
from conftest import FakeServo, wait_for

from roomcare_hw.actuators import DoorCloserServo, ServoButtonPurifier, WindowActuator
from roomcare_hw.bundle import HardwareBundle
from roomcare_hw.types import HardwareFault


def test_no_hardware_side_effects_for_invalid_bundle():
    with pytest.raises(ValueError):
        HardwareBundle(door_closer=True)
    with pytest.raises(ValueError):
        HardwareBundle(starter=True)


def test_bundle_starter_and_reverse_cleanup(monkeypatch):
    events = []

    class Source:
        def __init__(self, **kwargs):
            events.append("source-created")

        def close(self):
            events.append("source-closed")

    class Cache:
        last_error = None

        def __init__(self, source):
            self.source = source

        def close(self):
            self.source.close()

    class Touch:
        position = "unknown"
        touched = False

        def __init__(self, **kwargs):
            pass

        def close(self):
            events.append("touch-closed")

    monkeypatch.setattr("roomcare_hw.bundle.DHTReader", Source)
    monkeypatch.setattr("roomcare_hw.bundle.CachedSensorReader", Cache)
    monkeypatch.setattr("roomcare_hw.bundle.TouchWindowSensor", Touch)
    with HardwareBundle(starter=True, temperature_model="DHT11", window_touch=True) as hw:
        assert not hw.actuators
        assert hw.status()["window"]["position"] == "unknown"
    hw.close()
    assert events == ["source-created", "touch-closed", "source-closed"]


def test_bundle_partial_initialization_releases_previous_resources(monkeypatch):
    source = SimpleNamespace(close=lambda: calls.append("source"))
    calls = []
    monkeypatch.setattr("roomcare_hw.bundle.RoomSensorReader", lambda **kw: source)
    monkeypatch.setattr("roomcare_hw.bundle.CachedSensorReader", lambda source: source)

    def fail():
        raise IOError("motor missing")

    monkeypatch.setattr("roomcare_hw.bundle.WindowActuator", fail)
    with pytest.raises(IOError):
        HardwareBundle(window_motor=True)
    assert calls == ["source"]


class BrokenServo(FakeServo):
    @FakeServo.angle.setter
    def angle(self, value):
        raise IOError("PWM backend failed")


def test_button_backend_error_latches_and_thread_cleans_up():
    servo = BrokenServo()
    device = ServoButtonPurifier(servo=servo, initially_on=False)
    try:
        device.set(True)
        wait_for(lambda: device.fault is not None)
        assert not device.is_moving
        assert device.state == "unknown"
        with pytest.raises(HardwareFault):
            device.set(True)
    finally:
        device.close()
    assert servo.closed


def test_door_backend_error_and_immediate_close():
    device = DoorCloserServo(SimpleNamespace(is_open=True), servo=BrokenServo())
    try:
        device.push()
        wait_for(lambda: device.fault is not None)
        assert not device.is_moving
    finally:
        device.close()
    device = DoorCloserServo(SimpleNamespace(is_open=True), servo=FakeServo())
    device.push()
    device.close()  # also covers shutdown while the request is still queued
    assert not device.is_moving
    with pytest.raises(HardwareFault):
        device.set(False)


def test_motor_backend_failure_is_observable(monkeypatch):
    device = WindowActuator()

    def fail(*args):
        raise IOError("motor backend failed")

    monkeypatch.setattr(device._motor, "forward", fail)
    try:
        device.set(True)
        wait_for(lambda: device.fault is not None)
        assert "motor backend failed" in device.fault
        assert not device.is_moving
    finally:
        device.close()
