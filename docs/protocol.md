# Protocol — Meteor Sprint

The printer's own IEEE-1284 string reports `CMD:GDI`, suggesting a
proprietary, driver-defined raster protocol with no standard command
language. Direct, incremental testing against the physical hardware
(every command below was verified working, one variable at a time)
found this to be misleading: the firmware actually implements a real,
useful subset of ESC/POS. `CMD:GDI` describes how the Windows driver
talks to it, not a hard limit of the firmware.

## Text mode

Literal bytes print directly using the printer's built-in font -- no
framing or init sequence required.

- **Encoding: CP437** (IBM code page 437). Confirmed correct for
  accented Italian characters (à/è/é/ì/ò/ù); Latin-1 and UTF-8 both
  produce garbage.
- `0x0A` (LF) and `0x0D` (CR) both trigger a line break.
- `0x09` (HT) is a real, working horizontal tab.
- `0x00` (NUL) is a true zero-width no-op.
- **48 characters** fit per line at the default font. This is a
  text-mode-only limit -- it does not correspond to the printer's true
  raster width (see below).
- `ESC` (0x1B) and `FS` (0x1C) are recognized as command-prefix bytes,
  but no tested multi-byte `ESC`/`FS` command (e.g. bold via `ESC E n`)
  produces a visible effect. Not needed in practice, since raster mode
  (below) covers all formatting/graphics.

## Raster graphics: `GS v 0` -- confirmed working

```
GS(0x1D) v(0x76) '0'(0x30) m(0x00) xL xH yL yH <data>
```

- `m` = mode (`0x00`, the only value tested).
- `xL`, `xH` = width **in bytes**, little-endian 16-bit. Dots wide =
  `(xL + xH*256) * 8`.
- `yL`, `yH` = height in dot rows, little-endian 16-bit.
- `<data>` = exactly `(xL + xH*256) * (yL + yH*256)` bytes, MSB-first,
  **standard (non-inverted) ESC/POS polarity**: bit `1` = print a black
  dot, bit `0` = leave white.
- **Confirmed maximum usable width: 576 dots (72 bytes)** -- a
  full-width solid bar at this size fills the page edge-to-edge with no
  gap or corruption. This is not proven to be the *exact* ceiling, only
  a safe, confirmed full-width value.
- **A `\n` must precede this command** if there is any unflushed text
  pending on the current line, or that text is silently discarded.
- Implemented in `src/meteor_sprint/protocol.py::build_raster_command()`.

## Paper cut: `GS V 0` -- confirmed working

```
GS(0x1D) V(0x56) m(0x00)
```

Triggers a real, physical full paper cut. Needs a handful of blank feed
lines beforehand so the cut lands past printed content rather than
through it. Implemented in
`src/meteor_sprint/protocol.py::build_cut_command()`.

## What this makes possible

Since real raster graphics work, full document printing (arbitrary
fonts, images, tables -- anything rasterizable to a monochrome bitmap)
is achievable by rendering pages to bitmaps and encoding them as `GS v 0`
commands. This is exactly what `src/meteor_sprint/renderer.py` +
`cups/filters/rastertometeorsprint` do, and it's been confirmed printing
real photos, real multi-page PDFs, and rich text formatting (bold,
italic, multiple fonts, size ranges from 6-24pt) through the actual
installed macOS printer queue.

## Not determined

- Whether 576 dots is the printer's *exact* maximum width, or a safe
  value under some higher true ceiling.
- Maximum single raster command size/height before any chunking would be
  needed for extremely large images (not hit in practice so far).
- Exact physical paper width in mm and DPI (203 DPI / ~72mm is inferred
  from the confirmed 576-dot width via the industry-standard conversion
  for this dot count, not directly measured).
- Whether the bulk IN endpoint carries any real status information
  during/after a print job.
