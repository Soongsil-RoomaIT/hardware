"""Standalone hardware checks only; no MQTT or 600-second policy."""

import argparse
import json
import time
from contextlib import ExitStack
from dataclasses import asdict

from roomcare_hw.actuators import DehumidifierLED, DoorCloserServo, PurifierLED, WindowLED
from roomcare_hw.sensors import DHTReader, MagneticDoorSensor, MQ2GasSensor


def monitor(stack, args):
    dht = DHTReader(model="DHT11")
    stack.callback(dht.close)
    door = MagneticDoorSensor(verified=args.door_verified)
    stack.callback(door.close)
    gas = MQ2GasSensor(active_low=not args.gas_active_high, warmup_seconds=args.warmup)
    stack.callback(gas.close)
    while True:
        result = {"magnet_present": door.magnet_present, "door": door.position}
        try:
            result.update(asdict(dht.read()))
        except OSError as exc:
            result["dht_error"] = str(exc)
        result.update(
            gasDetected=gas.gas_detected, gas_warming_up=gas.warming_up, gas_error=gas.last_error
        )
        print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
        time.sleep(2)


def led_test(stack, args):
    devices = []
    for cls in (WindowLED, PurifierLED, DehumidifierLED):
        dev = cls()
        stack.callback(dev.close)
        devices.append(dev)
    for dev in devices:
        for _ in range(args.cycles):
            dev.set(True)
            assert dev.is_on
            dev.set(True)  # duplicate command does not toggle
            time.sleep(args.interval)
            dev.set(False)
            assert not dev.is_on
            time.sleep(args.interval)
        print(f"{dev.name}: {args.cycles} commanded ON/OFF cycles completed")
    print("Visually check the three LEDs; command state is not an optical measurement.")


def door_test(stack, args):
    door = MagneticDoorSensor(verified=True)
    stack.callback(door.close)
    servo = DoorCloserServo(
        door, rest_angle=args.rest_angle, push_angle=args.push_angle, hold_seconds=args.hold
    )
    stack.callback(servo.close)
    if not door.is_open:
        print("Door already closed; no movement commanded.")
        return
    servo.set(False)
    deadline = time.monotonic() + args.hold + 4
    while servo.is_moving and time.monotonic() < deadline:
        time.sleep(0.02)
    if servo.is_moving or servo.fault or door.is_open:
        raise RuntimeError(f"Closing not confirmed by MC-38; fault={servo.fault!r}")
    print("MC-38 confirms CLOSED; inspect model and safe rest position.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test", choices=("monitor", "led", "door"))
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--warmup", type=float, default=180.0)
    parser.add_argument("--gas-active-high", action="store_true")
    parser.add_argument("--door-verified", action="store_true")
    parser.add_argument("--bench-confirmed", action="store_true")
    parser.add_argument("--rest-angle", type=float, default=-60.0)
    parser.add_argument("--push-angle", type=float, default=60.0)
    parser.add_argument("--hold", type=float, default=1.0)
    args = parser.parse_args()
    if args.cycles < 1 or args.interval <= 0:
        parser.error("cycles and interval must be positive")
    if args.test == "door" and not (args.door_verified and args.bench_confirmed):
        parser.error(
            "verify MC-38 and calibrated, safe model first; then use both confirmation flags"
        )
    try:
        with ExitStack() as stack:
            {"monitor": monitor, "led": led_test, "door": door_test}[args.test](stack, args)
    except KeyboardInterrupt:
        print("Stopped; resources released.")


if __name__ == "__main__":
    main()
