"""문 닫기: 터치센서로 열림 감지 -> 서보로 문을 밀어서 닫는다.

- DoorCloserServo : 서보 한 번 스윙(밀기 -> 복귀). edge_agent 원격 조작용 Actuator("door").
- DoorAutoCloser  : 문이 열리고 close_delay 초가 지나도 열려 있으면 자동으로 닫는다.
                    사람이 드나드는 중에 바로 닫지 않도록 지연을 둔다.
"""

from __future__ import annotations

import logging
import threading
import time

from gpiozero import AngularServo

from .. import pins
from ..types import DOOR, DoorSensor

log = logging.getLogger(__name__)


class DoorCloserServo:
    """Actuator 인터페이스. on = 문 열림. 서보는 닫기만 할 수 있다."""

    name = DOOR

    def __init__(
        self,
        sensor: DoorSensor,
        pin: int = pins.DOOR_SERVO,
        rest_angle: float = -60.0,
        push_angle: float = 60.0,
        hold_seconds: float = 1.0,
    ) -> None:
        self._sensor = sensor
        self._servo = AngularServo(pin, min_angle=-90, max_angle=90)
        self._rest = rest_angle
        self._push = push_angle
        self._hold = hold_seconds
        self._busy = threading.Lock()
        self._servo.detach()

    @property
    def is_on(self) -> bool:
        return self._sensor.is_open

    @property
    def is_moving(self) -> bool:
        return self._busy.locked()

    def set(self, on: bool) -> None:
        if on:
            log.warning("door servo cannot open the door; ignored")
            return
        if not self._sensor.is_open:
            return
        self.push()

    def push(self) -> None:
        """서보 스윙을 백그라운드에서 시작하고 바로 반환. 이미 움직이는 중이면 무시."""
        if not self._busy.acquire(blocking=False):
            return
        threading.Thread(target=self._swing, daemon=True).start()

    def close(self) -> None:
        self._servo.close()

    def _swing(self) -> None:
        try:
            log.info("door servo: pushing")
            self._servo.angle = self._push
            time.sleep(self._hold)
            self._servo.angle = self._rest
            time.sleep(0.8)
            self._servo.detach()  # 대기 중 떨림 방지, 사람이 문을 열 때 서보가 버티지 않도록
        finally:
            self._busy.release()


class DoorAutoCloser:
    """문이 열린 채로 close_delay 초가 지나면 서보로 닫는다. 실패하면 max_attempts 번까지 재시도."""

    def __init__(
        self,
        sensor,  # TouchDoorSensor (when_opened / when_closed 콜백 필요)
        closer: DoorCloserServo,
        close_delay: float = 10.0,
        retry_delay: float = 3.0,
        max_attempts: int = 3,
    ) -> None:
        self._sensor = sensor
        self._closer = closer
        self._close_delay = close_delay
        self._retry_delay = retry_delay
        self._max_attempts = max_attempts
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._attempts = 0
        self.enabled = True

        sensor.when_opened = self._on_opened
        sensor.when_closed = self._on_closed
        if sensor.is_open:
            self._on_opened()

    def stop(self) -> None:
        with self._lock:
            self._cancel_locked()

    def _on_opened(self) -> None:
        log.info("door opened")
        with self._lock:
            self._attempts = 0
            self._schedule_locked(self._close_delay)

    def _on_closed(self) -> None:
        log.info("door closed")
        with self._lock:
            self._cancel_locked()

    def _try_close(self) -> None:
        with self._lock:
            self._timer = None
            if not self.enabled or not self._sensor.is_open:
                return
            if self._attempts >= self._max_attempts:
                log.error("door still open after %d attempts; giving up", self._attempts)
                return
            self._attempts += 1
            log.info("auto-closing door (attempt %d/%d)", self._attempts, self._max_attempts)
            self._closer.push()
            # 스윙이 끝난 뒤에도 열려 있으면 다시 시도
            self._schedule_locked(self._retry_delay)

    def _schedule_locked(self, delay: float) -> None:
        self._cancel_locked()
        self._timer = threading.Timer(delay, self._try_close)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
