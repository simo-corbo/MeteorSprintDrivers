"""Unit tests for meteor_sprint.protocol -- pure logic, no hardware."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meteor_sprint import protocol  # noqa: E402


def test_encode_text_ascii():
    assert protocol.encode_text("hello") == b"hello"


def test_encode_text_accented_cp437():
    # a-grave should encode to its confirmed CP437 byte (0x85) -- see
    # docs/protocol.md.
    assert protocol.encode_text("à") == b"\x85"


def test_encode_text_unsupported_char_replaced():
    # A character with no CP437 representation should be replaced, not
    # raise.
    result = protocol.encode_text("中")  # a CJK character
    assert result == b"?"


def test_wrap_line_short_line_unchanged():
    assert protocol.wrap_line("short line", width=48) == ["short line"]


def test_wrap_line_splits_on_word_boundary():
    text = "a" * 20 + " " + "b" * 20 + " " + "c" * 20
    lines = protocol.wrap_line(text, width=25)
    assert all(len(line) <= 25 for line in lines)
    assert "".join(lines).replace("", "") != ""


def test_wrap_line_splits_overlong_word():
    text = "x" * 100
    lines = protocol.wrap_line(text, width=48)
    assert len(lines) == 3
    assert lines[0] == "x" * 48
    assert lines[1] == "x" * 48
    assert lines[2] == "x" * 4


def test_build_text_job_ends_with_feed():
    data = protocol.build_text_job("hello")
    assert data.endswith(b"\n\n\n")
    assert b"hello" in data


def test_build_text_job_no_esc_or_gs_bytes():
    # Confirmed (see docs/protocol.md): ESC/GS bytes are silently
    # swallowed with no effect, so this module must never emit them.
    data = protocol.build_text_job("hello world")
    assert 0x1B not in data
    assert 0x1D not in data


def test_build_raster_command_header():
    image = b"\xff" * (2 * 4)
    cmd = protocol.build_raster_command(image, width_bytes=2, height_dots=4)
    assert cmd[:4] == bytes([0x1D, 0x76, 0x30, 0x00])
    assert cmd[4:6] == bytes([2, 0])  # width, little-endian
    assert cmd[6:8] == bytes([4, 0])  # height, little-endian
    assert cmd[8:] == image


def test_build_raster_command_wrong_length_raises():
    import pytest

    with pytest.raises(ValueError):
        protocol.build_raster_command(b"\x00" * 3, width_bytes=2, height_dots=4)


def test_build_raster_command_large_dimensions():
    # width/height are encoded little-endian across 2 bytes each.
    width_bytes, height_dots = 300, 500
    image = b"\x00" * (width_bytes * height_dots)
    cmd = protocol.build_raster_command(image, width_bytes, height_dots)
    assert cmd[4] == 300 & 0xFF
    assert cmd[5] == (300 >> 8) & 0xFF
    assert cmd[6] == 500 & 0xFF
    assert cmd[7] == (500 >> 8) & 0xFF


def test_build_cut_command():
    assert protocol.build_cut_command() == bytes([0x1D, 0x56, 0x00])
