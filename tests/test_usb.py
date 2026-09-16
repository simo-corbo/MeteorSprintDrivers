"""Unit tests for meteor_sprint.usb -- pure logic only, using a fake
device stub (no real hardware). Hardware-dependent behavior is validated
by actually running against the physical printer (see docs/protocol.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from meteor_sprint.usb import MeteorSprintTransport  # noqa: E402


class _FakeUSBDevice:
    """Stub matching just enough of pyusb's device interface for
    MeteorSprintTransport.write() to exercise its own logic."""

    def __init__(self, bytes_actually_written: int | None = None):
        self.bytes_actually_written = bytes_actually_written
        self.last_write_args = None

    def write(self, endpoint, data, timeout=None):
        self.last_write_args = (endpoint, data, timeout)
        if self.bytes_actually_written is None:
            return len(data)
        return self.bytes_actually_written


def test_write_raises_on_incomplete_transfer():
    # Regression test: this exact scenario (a large multi-page job
    # silently truncated by too short a timeout) caused real data loss
    # during development -- some pages of a real multi-page print job
    # never printed. A short write must now raise, not succeed quietly.
    transport = MeteorSprintTransport()
    transport._dev = _FakeUSBDevice(bytes_actually_written=10)

    with pytest.raises(RuntimeError, match="Incomplete USB write"):
        transport.write(b"x" * 100)


def test_write_succeeds_on_complete_transfer():
    transport = MeteorSprintTransport()
    transport._dev = _FakeUSBDevice()

    written = transport.write(b"hello")
    assert written == 5


def test_write_scales_timeout_with_data_size():
    transport = MeteorSprintTransport()
    fake = _FakeUSBDevice()
    transport._dev = fake

    transport.write(b"x" * 100_000)
    _, _, timeout = fake.last_write_args
    assert timeout >= 100_000  # at least ~1ms per byte, per the write() docstring


def test_write_has_generous_floor_for_small_data():
    transport = MeteorSprintTransport()
    fake = _FakeUSBDevice()
    transport._dev = fake

    transport.write(b"hi")
    _, _, timeout = fake.last_write_args
    assert timeout >= 30_000


def test_write_raises_if_not_open():
    transport = MeteorSprintTransport()
    with pytest.raises(RuntimeError, match="not open"):
        transport.write(b"hello")
