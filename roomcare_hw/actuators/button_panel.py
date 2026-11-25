"""버튼 서보 하나를 창문/공기청정기/제습기가 같이 쓰는 구성.

- 어떤 기기 명령이든 서보는 같은 동작(누름 -> 원위치)을 한다.
- 누르는 동안 그 기기의 LED 가 켜지고, 서보 동작이 끝나면 꺼진다 (어느 기기 버튼인지 표시).
- 서보가 하나라서 동시에 누를 수 없다. 여러 기기 명령이 겹치면 먼저 잡은 순서대로 하나씩 누른다.

기기 쪽 로직(상태 추정, 같은 명령 반복 무시, 종료 처리)은 ServoButtonPurifier 를 그대로 쓰고,
서보 자리에 이 패널의 채널(_ButtonChannel)을 넘긴다.
"""

from __future__ import annotations

import threading

from gpiozero import LED, AngularServo

from .. import pins
from ..types import AIR_PURIFIER, DEHUMIDIFIER, WINDOW, HardwareFault
from .air_purifier import ServoButtonDehumidifier, ServoButtonPurifier

DEFAULT_LED_PINS = {
    WINDOW: pins.LED_WINDOW,
    AIR_PURIFIER: pins.LED_PURIFIER,
    DEHUMIDIFIER: pins.LED_DEHUMIDIFIER,
}


class ButtonServoPanel:
    def __init__(
        self,
        pin: int = pins.BUTTON_SERVO,
        led_pins: dict[str, int] | None = None,
        *,
        servo=None,
        leds: dict | None = None,
        wait_seconds: float = 10.0,
    ):
        if wait_seconds <= 0:
            raise ValueError("wait_seconds must be positive")
        self._wait = wait_seconds
        self._lock = threading.Lock()
        self._closed = False
        self._leds: dict = {}
        self._servo = servo if servo is not None else AngularServo(pin, initial_angle=None)
        try:
            if leds is not None:
                self._leds = dict(leds)
            else:
                for name, led_pin in (led_pins or DEFAULT_LED_PINS).items():
                    self._leds[name] = LED(led_pin)
            for led in self._leds.values():
                led.off()
            self._servo.detach()
        except BaseException:
            self._close_hardware()
            raise

    def channel(self, name: str) -> _ButtonChannel:
        if name not in self._leds:
            raise ValueError(f"no LED for {name}")
        return _ButtonChannel(self, name)

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._close_hardware()

    def _close_hardware(self):
        try:
            for led in self._leds.values():
                try:
                    led.off()
                finally:
                    led.close()
        finally:
            try:
                self._servo.detach()
            finally:
                self._servo.close()


class _ButtonChannel:
    """한 기기 몫의 서보 대리 객체. ServoButtonPurifier 의 servo 자리에 넘긴다.

    누르기 시작(angle 설정)할 때 서보를 잡고 LED 를 켜고, detach 할 때 LED 를 끄고 서보를 놓는다.
    잡고 있지 않을 때의 detach/close 는 아무것도 하지 않는다 (다른 기기가 누르는 중일 수 있음).
    """

    def __init__(self, panel: ButtonServoPanel, name: str):
        self._panel = panel
        self._name = name
        self._holding = False

    @property
    def angle(self):
        return self._panel._servo.angle if self._holding else None

    @angle.setter
    def angle(self, value):
        panel = self._panel
        if not self._holding:
            if panel._closed:
                raise HardwareFault("button panel closed")
            if not panel._lock.acquire(timeout=panel._wait):
                raise HardwareFault("button servo busy too long")
            self._holding = True
            panel._leds[self._name].on()
        panel._servo.angle = value

    def detach(self):
        if not self._holding:
            return
        panel = self._panel
        try:
            panel._servo.detach()
        finally:
            try:
                panel._leds[self._name].off()
            finally:
                self._holding = False
                panel._lock.release()

    def close(self):
        self.detach()


class ServoButtonWindow(ServoButtonPurifier):
    """버튼으로 여닫는 창문 (on = 열림). 상태는 누른 횟수로 추정한다."""

    name = WINDOW


def button_devices(
    panel: ButtonServoPanel,
    *,
    window: bool = False,
    window_initial: bool | None = None,
    purifier: bool = False,
    purifier_initial: bool | None = None,
    dehumidifier: bool = False,
    dehumidifier_initial: bool | None = None,
    **button_kwargs,
) -> dict:
    """패널을 공유하는 버튼 기기들을 만든다. 만든 기기는 호출한 쪽이 close 한다."""
    specs = (
        (window, ServoButtonWindow, window_initial),
        (purifier, ServoButtonPurifier, purifier_initial),
        (dehumidifier, ServoButtonDehumidifier, dehumidifier_initial),
    )
    devices = {}
    try:
        for enabled, cls, initial in specs:
            if enabled:
                device = cls(initially_on=initial, servo=panel.channel(cls.name), **button_kwargs)
                devices[cls.name] = device
    except BaseException:
        for device in devices.values():
            device.close()
        raise
    return devices
