# USB Analysis — Meteor Sprint

Confirmed facts about the printer's USB identity and descriptors, from
`diagnostics/usb_probe.py` (read-only) plus physical inspection.

## Identity

```
Printer label:  Meteor Sprint
Serial (label): M878129030
USB Vendor ID:  0x4348 (WinChipHead / WCH -- a USB bridge chip vendor;
                this is not the printer's brand, just the internal
                USB-to-printer-engine bridge silicon)
USB Product ID: 0x5584
```

Physical disconnect test confirmed this exact VID:PID is the printer
(unplugging the USB-B cable makes the device disappear from the USB tree).

## Descriptors

```
bcdUSB               0x0110  (USB 1.1)
bDeviceClass          0x00   (class defined at interface level)
bMaxPacketSize0       8
iManufacturer/iProduct/iSerialNumber: all 0 (no USB string descriptors)
bNumConfigurations    1

Configuration 1:
  Interface 0, class 0x07 (Printer), subclass 0x01, protocol 0x01
    Endpoint 0x82: IN,  Bulk, wMaxPacketSize=32
    Endpoint 0x02: OUT, Bulk, wMaxPacketSize=32
```

Standard USB Printer Class device. No string descriptors are exposed, so
the serial number printed on the case is not readable over USB.

## IEEE-1284 Device ID (standard class request, `GET_DEVICE_ID`)

```
MFG:METEOR   ;CMD:GDI;MDL:SPRINT-PRINTER;CLS:PRINTER;MODE:GDI;
```

This originally suggested a proprietary "GDI-mode" printer with no
standard command language. Direct testing against the hardware (see
`docs/protocol.md`) found this to be misleading -- it describes how the
Windows driver talks to the printer, not a hard limit of the firmware,
which actually understands a real, useful subset of ESC/POS.

## Physical characteristics

- **No DIP switches or config buttons** -- only a power switch and a
  paper feed button (feed button only performs a manual feed, no
  self-test/config page).
- **Has a cutter blade**, and it works via the standard ESC/POS cut
  command (see `docs/protocol.md`).
- The port on the back initially thought to be Ethernet is smaller than
  RJ45 -- almost certainly an RJ11/RJ12 cash-drawer kick-out port, not a
  network interface. There is no network path to this printer.
- **Confirmed printable width: 576 dots (72 bytes)** at what behaves as
  203 DPI -- consistent with an 80mm-class paper roll (~72mm printable),
  not 58mm as the default text font's 48-characters-per-line might
  suggest (text-mode column count and raster-mode dot width turned out
  to be independent limits on this firmware).
- No Windows driver or manual for this exact model was found publicly
  available; the protocol was determined entirely through direct,
  incremental hardware testing (see `docs/protocol.md`).
