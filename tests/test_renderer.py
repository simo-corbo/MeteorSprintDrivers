"""Unit tests for meteor_sprint.renderer / dithering -- pure logic, no
hardware."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PIL import Image  # noqa: E402

from meteor_sprint import renderer  # noqa: E402
from meteor_sprint.dithering import dither_to_1bit  # noqa: E402


def test_resize_to_printer_width_preserves_aspect_ratio():
    image = Image.new("L", (100, 50))
    resized = renderer.resize_to_printer_width(image, width_dots=200)
    assert resized.width == 200
    assert resized.height == 100  # aspect ratio preserved (2:1)


def test_resize_to_printer_width_noop_if_already_correct():
    image = Image.new("L", (576, 300))
    resized = renderer.resize_to_printer_width(image, width_dots=576)
    assert resized is image


def test_dither_to_1bit_mode():
    image = Image.new("L", (10, 10), color=128)
    dithered = dither_to_1bit(image)
    assert dithered.mode == "1"


def test_pack_1bit_image_all_white():
    # PIL "1" mode: 255 = white. Confirmed printer polarity: white -> bit 0.
    image = Image.new("1", (16, 2), color=255)
    data, width_bytes, height = renderer.pack_1bit_image(image)
    assert width_bytes == 2
    assert height == 2
    assert data == b"\x00" * 4


def test_pack_1bit_image_all_black():
    # Confirmed printer polarity: black -> bit 1.
    image = Image.new("1", (16, 2), color=0)
    data, width_bytes, height = renderer.pack_1bit_image(image)
    assert data == b"\xff" * 4


def test_pack_1bit_image_single_black_pixel_msb_first():
    image = Image.new("1", (8, 1), color=255)
    image.putpixel((0, 0), 0)  # leftmost pixel black
    data, width_bytes, height = renderer.pack_1bit_image(image)
    assert width_bytes == 1
    assert data == bytes([0x80])  # leftmost pixel = MSB


def test_pack_1bit_image_width_not_multiple_of_8():
    image = Image.new("1", (10, 1), color=0)  # all black, 10 px wide
    data, width_bytes, height = renderer.pack_1bit_image(image)
    assert width_bytes == 2  # ceil(10/8)


def test_render_image_to_raster_end_to_end():
    image = Image.new("L", (100, 50), color=0)  # solid black
    data, width_bytes, height = renderer.render_image_to_raster(
        image, width_dots=64
    )
    assert width_bytes == 8  # 64 dots / 8
    assert height == 32  # 50 * (64/100)
    assert len(data) == width_bytes * height
