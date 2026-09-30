"""PMS7003 미세먼지 센서 (UART, 9600bps).

센서가 약 1초마다 32바이트 프레임을 보낸다:
    [0x42 0x4D][길이 2B][데이터 13 x 2B][체크섬 2B]
체크섬 = 앞 30바이트의 합.
"""

from __future__ import annotations

import struct

import serial

FRAME_LEN = 32
START = b"\x42\x4d"


class PMS7003:
    def __init__(self, port: str, timeout: float = 2.0) -> None:
        self._serial = serial.Serial(port, baudrate=9600, timeout=timeout)

    def read_pm25(self) -> float:
        """대기환경 기준(atmospheric) PM2.5 값 (ug/m3)."""
        frame = self._read_frame()
        # 데이터 워드: pm1_cf1, pm25_cf1, pm10_cf1, pm1_atm, pm25_atm, pm10_atm, ...
        words = struct.unpack(">13H", frame[4:30])
        return float(words[4])

    def _read_frame(self) -> bytes:
        # 버퍼에 오래된 프레임이 쌓여 있을 수 있으니 비우고 최신 프레임을 읽는다
        self._serial.reset_input_buffer()
        for _ in range(10):
            if self._serial.read(1) != START[:1] or self._serial.read(1) != START[1:]:
                continue
            rest = self._serial.read(FRAME_LEN - 2)
            if len(rest) != FRAME_LEN - 2:
                continue
            frame = START + rest
            checksum = struct.unpack(">H", frame[30:32])[0]
            if sum(frame[:30]) == checksum:
                return frame
        raise IOError("PMS7003: valid frame not received")

    def close(self) -> None:
        self._serial.close()
