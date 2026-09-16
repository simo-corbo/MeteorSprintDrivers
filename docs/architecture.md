# Architecture — Meteor Sprint macOS Driver

## End-to-end flow

```
Word / Pages / Preview / PDF / Browser
              |
            (Cmd+P)
              |
        macOS print system -> CUPS
              |
   CUPS filter: a standalone, PyInstaller-built executable of
   cups/filters/rastertometeorsprint (PDF -> PyMuPDF rasterize ->
   meteor_sprint.renderer/dithering -> GS v 0 raster command bytes)
              |
   macOS's own built-in "usb" CUPS backend (no custom backend needed)
              |
             USB
              |
        Meteor Sprint
```

## Module boundaries (`src/meteor_sprint/`)

```
usb.py         - USB transport only: open/close, bulk read/write. No
                 protocol knowledge.
protocol.py    - Wire protocol only: given raster bytes or text, builds
                 the exact byte stream the device expects (see
                 docs/protocol.md). No USB code, no image processing.
printer.py     - Combines usb.py + protocol.py into the high-level
                 operations callers want: print_text(), print_image(),
                 print_raster(), cut().
renderer.py    - Image -> printer raster bytes: resize to the confirmed
                 576-dot width, dither, pack into MSB-first bytes.
dithering.py   - Grayscale -> 1-bit (Floyd-Steinberg).
config.py      - Confirmed hardware constants (VID/PID, raster width,
                 text encoding). Data only.
```

Each layer only talks to the layer directly below it, so the (once
unconfirmed, now confirmed) wire protocol stayed isolated in
`protocol.py` throughout development.

## CUPS integration (`cups/`)

```
cups/filters/rastertometeorsprint  - PDF -> Meteor Sprint raster bytes.
                                      Must be built with PyInstaller
                                      before installing (see below) --
                                      it cannot run as a plain script.
cups/ppd/meteorsprint.ppd          - Describes paper size (72mm-class,
                                      custom-length receipt paper) and
                                      resolution; *cupsFilter2 points at
                                      the built filter's installed path.
```

No custom CUPS backend exists or is needed: Meteor Sprint is a standard
USB Printer Class device, and macOS's own built-in `usb` backend
already recognizes it (`lpinfo -v` shows
`usb://METEOR/SPRINT-PRINTER?location=...` with zero custom code) and
can transmit the filter's output as-is.

## Why the filter must be a compiled binary, not a script

`cupsd` on modern macOS runs filters in a sandboxed context that only
permits exec'ing interpreters from base-OS-trusted paths. A Python
shebang script pointing at a project venv, Homebrew's Python, or even
Apple's own `/usr/bin/python3` stub (which itself depends on Xcode
Command Line Tools via a path the same sandbox also blocks) all fail
with `execv failed: Permission denied` when `cupsd` tries to run them --
even though the exact same file runs fine invoked directly by hand.

The working fix: build the filter with PyInstaller in `--onedir` mode.
(`--onefile` also fails -- its runtime self-extraction relies on a SysV
semaphore, which the same sandbox blocks too.) `--onedir` pre-extracts
everything at build time, so there's no runtime interpreter resolution
or IPC for the sandbox to block.

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onedir --name rastertometeorsprint-bin \
    --paths src cups/filters/rastertometeorsprint
```

## Installing (current manual procedure; Phase 8 will automate this)

```bash
sudo mkdir -p /Library/Printers/Meteor
sudo cp -R dist/rastertometeorsprint-bin /Library/Printers/Meteor/
sudo chown -R root:wheel /Library/Printers/Meteor/rastertometeorsprint-bin
sudo find /Library/Printers/Meteor/rastertometeorsprint-bin -exec chmod a+rX {} \;
sudo xattr -rc /Library/Printers/Meteor/rastertometeorsprint-bin

sudo lpadmin -p meteorsprint -E \
    -v "usb://METEOR/SPRINT-PRINTER?location=<your-locationID>" \
    -P cups/ppd/meteorsprint.ppd -D "Meteor Sprint"
```

The PPD's `*cupsFilter2` line must reference the *installed* filter path
(e.g. `/Library/Printers/Meteor/rastertometeorsprint-bin/rastertometeorsprint-bin`),
not the repo's copy. Find your device's exact `usb://` URI with
`lpinfo -v`.

## Uninstalling

```bash
sudo lpadmin -x meteorsprint
sudo rm -rf /Library/Printers/Meteor
```
