"""USB transport for the Meteor Sprint printer.

This module owns the USB connection only: opening the device, and raw
bulk read/write. It has no knowledge of what the printer does with the
bytes -- that belongs in protocol.py. Keeping this separation means the
still-evolving understanding of the printer's actual protocol never leaks
into the USB plumbing.
"""
from __future__ import annotations

import os

from . import config

# Homebrew installs libusb outside the default dynamic linker search path
# on macOS, and pyusb's libusb1 backend needs to be told exactly where to
# find it. Relying on the caller to export DYLD_LIBRARY_PATH works for an
# interactive shell but not for a process launched by launchd/cupsd (e.g.
# a CUPS filter or backend), which gets a minimal environment. Searching
# these known locations here makes the transport work the same way
# regardless of who launches the process.
_LIBUSB_SEARCH_PATHS = [
    "/opt/homebrew/lib/libusb-1.0.dylib",  # Apple Silicon Homebrew
    "/usr/local/lib/libusb-1.0.dylib",     # Intel Homebrew
]


def _find_libusb_library(name: str) -> str | None:
    for path in _LIBUSB_SEARCH_PATHS:
        if os.path.exists(path):
            return path
    return None


def _get_libusb_backend():
    import usb.backend.libusb1

    return usb.backend.libusb1.get_backend(find_library=_find_libusb_library)


class DeviceNotFoundError(RuntimeError):
    pass


class MeteorSprintTransport:
    """Raw USB bulk transport to the Meteor Sprint printer.

    No protocol knowledge lives here -- just open/write/read.
    """

    def __init__(self, vendor_id: int = config.VENDOR_ID,
                 product_id: int = config.PRODUCT_ID):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self._dev = None

    def open(self) -> None:
        import usb.core

        dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id,
                             backend=_get_libusb_backend())
        if dev is None:
            raise DeviceNotFoundError(
                f"No USB device found with VID=0x{self.vendor_id:04x} "
                f"PID=0x{self.product_id:04x}. Is the printer connected?"
            )
        try:
            cfg = dev.get_active_configuration()
        except usb.core.USBError:
            cfg = None
        if cfg is None:
            dev.set_configuration()
        self._dev = dev

    def close(self) -> None:
        self._dev = None

    def __enter__(self) -> "MeteorSprintTransport":
        self.open()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def write(self, data: bytes, timeout_ms: int | None = None) -> int:
        """Write data to the printer's bulk OUT endpoint.

        The printer is a real thermal mechanism, not just a USB buffer --
        it takes real physical time (motor movement, print-head heating)
        to consume a large job, and this device's endpoints use a tiny
        32-byte max packet size (confirmed in docs/usb-analysis.md),
        making transfers slow. A short, fixed timeout silently truncates
        large jobs without raising an error (this caused real data loss
        on a real multi-page print job during development: some pages
        were silently dropped). The default timeout here scales with the
        data size, with a generous floor, and the actual bytes-written
        count is always checked against the requested length.
        """
        if self._dev is None:
            raise RuntimeError("Transport is not open. Call open() first.")
        if timeout_ms is None:
            # ~1 second per KB, minimum 30s, deliberately generous: a
            # timeout that's too long just makes a real failure take
            # longer to report; one that's too short silently drops data.
            timeout_ms = max(30_000, len(data))
        written = self._dev.write(config.BULK_OUT_ENDPOINT, data, timeout=timeout_ms)
        if written != len(data):
            raise RuntimeError(
                f"Incomplete USB write: sent {written} of {len(data)} bytes "
                f"(timeout={timeout_ms}ms). The printer likely didn't "
                f"finish processing in time."
            )
        return written

    def try_read(self, length: int = 64, timeout_ms: int = 500) -> bytes | None:
        """Best-effort read from the bulk IN endpoint. Returns None on
        timeout, since many operations produce no response and that is
        not an error condition for this device.
        """
        if self._dev is None:
            raise RuntimeError("Transport is not open. Call open() first.")
        try:
            data = self._dev.read(config.BULK_IN_ENDPOINT, length, timeout=timeout_ms)
            return bytes(data)
        except Exception:
            return None
