"""edge_agent 와 약속한 인터페이스.

edge_agent/src/edge_agent/devices.py 와 필드 이름/단위가 반드시 같아야 한다.
바꿀 때는 엣지 담당과 같이 바꾼다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Reading:
    measured_at: float  # unix time (time.time())
    temperature: float  # C
    humidity: float  # %RH
    co2: float  # ppm
    pm25: float  # ug/m3


class SensorReader(Protocol):
    def read(self) -> Reading: ...


class DoorSensor(Protocol):
    """문 열림 감지 센서."""

    @property
    def is_open(self) -> bool: ...


class Actuator(Protocol):
    """켜짐/꺼짐 두 상태. 창문은 on = 완전히 열림, 문은 on = 열림."""

    name: str

    @property
    def is_on(self) -> bool: ...

    def set(self, on: bool) -> None:
        """목표 상태로 동작을 '시작'하고 바로 반환해야 한다 (오래 막으면 엣지 루프가 멈춘다)."""
        ...


# 액추에이터 이름 (MQTT 명령에서도 이 이름을 쓴다)
WINDOW = "window"
AIR_PURIFIER = "air_purifier"
DOOR = "door"  # 닫기만 가능 (set(False))
DEHUMIDIFIER = "dehumidifier"  # edge_agent의 명령 allowlist 확장이 필요


@dataclass(frozen=True)
class PartialReading:
    """실습 전용. 미장착 센서를 0으로 위조하지 않는다. 기존 Reading과 별개."""

    measured_at: float
    temperature: float
    humidity: float
    co2: float | None = None
    pm25: float | None = None


class HardwareFault(RuntimeError):
    """명령을 수행할 수 없는 상태. 사용자 점검/복구가 필요하다."""
