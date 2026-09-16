#!/usr/bin/env python3
"""
Read-only USB descriptor probe for the "Meteor Sprint" thermal printer.

Target device:
    VID = 0x4348 (17224)
    PID = 0x5584 (21892)

SAFETY: This tool is strictly read-only. It only reads USB descriptors
(device, configuration, interface, endpoint, string) via standard USB
control transfers (GET_DESCRIPTOR). It never writes to an endpoint, never
sends vendor-specific commands, and never resets or reconfigures the
device. Do not add write operations to this file — create a separate,
clearly-labeled tool once the protocol is understood.

Usage:
    python3 diagnostics/usb_probe.py
    python3 diagnostics/usb_probe.py --vid 0x4348 --pid 0x5584
    python3 diagnostics/usb_probe.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_VID = 0x4348
DEFAULT_PID = 0x5584

# USB class code -> human name, for readability in the report only.
# This is a lookup table for display purposes; it does not affect probing.
USB_CLASS_NAMES = {
    0x00: "Defined at interface level",
    0x01: "Audio",
    0x02: "Communications and CDC Control",
    0x03: "HID (Human Interface Device)",
    0x05: "Physical",
    0x06: "Image (PTP/MTP)",
    0x07: "Printer",
    0x08: "Mass Storage",
    0x09: "Hub",
    0x0A: "CDC-Data",
    0x0B: "Smart Card",
    0x0D: "Content Security",
    0x0E: "Video",
    0x0F: "Personal Healthcare",
    0x10: "Audio/Video Devices",
    0x11: "Billboard",
    0x12: "USB Type-C Bridge",
    0xDC: "Diagnostic Device",
    0xE0: "Wireless Controller",
    0xEF: "Miscellaneous",
    0xFE: "Application Specific",
    0xFF: "Vendor Specific",
}

TRANSFER_TYPE_NAMES = {
    0: "Control",
    1: "Isochronous",
    2: "Bulk",
    3: "Interrupt",
}


def class_name(code: int) -> str:
    return USB_CLASS_NAMES.get(code, f"Unknown (0x{code:02x})")


@dataclass
class EndpointInfo:
    address: int
    direction: str
    transfer_type: str
    max_packet_size: int
    interval: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterfaceInfo:
    interface_number: int
    alternate_setting: int
    interface_class: int
    interface_class_name: str
    interface_subclass: int
    interface_protocol: int
    num_endpoints: int
    endpoints: list[EndpointInfo] = field(default_factory=list)
    interface_string: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["endpoints"] = [e.to_dict() for e in self.endpoints]
        return d


@dataclass
class ConfigurationInfo:
    configuration_value: int
    num_interfaces: int
    attributes: int
    max_power_ma: int
    self_powered: bool
    remote_wakeup: bool
    configuration_string: str | None
    interfaces: list[InterfaceInfo] = field(default_factory=list)
    interface_associations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["interfaces"] = [i.to_dict() for i in self.interfaces]
        return d


@dataclass
class DeviceInfo:
    vendor_id: int
    product_id: int
    bus: int | None
    address: int | None
    bcd_usb: int
    device_class: int
    device_class_name: str
    device_subclass: int
    device_protocol: int
    max_packet_size_0: int
    bcd_device: int
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    num_configurations: int
    configurations: list[ConfigurationInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ieee1284_device_id: str | None = None
    port_status: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["configurations"] = [c.to_dict() for c in self.configurations]
        return d


def safe_get_string(dev, index: int, langid=None) -> str | None:
    """Best-effort string descriptor read. Returns None on any failure.

    A failure here is expected and informative: many low-cost USB devices
    report iManufacturer/iProduct/iSerialNumber = 0 (no string descriptors
    at all), which is itself a diagnostic fact worth recording.
    """
    if index == 0:
        return None
    import usb.util

    try:
        return usb.util.get_string(dev, index, langid=langid)
    except Exception:
        return None


def probe_device(vid: int, pid: int) -> DeviceInfo:
    import usb.core
    import usb.util

    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if dev is None:
        raise RuntimeError(
            f"No USB device found with VID=0x{vid:04x} PID=0x{pid:04x}. "
            "Is the printer connected? (This tool never sends data, so a "
            "'not found' result is purely a detection issue.)"
        )

    warnings: list[str] = []

    manufacturer = safe_get_string(dev, dev.iManufacturer)
    product = safe_get_string(dev, dev.iProduct)
    serial = safe_get_string(dev, dev.iSerialNumber)

    info = DeviceInfo(
        vendor_id=vid,
        product_id=pid,
        bus=getattr(dev, "bus", None),
        address=getattr(dev, "address", None),
        bcd_usb=dev.bcdUSB,
        device_class=dev.bDeviceClass,
        device_class_name=class_name(dev.bDeviceClass),
        device_subclass=dev.bDeviceSubClass,
        device_protocol=dev.bDeviceProtocol,
        max_packet_size_0=dev.bMaxPacketSize0,
        bcd_device=dev.bcdDevice,
        manufacturer=manufacturer,
        product=product,
        serial_number=serial,
        num_configurations=dev.bNumConfigurations,
        warnings=warnings,
    )

    try:
        active_cfg_value = dev.get_active_configuration().bConfigurationValue
    except Exception as exc:  # noqa: BLE001 - purely diagnostic
        active_cfg_value = None
        warnings.append(f"Could not read active configuration: {exc!r}")

    for cfg in dev:
        cfg_string = safe_get_string(dev, cfg.iConfiguration)

        # Interface Association Descriptors (IADs), if present, group
        # multiple interfaces (e.g. composite devices). pyusb exposes
        # these via cfg.extra_descriptors on some backends; we surface
        # them opportunistically without failing if unavailable.
        iads: list[dict[str, Any]] = []
        extra = getattr(cfg, "extra_descriptors", None)
        if extra:
            iads.extend(_parse_iads(extra))

        cfg_info = ConfigurationInfo(
            configuration_value=cfg.bConfigurationValue,
            num_interfaces=cfg.bNumInterfaces,
            attributes=cfg.bmAttributes,
            max_power_ma=cfg.bMaxPower * 2,  # USB spec: units of 2 mA
            self_powered=bool(cfg.bmAttributes & (1 << 6)),
            remote_wakeup=bool(cfg.bmAttributes & (1 << 5)),
            configuration_string=cfg_string,
            interface_associations=iads,
        )

        for intf in cfg:
            intf_string = safe_get_string(dev, intf.iInterface)
            intf_info = InterfaceInfo(
                interface_number=intf.bInterfaceNumber,
                alternate_setting=intf.bAlternateSetting,
                interface_class=intf.bInterfaceClass,
                interface_class_name=class_name(intf.bInterfaceClass),
                interface_subclass=intf.bInterfaceSubClass,
                interface_protocol=intf.bInterfaceProtocol,
                num_endpoints=intf.bNumEndpoints,
                interface_string=intf_string,
            )

            for ep in intf:
                direction = "IN" if usb.util.endpoint_direction(
                    ep.bEndpointAddress
                ) == usb.util.ENDPOINT_IN else "OUT"
                transfer_type = usb.util.endpoint_type(ep.bmAttributes)
                ep_info = EndpointInfo(
                    address=ep.bEndpointAddress,
                    direction=direction,
                    transfer_type=TRANSFER_TYPE_NAMES.get(
                        transfer_type, f"Unknown ({transfer_type})"
                    ),
                    max_packet_size=ep.wMaxPacketSize,
                    interval=ep.bInterval,
                )
                intf_info.endpoints.append(ep_info)

            cfg_info.interfaces.append(intf_info)

        info.configurations.append(cfg_info)

    if active_cfg_value is not None:
        info.warnings.append(f"Active configuration value: {active_cfg_value}")

    # Standard, read-only USB Printer Class control requests. Only
    # attempted if a Printer-class (0x07) interface was actually found,
    # since these are class-specific requests defined by that class.
    printer_interfaces = [
        intf
        for cfg in info.configurations
        for intf in cfg.interfaces
        if intf.interface_class == 0x07
    ]
    if printer_interfaces:
        target = printer_interfaces[0]
        try:
            info.ieee1284_device_id = read_ieee1284_device_id(
                dev, target.interface_number, target.alternate_setting
            )
        except Exception as exc:  # noqa: BLE001
            info.warnings.append(f"GET_DEVICE_ID raised: {exc!r}")
        try:
            info.port_status = read_port_status(dev, target.interface_number)
        except Exception as exc:  # noqa: BLE001
            info.warnings.append(f"GET_PORT_STATUS raised: {exc!r}")

    return info


def _parse_iads(extra_descriptors: bytes) -> list[dict[str, Any]]:
    """Parse raw extra descriptor bytes looking for Interface Association
    Descriptors (bDescriptorType == 0x0B, length 8).

    This is a best-effort, defensive parser over already-read descriptor
    bytes; it performs no USB I/O itself.
    """
    iads = []
    i = 0
    data = bytes(extra_descriptors)
    while i + 1 < len(data):
        length = data[i]
        if length == 0:
            break
        descriptor_type = data[i + 1] if i + 1 < len(data) else None
        if descriptor_type == 0x0B and length == 8 and i + 8 <= len(data):
            iads.append(
                {
                    "first_interface": data[i + 2],
                    "interface_count": data[i + 3],
                    "function_class": data[i + 4],
                    "function_subclass": data[i + 5],
                    "function_protocol": data[i + 6],
                }
            )
        i += length
    return iads


def read_ieee1284_device_id(dev, interface_number: int, alt_setting: int,
                             configuration_index: int = 0) -> str | None:
    """Issue the standard USB Printer Class GET_DEVICE_ID control request.

    This is a READ-ONLY, standard, class-defined control transfer (not a
    vendor/proprietary command). It is the exact mechanism CUPS/macOS use
    to auto-identify printers and typically returns an IEEE 1284 Device ID
    string such as "MFG:...;MDL:...;CMD:...;CLS:PRINTER;". It performs no
    writes to the bulk OUT endpoint and sends nothing printer-specific.

    bmRequestType = 0xA1 (Device-to-host | Class | Interface)
    bRequest      = 0 (GET_DEVICE_ID)
    wValue        = configuration index (0-based)
    wIndex        = (alt_setting << 8) | interface_number
    """
    w_value = configuration_index
    w_index = (alt_setting << 8) | interface_number
    try:
        raw = dev.ctrl_transfer(0xA1, 0, w_value, w_index, 256, timeout=2000)
    except Exception as exc:  # noqa: BLE001 - diagnostic, report and continue
        return f"<GET_DEVICE_ID failed: {exc!r}>"

    data = bytes(raw)
    if len(data) < 2:
        return f"<GET_DEVICE_ID returned too few bytes: {data!r}>"

    # First two bytes are a big-endian length (per IEEE 1284), including
    # the length field itself.
    declared_len = (data[0] << 8) | data[1]
    payload = data[2:declared_len] if declared_len > 2 else data[2:]
    try:
        return payload.decode("ascii", errors="replace")
    except Exception:
        return repr(payload)


def read_port_status(dev, interface_number: int) -> dict[str, Any] | None:
    """Issue the standard USB Printer Class GET_PORT_STATUS control request.

    READ-ONLY standard class request (bRequest=1). Returns a single status
    byte with paper-out / select / not-error bits, per the USB Printer
    Class spec.
    """
    try:
        raw = dev.ctrl_transfer(0xA1, 1, 0, interface_number, 1, timeout=2000)
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}

    if not raw:
        return None
    status = raw[0]
    return {
        "raw_byte": status,
        "paper_empty": bool(status & 0x20),
        "selected": bool(status & 0x10),
        "not_error": bool(status & 0x08),
    }


def check_permissions_hint(exc: Exception) -> str:
    text = str(exc).lower()
    if "access" in text or "permission" in text or "errno 13" in text:
        return (
            "This looks like a macOS USB access-permission problem, not a "
            "code bug. On modern macOS, the in-kernel/DriverKit USB stack "
            "may hold the device or require the calling process to have "
            "appropriate entitlements. Options to investigate next:\n"
            "  1. Run this script with the Terminal/iTerm granted Full "
            "Disk Access or run via 'sudo' as a quick diagnostic (not a "
            "long-term solution).\n"
            "  2. Check whether a competing driver/process has claimed "
            "the interface (e.g. AppleUSBXHCI's built-in class drivers).\n"
            "  3. If libusb cannot open the device at all, consider a "
            "small native IOKit-based helper (Swift or Objective-C) as "
            "an alternative to libusb for descriptor reads.\n"
        )
    return ""


def print_report(info: DeviceInfo) -> None:
    print("=" * 70)
    print("METEOR SPRINT - USB DIAGNOSTIC REPORT (read-only)")
    print("=" * 70)
    print(f"VID:PID              0x{info.vendor_id:04x}:0x{info.product_id:04x} "
          f"({info.vendor_id}:{info.product_id})")
    print(f"Bus / Address         {info.bus} / {info.address}")
    print(f"bcdUSB                0x{info.bcd_usb:04x}")
    print(f"Device Class          0x{info.device_class:02x} "
          f"({info.device_class_name})")
    print(f"Device SubClass       0x{info.device_subclass:02x}")
    print(f"Device Protocol       0x{info.device_protocol:02x}")
    print(f"bMaxPacketSize0       {info.max_packet_size_0}")
    print(f"bcdDevice             0x{info.bcd_device:04x}")
    print(f"Manufacturer string   {info.manufacturer!r}")
    print(f"Product string        {info.product!r}")
    print(f"Serial number string  {info.serial_number!r}")
    print(f"bNumConfigurations    {info.num_configurations}")

    for cfg in info.configurations:
        print("-" * 70)
        print(f"Configuration {cfg.configuration_value}: "
              f"{cfg.num_interfaces} interface(s), "
              f"max power {cfg.max_power_ma} mA, "
              f"self_powered={cfg.self_powered}, "
              f"remote_wakeup={cfg.remote_wakeup}")
        if cfg.configuration_string:
            print(f"  Configuration string: {cfg.configuration_string!r}")
        if cfg.interface_associations:
            print("  Interface Association Descriptors (IAD) found:")
            for iad in cfg.interface_associations:
                print(f"    {iad}")
        else:
            print("  No Interface Association Descriptors found.")

        for intf in cfg.interfaces:
            print(f"  Interface {intf.interface_number}, "
                  f"AltSetting {intf.alternate_setting}: "
                  f"class=0x{intf.interface_class:02x} "
                  f"({intf.interface_class_name}), "
                  f"subclass=0x{intf.interface_subclass:02x}, "
                  f"protocol=0x{intf.interface_protocol:02x}, "
                  f"{intf.num_endpoints} endpoint(s)")
            if intf.interface_string:
                print(f"    Interface string: {intf.interface_string!r}")
            for ep in intf.endpoints:
                print(f"    Endpoint 0x{ep.address:02x}: "
                      f"{ep.direction}, {ep.transfer_type}, "
                      f"max_packet_size={ep.max_packet_size}, "
                      f"interval={ep.interval}")

    if info.ieee1284_device_id is not None or info.port_status is not None:
        print("-" * 70)
        print("USB Printer Class standard requests (read-only):")
        print(f"  GET_DEVICE_ID (IEEE 1284 string): {info.ieee1284_device_id!r}")
        print(f"  GET_PORT_STATUS: {info.port_status}")

    if info.warnings:
        print("-" * 70)
        print("Notes/warnings:")
        for w in info.warnings:
            print(f"  - {w}")

    print("=" * 70)
    print("This report is READ-ONLY descriptor data. No commands were sent "
          "to the printer.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vid", type=lambda x: int(x, 0), default=DEFAULT_VID,
                         help="USB Vendor ID (default: 0x4348)")
    parser.add_argument("--pid", type=lambda x: int(x, 0), default=DEFAULT_PID,
                         help="USB Product ID (default: 0x5584)")
    parser.add_argument("--json", metavar="PATH", default=None,
                         help="Also write the full report as JSON to PATH")
    args = parser.parse_args(argv)

    try:
        import usb.core  # noqa: F401
    except ImportError:
        print("ERROR: pyusb is not installed. Install it with:\n"
              "    pip install pyusb\n"
              "and ensure libusb is available, e.g.:\n"
              "    brew install libusb", file=sys.stderr)
        return 2

    try:
        info = probe_device(args.vid, args.pid)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level diagnostic tool
        print(f"ERROR: Failed to probe device: {exc!r}", file=sys.stderr)
        hint = check_permissions_hint(exc)
        if hint:
            print(hint, file=sys.stderr)
        return 1

    print_report(info)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(info.to_dict(), f, indent=2)
        print(f"\nFull JSON report written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
