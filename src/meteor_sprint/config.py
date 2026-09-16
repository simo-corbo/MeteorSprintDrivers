"""Confirmed hardware/protocol constants for the Meteor Sprint printer.

Every value here is backed by direct testing against the physical
hardware -- see docs/usb-analysis.md and docs/protocol.md. Do not add
speculative values here; if something isn't confirmed, it doesn't
belong in this file.
"""

VENDOR_ID = 0x4348
PRODUCT_ID = 0x5584

BULK_OUT_ENDPOINT = 0x02
BULK_IN_ENDPOINT = 0x82

# Two independent full lines of exactly 48 characters were observed
# before wrapping, at the printer's default text-mode font.
LINE_WIDTH_CHARS = 48

# CP437 produced correct accented characters; Latin-1 and UTF-8 both
# produced garbage.
TEXT_ENCODING = "cp437"

# A 72-byte/576-dot-wide solid raster filled the full paper width with
# no gap or corruption (~72mm printable, consistent with 80mm-class
# paper -- not 58mm as the text-mode character count alone would
# suggest; text and raster width are independent limits on this
# firmware). Not proven to be the exact maximum, only confirmed as a
# safe full-width value. See docs/protocol.md.
RASTER_WIDTH_BYTES = 72
RASTER_WIDTH_DOTS = RASTER_WIDTH_BYTES * 8
