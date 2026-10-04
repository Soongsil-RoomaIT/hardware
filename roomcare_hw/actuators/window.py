"""Serialized motor worker with limit feedback, reversal pause and latched faults."""

from __future__ import annotations

import math
import threading
import time
from contextlib import ExitStack

from gpiozero import Button, Motor

from .. import pins
from ..types import WINDOW, HardwareFault


class WindowActuator:
    name = WINDOW

    def __init__(
        self,
        speed=0.8,
        timeout=15.0,
        *,
        reverse_pause=0.1,
        motor=None,
        open_switch=None,
        closed_switch=None,
        obstruction=None,
    ):
        if not math.isfinite(speed) or not 0 < speed <= 1:
            raise ValueError("speed must be in (0, 1]")
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(reverse_pause)
            or reverse_pause < 0
        ):
            raise ValueError("invalid timeout/reverse_pause")
        self._resources = ExitStack()
        try:
            self._motor = (
                motor
                if motor is not None
                else Motor(
                    forward=pins.WINDOW_MOTOR_IN1,
                    backward=pins.WINDOW_MOTOR_IN2,
                    enable=pins.WINDOW_MOTOR_ENA,
                )
            )
            self._resources.callback(self._motor.close)
            self._open_sw = (
                open_switch
                if open_switch is not None
                else Button(pins.WINDOW_LIMIT_OPEN, pull_up=True, bounce_time=0.01)
            )
            self._resources.callback(self._open_sw.close)
            self._closed_sw = (
                closed_switch
                if closed_switch is not None
                else Button(pins.WINDOW_LIMIT_CLOSED, pull_up=True, bounce_time=0.01)
            )
            self._resources.callback(self._closed_sw.close)
            self._motor.stop()
        except BaseException:
            self._resources.close()
            raise
        self._speed, self._timeout, self._pause = speed, timeout, reverse_pause
        self._obstruction = obstruction  # callable returning True while obstructed
        self._lock = threading.RLock()
        self._quit = threading.Event()
        self._target = None
        self._direction = None
        self._last_direction = None
        self._stopped_at = time.monotonic()
        self._started = 0.0
        self.fault = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="roomcare-window")
        self._thread.start()

    @property
    def position(self):
        with self._lock:
            a, b = self._open_sw.is_pressed, self._closed_sw.is_pressed
            if self.fault or (a and b):
                return "fault"
            if self._direction is not None:
                return "opening" if self._direction else "closing"
            return "open" if a else "closed" if b else "unknown"

    @property
    def is_on(self):
        return self.position == "open"

    @property
    def is_moving(self):
        with self._lock:
            return self._target is not None  # includes queued/reversal phase

    def set(self, on: bool):
        if type(on) is not bool:
            raise ValueError("on must be bool")
        with self._lock:
            if self._closed:
                raise HardwareFault("window closed")
            if self.fault:
                raise HardwareFault(self.fault)
            if self._open_sw.is_pressed and self._closed_sw.is_pressed:
                self._fail("conflicting limit switches")
                raise HardwareFault(self.fault)
            self._target = on

    def stop(self):
        with self._lock:
            self._target = None
            self._halt()

    def reset_fault(self):
        with self._lock:
            if self._closed:
                raise HardwareFault("window closed")
            if self._open_sw.is_pressed and self._closed_sw.is_pressed:
                raise HardwareFault("check limit wiring before reset")
            if self._obstruction and self._obstruction():
                raise HardwareFault("remove obstruction before reset")
            self.stop()
            self.fault = None  # explicit inspection/reset; never auto-restart on timeout

    def _halt(self):
        self._motor.stop()
        if self._direction is not None:
            self._last_direction = self._direction
            self._stopped_at = time.monotonic()
        self._direction = None

    def _fail(self, reason):
        self.fault = reason
        self._target = None
        self._halt()

    def _run(self):
        while not self._quit.wait(0.01):
            with self._lock:
                try:
                    a, b = self._open_sw.is_pressed, self._closed_sw.is_pressed
                    if a and b:
                        self._fail("conflicting limit switches")
                    elif self._target is not None and not self.fault:
                        if self._obstruction and self._obstruction():
                            self._fail("obstruction detected")
                        elif a if self._target else b:
                            self._target = None
                            self._halt()
                        elif self._direction is not None and self._direction != self._target:
                            self._halt()
                        elif self._direction is None:
                            reversing = (
                                self._last_direction is not None
                                and self._last_direction != self._target
                            )
                            if not reversing or time.monotonic() - self._stopped_at >= self._pause:
                                self._direction = self._target
                                self._started = time.monotonic()
                                if self._direction:
                                    self._motor.forward(self._speed)
                                else:
                                    self._motor.backward(self._speed)
                        elif time.monotonic() - self._started >= self._timeout:
                            self._fail("motor timeout: limit not reached")
                except Exception as exc:
                    self.fault = f"motor/input error: {exc}"
                    self._target = None
                    try:
                        self._halt()
                    except Exception as stop_exc:
                        self.fault += f"; stop failed: {stop_exc}"
                        self._direction = None

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._quit.set()
            self.stop()
        self._thread.join()
        self._resources.close()
