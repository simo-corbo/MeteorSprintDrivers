"""Image -> printer raster bytes.

Resizes an arbitrary image to the printer's confirmed width, dithers it
to 1-bit, and packs it into the MSB-first, standard-polarity byte format
protocol.build_raster_command() expects (see docs/protocol.md for how
that format was confirmed).

No USB/protocol-command knowledge here -- only pixels in, packed bytes
out.
"""
from __future__ import annotations

from PIL import Image

from . import config
from .dithering import dither_to_1bit


def resize_to_printer_width(image: Image.Image,
                             width_dots: int = config.RASTER_WIDTH_DOTS) -> Image.Image:
    """Resize an image to the printer's raster width, preserving aspect
    ratio.
    """
    if image.width == width_dots:
        return image
    scale = width_dots / image.width
    height_dots = max(1, round(image.height * scale))
    return image.resize((width_dots, height_dots), Image.LANCZOS)


def pack_1bit_image(image: Image.Image) -> tuple[bytes, int, int]:
    """Pack a 1-bit PIL Image into (data, width_bytes, height_dots) for
    protocol.build_raster_command().

    PIL's "1" mode stores 255 for white pixels and 0 for black. Printer
    polarity is confirmed standard (see docs/protocol.md): bit 1 = print
    black, bit 0 = blank -- so a PIL-white pixel (255) must become bit 0,
    and a PIL-black pixel (0) must become bit 1 (inverted from PIL's own
    convention).
    """
    if image.mode != "1":
        raise ValueError("image must already be in 1-bit mode (use dither_to_1bit)")

    width, height = image.size
    width_bytes = (width + 7) // 8
    pixels = image.load()

    out = bytearray(width_bytes * height)
    for y in range(height):
        row_offset = y * width_bytes
        for x in range(width):
            is_black = pixels[x, y] == 0
            if is_black:
                out[row_offset + (x // 8)] |= 0x80 >> (x % 8)
    return bytes(out), width_bytes, height


def render_image_to_raster(image: Image.Image,
                            width_dots: int = config.RASTER_WIDTH_DOTS
                            ) -> tuple[bytes, int, int]:
    """Full pipeline: resize -> dither -> pack, ready for
    protocol.build_raster_command(data, width_bytes, height_dots).
    """
    resized = resize_to_printer_width(image, width_dots)
    dithered = dither_to_1bit(resized)
    return pack_1bit_image(dithered)
