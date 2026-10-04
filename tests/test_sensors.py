import struct
import threading
import time
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from conftest import wait_for

from roomcare_hw.sensors import CachedSensorReader, DHTReader, TouchDoorSensor, TouchWindowSensor
from roomcare_hw.sensors.pms7003 import PMS7003, parse_frame
from roomcare_hw.sensors.room import RoomSensorReader
from roomcare_hw.types import HardwareFault, PartialReading, Reading


def frame(pm=37, error=0):
    data = bytearray(b"\x42\x4d\x00\x1c" + bytes(26))
    data[6:8] = struct.pack(">H", 999)  # CF1 must not be used
    data[12:14] = struct.pack(">H", pm)
    data[29] = error
    return bytes(data) + struct.pack(">H", sum(data))


def test_pm_atmospheric_field():
    assert parse_frame(frame()) == 37


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        frame()[:-1],
        b"XX" + frame()[2:],
        frame()[:2] + b"\x00\x20" + frame()[4:],
        frame()[:-2] + b"\x00\x00",
        frame(error=1),
    ],
)
def test_pm_rejects_bad_frames(bad):
    with pytest.raises(IOError):
        parse_frame(bad)


class Stream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.timeout = 0.001
        self.closed = False

    def reset_input_buffer(self):
        pass

    def read(self, n):
        return next(self.chunks, b"")

    def close(self):
        self.closed = True


def test_pm_noise_overlapping_header_partial_and_checksum_recovery():
    good = frame(42)
    stream = Stream(
        [
            b"noise\x42",
            b"\x42\x4d\x00\x03junk",
            frame()[:-1] + b"\x00",
            good[:3],
            good[3:18],
            good[18:],
        ]
    )
    reader = PMS7003("unused", timeout=0.1, serial_port=stream)
    assert reader.read_pm25() == 42
    reader.close()
    assert stream.closed


def test_pm_one_overall_deadline():
    reader = PMS7003("unused", timeout=0.02, serial_port=Stream([]))
    start = time.monotonic()
    with pytest.raises(IOError):
        reader.read_pm25()
    assert time.monotonic() - start < 0.2
    reader.close()


def test_dht_missing_gas_and_timestamp_cache(monkeypatch):
    device = SimpleNamespace(temperature=24, humidity=55, exit=lambda: None)
    reader = DHTReader(device=device)
    first = reader.read()
    assert reader.read() is first
    assert asdict(first)["co2"] is None and first.pm25 is None
    reader._last_attempt -= 3
    device.temperature = float("nan")
    with pytest.raises(IOError):
        reader.read()
    with pytest.raises(IOError):
        reader.read()
    reader.close()
    with pytest.raises(IOError):
        reader.read()


def test_touch_unknown_and_polarity(gpio):
    sensor = TouchWindowSensor()
    try:
        assert sensor.position == "unknown"
        with pytest.raises(HardwareFault):
            _ = sensor.is_open
        sensor.verified = True
        gpio.pin(24).drive_high()
        assert sensor.position == "closed"
        gpio.pin(24).drive_low()
        assert sensor.position == "open"
    finally:
        sensor.close()
    reversed_sensor = TouchDoorSensor(touched_means_closed=False, verified=True)
    try:
        gpio.pin(23).drive_high()
        assert reversed_sensor.is_open
    finally:
        reversed_sensor.close()


class Scd:
    data_ready = False
    CO2 = 650
    stopped = False

    def start_periodic_measurement(self):
        pass

    def stop_periodic_measurement(self):
        self.stopped = True


def make_room(scd):
    return RoomSensorReader(
        sht=SimpleNamespace(temperature=23, relative_humidity=50),
        scd=scd,
        pms=SimpleNamespace(read_pm25=lambda: 12, close=lambda: None),
        co2_max_age=0.02,
    )


def test_room_warmup_stale_co2_and_cleanup():
    scd = Scd()
    reader = make_room(scd)
    with pytest.raises(IOError):
        reader.read()
    scd.data_ready = True
    r = reader.read()
    assert r.co2 == 650 and r.pm25 == 12
    scd.data_ready = False
    reader._co2_at -= 1
    with pytest.raises(IOError):
        reader.read()
    reader.close()
    assert scd.stopped


def test_room_dht_full_configuration():
    scd = Scd()
    scd.data_ready = True
    dht = SimpleNamespace(read=lambda: PartialReading(time.time(), 23, 45), close=lambda: None)
    reader = RoomSensorReader(
        temperature_model="DHT11",
        scd=scd,
        dht=dht,
        pms=SimpleNamespace(read_pm25=lambda: 18, close=lambda: None),
    )
    assert reader.read().humidity == 45
    reader.close()


def test_room_partial_init_cleanup(monkeypatch):
    scd = Scd()

    def fail(*args):
        raise IOError("UART missing")

    monkeypatch.setattr("roomcare_hw.sensors.room.PMS7003", fail)
    with pytest.raises(IOError):
        RoomSensorReader(sht=object(), scd=scd)
    assert scd.stopped


def test_background_reader_does_not_block_and_expires():
    gate = threading.Event()

    class Source:
        calls = 0
        closed = False

        def read(self):
            self.calls += 1
            if self.calls > 1:
                gate.wait(1)
            return Reading(time.time(), 24, 50, 600, 12)

        def close(self):
            self.closed = True

    source = Source()
    reader = CachedSensorReader(source, interval=0.01, max_age=0.02)
    try:
        wait_for(lambda: source.calls >= 2)
        start = time.monotonic()
        reader.read()
        assert time.monotonic() - start < 0.05
        time.sleep(0.03)
        with pytest.raises(IOError, match="stale"):
            reader.read()
    finally:
        gate.set()
        reader.close()
    assert source.closed


def test_background_error_recovery():
    class Source:
        fail = True

        def read(self):
            if self.fail:
                raise IOError("disconnected")
            return Reading(time.time(), 22, 40, 700, 8)

        def close(self):
            pass

    source = Source()
    reader = CachedSensorReader(source, interval=0.01)
    try:
        wait_for(lambda: reader.last_error == "disconnected")
        with pytest.raises(IOError):
            reader.read()
        source.fail = False
        wait_for(lambda: reader.last_error is None)
        assert reader.read().temperature == 22
    finally:
        reader.close()
