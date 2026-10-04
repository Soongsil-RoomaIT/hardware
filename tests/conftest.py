import time

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin


@pytest.fixture(autouse=True)
def gpio():
    factory = MockFactory(pin_class=MockPWMPin)
    Device.pin_factory = factory
    yield factory
    factory.close()
    Device.pin_factory = None


def wait_for(predicate, timeout=1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "condition timed out"


class FakeServo:
    def __init__(self):
        self.closed = False
        self.history = []
        self._angle = None

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        assert not self.closed, "write after close"
        self._angle = value
        self.history.append(value)

    def detach(self):
        assert not self.closed, "detach after close"
        self._angle = None

    def close(self):
        self.closed = True
