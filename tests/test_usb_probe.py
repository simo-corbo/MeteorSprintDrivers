"""Unit tests for the pure-logic parts of diagnostics/usb_probe.py.

These do not touch real hardware. Hardware-dependent verification is done
by actually running diagnostics/usb_probe.py against the connected
printer, not by automated tests (see docs/usb-analysis.md for the last
captured real-device report).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnostics"))

from usb_probe import class_name, _parse_iads  # noqa: E402


def test_class_name_known():
    assert class_name(0x07) == "Printer"
    assert class_name(0x03) == "HID (Human Interface Device)"


def test_class_name_unknown():
    assert class_name(0x77) == "Unknown (0x77)"


def test_parse_iads_empty():
    assert _parse_iads(b"") == []


def test_parse_iads_no_iad_present():
    # A single 3-byte bogus descriptor with a non-IAD type.
    data = bytes([3, 0x21, 0x00])
    assert _parse_iads(data) == []


def test_parse_iads_single_iad():
    # bLength=8, bDescriptorType=0x0B (IAD), first_iface=0, count=2,
    # class=0xFF, subclass=0x01, protocol=0x00, iFunction=0
    iad = bytes([8, 0x0B, 0x00, 0x02, 0xFF, 0x01, 0x00, 0x00])
    result = _parse_iads(iad)
    assert len(result) == 1
    assert result[0] == {
        "first_interface": 0,
        "interface_count": 2,
        "function_class": 0xFF,
        "function_subclass": 0x01,
        "function_protocol": 0x00,
    }


def test_parse_iads_stops_on_zero_length():
    data = bytes([0, 0x0B])
    assert _parse_iads(data) == []
