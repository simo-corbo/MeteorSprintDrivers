#!/usr/bin/env bash
# Installs the Meteor Sprint printer on macOS.
#
# This automates exactly the manual procedure recorded in
# docs/architecture.md: build the CUPS filter as a standalone binary
# (required -- cupsd's sandbox refuses to exec a plain Python script,
# see docs/architecture.md for why), install it under
# /Library/Printers/Meteor, and register the printer queue with CUPS.
#
# Safe to re-run: each step either creates fresh state or overwrites the
# previous install in place. Building the filter does not require root;
# only installing it and registering the queue does, so you'll be
# prompted for your password partway through, not at the start.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
    echo "ERROR: this installer is macOS-only." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/Library/Printers/Meteor"
FILTER_NAME="rastertometeorsprint-bin"
PRINTER_NAME="meteorsprint"
VENV_DIR="$REPO_ROOT/.venv"
PPD_PATH="$REPO_ROOT/cups/ppd/meteorsprint.ppd"

if [ ! -f "$PPD_PATH" ]; then
    echo "ERROR: $PPD_PATH not found. Run this script from a full checkout of the repo." >&2
    exit 1
fi

echo "==> Meteor Sprint installer"

echo "==> Setting up a build environment..."
if [ ! -x "$VENV_DIR/bin/python3" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q -e "$REPO_ROOT[cups]"

echo "==> Building the CUPS filter (this can take a minute)..."
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

"$VENV_DIR/bin/pyinstaller" --onedir --name "$FILTER_NAME" \
    --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/build" \
    --specpath "$BUILD_DIR" \
    --paths "$REPO_ROOT/src" \
    "$REPO_ROOT/cups/filters/rastertometeorsprint" \
    > "$BUILD_DIR/pyinstaller.log" 2>&1 \
    || { echo "ERROR: filter build failed, see $BUILD_DIR/pyinstaller.log" >&2; cat "$BUILD_DIR/pyinstaller.log" >&2; exit 1; }

echo "==> Looking for the printer over USB..."
DEVICE_URI="$(lpinfo -v | awk '/usb:.*SPRINT-PRINTER/ {print $2}' | head -n1)"
if [ -z "$DEVICE_URI" ]; then
    echo "ERROR: Meteor Sprint not found on USB. Is it connected and powered on?" >&2
    exit 1
fi
echo "    Found: $DEVICE_URI"

echo "==> Installing (you may be asked for your password)..."
sudo mkdir -p "$INSTALL_DIR"
sudo rm -rf "${INSTALL_DIR:?}/$FILTER_NAME"
sudo cp -R "$BUILD_DIR/dist/$FILTER_NAME" "$INSTALL_DIR/"
sudo chown -R root:wheel "$INSTALL_DIR/$FILTER_NAME"
sudo find "$INSTALL_DIR/$FILTER_NAME" -exec chmod a+rX {} \;
sudo xattr -rc "$INSTALL_DIR/$FILTER_NAME" 2>/dev/null || true

sudo lpadmin -p "$PRINTER_NAME" -E -v "$DEVICE_URI" -P "$PPD_PATH" -D "Meteor Sprint"

echo "==> Restarting the print system so it picks up the change..."
sudo launchctl kickstart -k system/org.cups.cupsd

echo ""
echo "==> Done. \"Meteor Sprint\" should now appear in"
echo "    System Settings -> Printers & Scanners, and in any app's Print dialog."
echo "    To remove it: installer/uninstall.sh"
