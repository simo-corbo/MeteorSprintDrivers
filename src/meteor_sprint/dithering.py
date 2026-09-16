"""Grayscale -> 1-bit dithering.

No printer/USB knowledge here -- pure image processing. Takes a PIL
Image and returns a 1-bit-per-pixel PIL Image ("1" mode), using
Floyd-Steinberg error diffusion, which Pillow implements natively via
Image.convert("1").
"""
from __future__ import annotations

from PIL import Image


def dither_to_1bit(image: Image.Image) -> Image.Image:
    """Convert an image to 1-bit using Floyd-Steinberg dithering.

    Pillow's own "1" mode conversion already does Floyd-Steinberg
    diffusion dithering (its default, undocumented-but-stable behavior
    for convert("1")); this wrapper exists so callers don't need to know
    that detail and so the algorithm is swappable in one place later.
    """
    if image.mode != "L":
        image = image.convert("L")
    return image.convert("1")
