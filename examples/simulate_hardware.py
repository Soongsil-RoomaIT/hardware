"""PC-only demo using gpiozero MockFactory. NO real sensors or motors are used."""

import json
import time

from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin

from roomcare_hw.actuators import WindowActuator
from roomcare_hw.sensors import TouchWindowSensor


def wait_until(predicate):
    end = time.monotonic() + 1
    while not predicate():
        if time.monotonic() >= end:
            raise TimeoutError("simulation step failed")
        time.sleep(0.01)


def main():
    factory = MockFactory(pin_class=MockPWMPin)
    Device.pin_factory = factory
    window = WindowActuator(timeout=0.2)
    touch = TouchWindowSensor(verified=True)
    try:
        print("SIMULATION: 실제 하드웨어 측정/동작이 아닙니다.")
        factory.pin(24).drive_high()
        print(json.dumps({"simulated_touch_window": touch.position}))
        window.set(True)
        wait_until(lambda: window._motor.is_active)
        factory.pin(5).drive_low()
        wait_until(lambda: not window.is_moving)
        print(json.dumps({"simulated_motor_window": window.position}))
        factory.pin(5).drive_high()
        window.set(False)
        wait_until(lambda: window.fault is not None)
        print(
            json.dumps(
                {"simulated_limit_failure": window.fault, "motor_stopped": not window.is_moving}
            )
        )
    finally:
        touch.close()
        window.close()
        factory.close()


if __name__ == "__main__":
    main()
