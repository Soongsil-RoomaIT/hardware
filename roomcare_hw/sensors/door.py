"""문 열림 감지: TTP223 정전식 터치센서.

문이 닫히면 문짝(에 붙인 금속 테이프 등)이 센서 패드에 닿도록 설치한다.
    닿음(HIGH)   -> 닫힘
    안 닿음(LOW) -> 열림
반대로 설치했다면 touched_means_closed=False.
"""

from __future__ import annotations

from typing import Callable

from gpiozero import DigitalInputDevice

from .. import pins


class TouchDoorSensor:
    def __init__(
        self,
        pin: int = pins.DOOR_TOUCH,
        touched_means_closed: bool = True,
        debounce: float = 0.2,
    ) -> None:
        # TTP223 은 자체적으로 HIGH/LOW 를 출력하므로 풀업/풀다운 없이 읽는다
        self._dev = DigitalInputDevice(
            pin, pull_up=None, active_state=True, bounce_time=debounce
        )
        self._touched_means_closed = touched_means_closed
        self.when_opened: Callable[[], None] | None = None
        self.when_closed: Callable[[], None] | None = None
        self._dev.when_activated = self._on_touch
        self._dev.when_deactivated = self._on_release

    @property
    def is_open(self) -> bool:
        touched = self._dev.is_active
        return not touched if self._touched_means_closed else touched

    def close(self) -> None:
        self._dev.close()

    def _on_touch(self) -> None:
        self._fire(self.when_closed if self._touched_means_closed else self.when_opened)

    def _on_release(self) -> None:
        self._fire(self.when_opened if self._touched_means_closed else self.when_closed)

    @staticmethod
    def _fire(callback: Callable[[], None] | None) -> None:
        if callback is not None:
            callback()
