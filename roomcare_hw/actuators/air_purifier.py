"""공기청정기 Retrofit: 서보모터로 전원 버튼을 눌러 켜고 끈다.

주의: 버튼이 토글 방식이라 실제 상태를 알 수 없고 소프트웨어가 기억한 상태를 쓴다.
사람이 직접 버튼을 누르면 상태가 어긋난다.
-> 가능하면 전류 센서나 전원 LED 감지(조도 센서) 등으로 실제 상태를 읽도록 개선할 것.
"""

from __future__ import annotations

import threading
import time

from gpiozero import AngularServo

from .. import pins
from ..types import AIR_PURIFIER


class ServoButtonPurifier:
    name = AIR_PURIFIER

    def __init__(
        self,
        rest_angle: float = 0.0,
        press_angle: float = 35.0,
        press_seconds: float = 0.4,
        initially_on: bool = False,
    ) -> None:
        self._servo = AngularServo(pins.PURIFIER_SERVO, min_angle=-90, max_angle=90)
        self._rest = rest_angle
        self._press = press_angle
        self._press_seconds = press_seconds
        self._on = initially_on
        self._lock = threading.Lock()
        self._release()

    @property
    def is_on(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        with self._lock:
            if on == self._on:
                return
            self._on = on
        # 버튼 누르는 동작(~1초)은 백그라운드에서 수행하고 바로 반환
        threading.Thread(target=self._press_button, daemon=True).start()

    def close(self) -> None:
        self._servo.close()

    def _press_button(self) -> None:
        self._servo.angle = self._press
        time.sleep(self._press_seconds)
        self._servo.angle = self._rest
        time.sleep(0.5)
        self._release()

    def _release(self) -> None:
        # 신호를 끊어 대기 중 서보 떨림(jitter)과 소음을 없앤다
        self._servo.detach()
