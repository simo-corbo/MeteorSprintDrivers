#!/usr/bin/env bash
# Removes the Meteor Sprint printer queue and installed filter.
#
# Reverses everything installer/install.sh did. Does not touch the
# project's own .venv or repo files -- only the CUPS queue and the
# files installed under /Library/Printers/Meteor.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
    echo "ERROR: this uninstaller is macOS-only." >&2
    exit 1
fi

INSTALL_DIR="/Library/Printers/Meteor"
PRINTER_NAME="meteorsprint"

echo "==> Removing the Meteor Sprint printer queue (you may be asked for your password)..."
if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
    sudo lpadmin -x "$PRINTER_NAME"
else
    echo "    (queue was not registered)"
fi

echo "==> Removing installed filter..."
if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf "$INSTALL_DIR"
else
    echo "    (nothing installed at $INSTALL_DIR)"
fi

echo "==> Done."
