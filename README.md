# Meteor Sprint — macOS Printer Support

Open-source macOS printing support for the **Meteor Sprint** thermal
receipt printer. It appears as a normal printer in **System Settings ->
Printers & Scanners** and works from any macOS application (Word, Pages,
Preview, PDF, browsers, etc.) via the standard `Cmd+P` print dialog.

**Status: working.** Text, images, and full documents (with fonts,
formatting, and layout) all print correctly through the real macOS CUPS
pipeline. The install is currently a manual procedure (see
`docs/architecture.md`); a one-command installer is the remaining piece
of work.

## Hardware

```
Printer label:  Meteor Sprint
USB Vendor ID:  0x4348 (WinChipHead / WCH bridge chip)
USB Product ID: 0x5584
USB class:      Printer Class (0x07), USB 1.1
```

The printer's own USB identification string reports `CMD:GDI`, which
would normally mean no standard command language. Direct testing against
the hardware found this to be misleading -- see
[`docs/protocol.md`](docs/protocol.md) for the confirmed protocol (a real
subset of ESC/POS, including raster graphics) and
[`docs/usb-analysis.md`](docs/usb-analysis.md) for the full USB
descriptor analysis.

## How it works

```
Word / Pages / Preview / PDF / Browser
              |  (Cmd+P)
        macOS print system -> CUPS
              |
   CUPS filter: renders the PDF to a bitmap and encodes it as the
   printer's raster protocol (src/meteor_sprint)
              |
   macOS's built-in USB CUPS backend
              |
        Meteor Sprint
```

See [`docs/architecture.md`](docs/architecture.md) for the full design,
module boundaries, and install/uninstall instructions.

## Repository layout

```
src/meteor_sprint/   Python package: USB transport, wire protocol,
                     printer API, image rendering/dithering
cups/                CUPS PPD + filter for macOS printer integration
diagnostics/         Read-only USB inspection tool
tests/               Unit tests (no hardware required)
docs/                Architecture, USB analysis, protocol reference
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,cups]"

pytest tests/                        # unit tests, no hardware needed
python3 diagnostics/usb_probe.py     # read-only USB descriptor probe
```

Installing the printer on macOS requires building the CUPS filter with
PyInstaller first and running a few `sudo` commands — see
[`docs/architecture.md`](docs/architecture.md) for the full procedure
and why a plain script won't work as a CUPS filter on macOS.

## Safety principles this project follows

1. Never invent protocol information — only act on confirmed evidence.
2. Never assume ESC/POS without evidence.
3. USB transport, protocol, rendering, and CUPS integration are kept in
   separate, independently testable layers.

## Contributing

Issues and PRs welcome. Please keep protocol claims backed by evidence
(a capture, a test result, a cited source).

## License

MIT — see [`LICENSE`](LICENSE).
