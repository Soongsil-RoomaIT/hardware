"""PMS7003 active-mode frames: length/checksum validation and bounded resync."""

from __future__ import annotations

import math
import struct
import time

FRAME_LEN = 32
START = b"\x42\x4d"


def parse_frame(frame: bytes) -> float:
    if len(frame) != FRAME_LEN or frame[:2] != START:
        raise IOError("PMS7003: invalid frame header/size")
    if int.from_bytes(frame[2:4], "big") != 28:
        raise IOError("PMS7003: invalid frame length")
    if sum(frame[:30]) != int.from_bytes(frame[30:32], "big"):
        raise IOError("PMS7003: checksum mismatch")
    if frame[29] != 0:
        raise IOError(f"PMS7003: device error {frame[29]}")
    return float(struct.unpack(">H", frame[12:14])[0])  # atmospheric PM2.5


class PMS7003:
    def __init__(self, port: str, timeout: float = 1.5, *, serial_port=None) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if serial_port is None:
            import serial

            serial_port = serial.Serial(port, baudrate=9600, timeout=min(timeout, 0.1))
        self._serial = serial_port
        self._timeout = timeout

    def read_pm25(self) -> float:
        # Discard queued stale frames; read a new one within ONE overall deadline.
        self._serial.reset_input_buffer()
        end = time.monotonic() + self._timeout
        buffer = bytearray()
        while time.monotonic() < end:
            self._serial.timeout = min(0.1, max(0, end - time.monotonic()))
            buffer.extend(self._serial.read(32))
            while buffer:
                start = buffer.find(START)
                if start < 0:
                    buffer[:] = buffer[-1:] if buffer[-1:] == START[:1] else b""
                    break
                del buffer[:start]
                if len(buffer) < 4:
                    break
                if buffer[2:4] != b"\x00\x1c":
                    del buffer[0]
                    continue
                if len(buffer) < FRAME_LEN:
                    break
                try:
                    return parse_frame(bytes(buffer[:FRAME_LEN]))
                except IOError:
                    del buffer[0]
        raise IOError("PMS7003: no valid fresh frame before deadline")

    def close(self) -> None:
        self._serial.close()
