"""Meteor Sprint wire protocol -- confirmed plain-text and raster modes.

Encodes text and raster images into exactly what direct hardware testing
confirmed the printer accepts: literal CP437-encoded text (0x0A = line
feed), the standard ESC/POS `GS v 0` raster bit-image command (standard,
non-inverted polarity), and the standard `GS V 0` full-cut command. See
docs/protocol.md for the full confirmed protocol reference.

This module has no USB knowledge -- it only turns text/images into bytes.
"""
from __future__ import annotations

from . import config


def encode_text(text: str) -> bytes:
    """Encode a string into the byte stream the printer expects.

    Characters not representable in CP437 are replaced with '?' (via
    errors="replace") rather than raising, since a print job should not
    fail outright over a single unsupported character.
    """
    return text.encode(config.TEXT_ENCODING, errors="replace")


def wrap_line(text: str, width: int = config.LINE_WIDTH_CHARS) -> list[str]:
    """Word-wrap a single logical line to the printer's confirmed column
    width, without splitting words unless a single word exceeds the
    width.
    """
    if width <= 0:
        raise ValueError("width must be positive")

    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while len(word) > width:
            lines.append(word[:width])
            word = word[width:]
        current = word
    if current or not lines:
        lines.append(current)
    return lines


def build_text_job(text: str, width: int = config.LINE_WIDTH_CHARS) -> bytes:
    """Build the full byte stream for printing a block of text.

    Wraps each input line to the confirmed column width, encodes to
    CP437, and terminates with a few feed lines so the receipt is easy to
    tear off -- matching what was manually verified against the hardware.
    """
    output_lines: list[str] = []
    for raw_line in text.splitlines() or [""]:
        output_lines.extend(wrap_line(raw_line, width))

    body = "\n".join(output_lines) + "\n"
    return encode_text(body) + b"\n\n\n"


def build_raster_command(image_data: bytes, width_bytes: int,
                          height_dots: int) -> bytes:
    """Build a `GS v 0` raster bit-image command.

    Confirmed working against the physical hardware: standard, non-
    inverted ESC/POS polarity (bit 1 = print a black dot, bit 0 = blank),
    MSB-first within each byte. `image_data` must be exactly
    `width_bytes * height_dots` bytes -- each byte covers 8 dot columns
    of one row. See docs/protocol.md.

    IMPORTANT: if there is any unflushed text pending on the current
    line, it will be silently discarded when this command executes.
    Callers must ensure the preceding output ends with `\\n` first --
    this function does not do that for you, since it has no visibility
    into what preceded it.
    """
    expected_len = width_bytes * height_dots
    if len(image_data) != expected_len:
        raise ValueError(
            f"image_data must be exactly {expected_len} bytes "
            f"(width_bytes={width_bytes} * height_dots={height_dots}), "
            f"got {len(image_data)}"
        )
    if not (0 <= width_bytes <= 0xFFFF) or not (0 <= height_dots <= 0xFFFF):
        raise ValueError("width_bytes and height_dots must fit in 16 bits")

    header = bytes([
        0x1D, 0x76, 0x30, 0x00,  # GS v 0, mode 0
        width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
        height_dots & 0xFF, (height_dots >> 8) & 0xFF,
    ])
    return header + image_data


def build_cut_command() -> bytes:
    """Build the `GS V 0` full-cut command (confirmed working against
    the physical hardware, see docs/protocol.md). Callers should ensure
    a few blank feed lines precede this so the cut lands past printed
    content rather than through it.
    """
    return bytes([0x1D, 0x56, 0x00])
