import time
from types import SimpleNamespace

import pytest
from conftest import FakeServo, wait_for

from roomcare_hw.actuators import (
    DoorAutoCloser,
    DoorCloserServo,
    ServoButtonDehumidifier,
    ServoButtonPurifier,
    WindowActuator,
)
from roomcare_hw.types import HardwareFault


def test_window_nonblocking_limit_and_repeat(gpio):
    w = WindowActuator(timeout=0.4)
    try:
        start = time.monotonic()
        w.set(True)
        assert time.monotonic() - start < 0.05
        wait_for(lambda: w._motor.is_active)
        for _ in range(100):
            w.set(True)
        gpio.pin(5).drive_low()
        wait_for(lambda: not w.is_moving)
        assert w.is_on and w.position == "open"
        assert not w._motor.is_active
    finally:
        w.close()
    w.close()


def test_window_timeout_is_latched_despite_repeated_commands():
    w = WindowActuator(timeout=0.04)
    try:
        w.set(True)
        wait_for(lambda: w._motor.is_active)
        for _ in range(10):
            w.set(True)
        wait_for(lambda: w.fault is not None)
        assert not w._motor.is_active
        with pytest.raises(HardwareFault):
            w.set(True)
        w.reset_fault()
        w.set(False)
        wait_for(lambda: w._motor.value < 0)
    finally:
        w.close()


def test_window_reversal_pause_and_closed_feedback(gpio):
    w = WindowActuator(reverse_pause=0.08)
    try:
        w.set(True)
        wait_for(lambda: w._motor.value > 0)
        w.set(False)
        wait_for(lambda: w._motor.value == 0)
        time.sleep(0.02)
        assert w._motor.value == 0
        wait_for(lambda: w._motor.value < 0)
        gpio.pin(6).drive_low()
        wait_for(lambda: not w.is_moving)
        assert w.position == "closed" and not w.is_on
    finally:
        w.close()


def test_window_conflicting_limits_and_obstruction(gpio):
    blocked = [False]
    w = WindowActuator(obstruction=lambda: blocked[0])
    try:
        w.set(True)
        wait_for(lambda: w._motor.is_active)
        blocked[0] = True
        wait_for(lambda: w.fault is not None)
        assert not w._motor.is_active
        with pytest.raises(HardwareFault):
            w.reset_fault()
        blocked[0] = False
        w.reset_fault()
        gpio.pin(5).drive_low()
        gpio.pin(6).drive_low()
        with pytest.raises(HardwareFault):
            w.set(True)
        assert w.position == "fault"
    finally:
        w.close()


def test_window_unknown_is_not_closed():
    w = WindowActuator()
    try:
        assert w.position == "unknown"
        w.set(True)
        w.stop()
        assert not w.is_moving
    finally:
        w.close()
    with pytest.raises(HardwareFault):
        w.set(True)


def test_button_requires_known_state():
    servo = FakeServo()
    p = ServoButtonPurifier(servo=servo)
    try:
        with pytest.raises(HardwareFault):
            p.set(True)
        with pytest.raises(HardwareFault):
            _ = p.is_on
        assert servo.history == []
        p.confirm_state(False)
        assert p.is_on is False
    finally:
        p.close()


def test_button_repeat_does_not_double_toggle_and_reversal_serialized():
    servo = FakeServo()
    p = ServoButtonPurifier(
        servo=servo, initially_on=False, press_seconds=0.025, settle_seconds=0.025
    )
    try:
        for _ in range(100):
            p.set(True)
        wait_for(lambda: not p.is_moving)
        assert servo.history == [35, 0]
        assert p.is_on is True
        p.set(False)
        wait_for(lambda: p._busy)
        p.set(True)
        wait_for(lambda: not p.is_moving)
        assert servo.history == [35, 0, 35, 0, 35, 0]
        assert p.is_on
    finally:
        p.close()


def test_button_feedback_failure_latches():
    p = ServoButtonPurifier(
        servo=FakeServo(), feedback=lambda: False, press_seconds=0.01, settle_seconds=0.01
    )
    try:
        p.set(True)
        wait_for(lambda: p.fault is not None)
        assert p.state == "unknown"
        with pytest.raises(HardwareFault):
            p.set(True)
    finally:
        p.close()


def test_button_shutdown_interrupts_worker_and_no_write_after_close():
    servo = FakeServo()
    p = ServoButtonPurifier(servo=servo, initially_on=False, press_seconds=10)
    p.set(True)
    wait_for(lambda: p._busy)
    start = time.monotonic()
    p.close()
    assert time.monotonic() - start < 0.2
    assert servo.closed
    p.close()
    with pytest.raises(HardwareFault):
        p.set(True)


def test_dehumidifier_name_and_independent_pin():
    p = ServoButtonDehumidifier(initially_on=False)
    try:
        assert p.name == "dehumidifier"
        assert p._servo.pwm_device.pin.info.name == "GPIO12"
    finally:
        p.close()


def test_door_reject_open_and_duplicate_close():
    servo = FakeServo()
    sensor = SimpleNamespace(is_open=True)
    d = DoorCloserServo(sensor, servo=servo, hold_seconds=0.02, return_seconds=0.02)
    try:
        with pytest.raises(HardwareFault):
            d.set(True)
        for _ in range(100):
            d.set(False)
        wait_for(lambda: not d.is_moving)
        d.set(False)
        time.sleep(0.01)
        assert servo.history == [60, -60]
        assert d.is_on  # never claim successful close without feedback
        sensor.is_open = False
        d.set(False)
        sensor.is_open = True
        d.set(False)
        wait_for(lambda: not d.is_moving)
        assert len(servo.history) == 4
    finally:
        d.close()


def test_door_shutdown_cancels_long_swing():
    servo = FakeServo()
    d = DoorCloserServo(SimpleNamespace(is_open=True), servo=servo, hold_seconds=10)
    d.push()
    wait_for(lambda: len(servo.history) > 0)
    d.close()
    assert servo.closed and not d.is_moving
    d.close()


def test_auto_default_600_and_stop_disarms():
    sensor = SimpleNamespace(is_open=True)
    closer = SimpleNamespace(is_moving=False, push=lambda: pytest.fail("should not move"))
    auto = DoorAutoCloser(sensor, closer, poll_interval=0.005)
    assert auto._delay == 600
    auto.stop()
    sensor.is_open = False
    sensor.is_open = True
    assert not auto.enabled


def test_auto_bounded_retries_only_after_movement():
    sensor = SimpleNamespace(is_open=True)

    class Closer:
        is_moving = False
        count = 0

        def push(self):
            self.count += 1
            self.is_moving = True
            return True

    closer = Closer()
    auto = DoorAutoCloser(
        sensor, closer, close_delay=0.015, retry_delay=0.01, max_attempts=2, poll_interval=0.005
    )
    try:
        wait_for(lambda: closer.count == 1)
        time.sleep(0.03)
        assert closer.count == 1
        closer.is_moving = False
        wait_for(lambda: closer.count == 2)
        closer.is_moving = False
        wait_for(lambda: auto.last_error is not None)
        time.sleep(0.03)
        assert closer.count == 2
    finally:
        auto.stop()


def test_auto_close_before_delay_cancels_and_disable_resets():
    sensor = SimpleNamespace(is_open=True)
    closer = SimpleNamespace(is_moving=False, push=lambda: pytest.fail("unexpected push"))
    auto = DoorAutoCloser(sensor, closer, close_delay=0.1, poll_interval=0.005)
    try:
        wait_for(lambda: auto._opened_at is not None)
        sensor.is_open = False
        wait_for(lambda: auto._opened_at is None)
        sensor.is_open = True
        auto.enabled = False
        time.sleep(0.12)
        assert auto.attempts == 0
    finally:
        auto.stop()


@pytest.mark.parametrize(
    "build",
    [
        lambda: WindowActuator(speed=2),
        lambda: WindowActuator(timeout=float("nan")),
        lambda: ServoButtonPurifier(press_angle=120),
        lambda: DoorCloserServo(None, hold_seconds=-1),
    ],
)
def test_invalid_calibration_rejected_before_gpio(build):
    with pytest.raises(ValueError):
        build()
