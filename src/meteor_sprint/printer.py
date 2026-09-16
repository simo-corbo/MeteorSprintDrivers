"""High-level Meteor Sprint printer interface.

Combines usb.py (transport) and protocol.py (confirmed plain-text wire
format) into the operations a caller actually wants. This is the only
module most callers should need to import.
"""
from __future__ import annotations

from . import protocol
from .renderer import render_image_to_raster
from .usb import MeteorSprintTransport


class MeteorSprintPrinter:
    def __init__(self, transport: MeteorSprintTransport | None = None):
        self._transport = transport or MeteorSprintTransport()
        self._owns_transport = transport is None

    def __enter__(self) -> "MeteorSprintPrinter":
        if self._owns_transport:
            self._transport.open()
        return self

    def __exit__(self, *exc_info) -> None:
        if self._owns_transport:
            self._transport.close()

    def print_text(self, text: str) -> None:
        """Print a block of plain text, word-wrapped to the printer's
        confirmed 48-character line width and transcoded to CP437.

        Does not support bold/alignment via ESC/POS text commands -- see
        docs/protocol.md (those commands are inert on this firmware).
        For images/graphics, use print_raster() instead.
        """
        data = protocol.build_text_job(text)
        self._transport.write(data)

    def print_raster(self, image_data: bytes, width_bytes: int,
                      height_dots: int) -> None:
        """Print a monochrome raster image (see protocol.build_raster_command
        for the exact format: standard ESC/POS polarity, MSB-first bits).

        Ends with `\\n` first so any pending text on the current line is
        flushed before the raster command -- otherwise it would be
        silently discarded (see docs/protocol.md).
        """
        command = protocol.build_raster_command(image_data, width_bytes, height_dots)
        self._transport.write(b"\n" + command)

    def print_image(self, image) -> None:
        """Print an arbitrary PIL Image: resize to the printer's
        confirmed raster width, dither to 1-bit, and print it.

        `image` is a PIL.Image.Image. Kept untyped here to avoid forcing
        a PIL import on every caller of this module for type hints alone.
        """
        data, width_bytes, height_dots = render_image_to_raster(image)
        self.print_raster(data, width_bytes, height_dots)

    def cut(self, feed_lines: int = 6) -> None:
        """Feed a few blank lines, then trigger a full paper cut.

        The feed is needed so the cut lands past printed content rather
        than through it (see docs/protocol.md).
        """
        self._transport.write(b"\n" * feed_lines + protocol.build_cut_command())
