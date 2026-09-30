"""창문 개폐 액추에이터: DC 모터(또는 리니어 액추에이터) + L298N + 리밋 스위치 2개.

set() 은 모터를 돌리기 시작하고 바로 반환한다.
리밋 스위치가 눌리면 gpiozero 콜백에서 모터를 멈추고,
스위치가 고장 나도 모터가 계속 돌지 않도록 타임아웃으로 강제 정지한다.
"""

from __future__ import annotations

import logging
import threading

from gpiozero import Button, Motor

from .. import pins
from ..types import WINDOW

log = logging.getLogger(__name__)


class WindowActuator:
    name = WINDOW

    def __init__(self, speed: float = 0.8, timeout: float = 15.0) -> None:
        self._motor = Motor(
            forward=pins.WINDOW_MOTOR_IN1,
            backward=pins.WINDOW_MOTOR_IN2,
            enable=pins.WINDOW_MOTOR_ENA,
        )
        self._open_sw = Button(pins.WINDOW_LIMIT_OPEN, pull_up=True)
        self._closed_sw = Button(pins.WINDOW_LIMIT_CLOSED, pull_up=True)
        self._speed = speed
        self._timeout = timeout
        self._lock = threading.Lock()
        self._target: bool | None = None
        self._timer: threading.Timer | None = None

        self._open_sw.when_pressed = lambda: self._on_limit(True)
        self._closed_sw.when_pressed = lambda: self._on_limit(False)

    @property
    def is_on(self) -> bool:
        """완전히 열린 상태(열림 리밋 스위치 눌림)일 때만 True."""
        return self._open_sw.is_pressed

    @property
    def is_moving(self) -> bool:
        return self._motor.is_active

    def set(self, on: bool) -> None:
        with self._lock:
            at_target = self._open_sw.is_pressed if on else self._closed_sw.is_pressed
            if at_target:
                self._stop_locked()
                return
            if self.is_moving and self._target == on:
                return  # 이미 그 방향으로 움직이는 중

            self._stop_locked()
            self._target = on
            if on:
                self._motor.forward(self._speed)
            else:
                self._motor.backward(self._speed)
            self._timer = threading.Timer(self._timeout, self._on_timeout)
            self._timer.daemon = True
            self._timer.start()
            log.info("window %s", "opening" if on else "closing")

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def close(self) -> None:
        self.stop()
        self._motor.close()
        self._open_sw.close()
        self._closed_sw.close()

    # --- internal -------------------------------------------------------

    def _on_limit(self, opened: bool) -> None:
        with self._lock:
            if self._target == opened:
                self._stop_locked()
                log.info("window fully %s", "open" if opened else "closed")

    def _on_timeout(self) -> None:
        with self._lock:
            if self.is_moving:
                self._stop_locked()
                log.error("window motor timeout: limit switch not reached")

    def _stop_locked(self) -> None:
        self._motor.stop()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
