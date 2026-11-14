#!/usr/bin/env python3
"""Idempotently deploy the companion; suitable for a Chezmoi apply hook."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import sys

from native_host import HOST_NAME

SOURCE = Path(__file__).resolve().parent
BROWSERS = {
    "brave-origin": "BraveSoftware/Brave-Origin",
    "brave": "BraveSoftware/Brave-Browser",
    "brave-origin-nightly": "BraveSoftware/Brave-Origin-Nightly",
    "brave-beta": "BraveSoftware/Brave-Browser-Beta",
    "brave-nightly": "BraveSoftware/Brave-Browser-Nightly",
    "chromium": "chromium",
    "chrome": "google-chrome",
}


def extension_id():
    manifest = json.loads((SOURCE / "extension/manifest.json").read_text())
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()
    return "".join(chr(ord("a") + int(char, 16)) for char in digest[:32])


def install(config, data, browsers, uninstall=False):
    destination = data / "grymm-theme-companion"
    for browser in browsers:
        manifest_dir = config / BROWSERS[browser] / "NativeMessagingHosts"
        manifest_path = manifest_dir / f"{HOST_NAME}.json"
        if uninstall:
            manifest_path.unlink(missing_ok=True)
            continue
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": HOST_NAME,
            "description": "Read the active local Omarchy color palette",
            "path": str(destination / "native-host"),
            "type": "stdio",
            "allowed_origins": [f"chrome-extension://{extension_id()}/"],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    if uninstall:
        # Other registered browsers may still use this shared installation.
        print("Selected native registrations removed; extension files kept.")
        return
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "native_host.py", destination / "native_host.py")
    shutil.copytree(
        SOURCE / "extension", destination / "extension", dirs_exist_ok=True
    )
    # Use the exact Python 3.11+ executable running this installer, rather
    # than depending on Brave's desktop-launch PATH or shell initialization.
    launcher = destination / "native-host"
    launcher.write_text(
        "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " "
        + shlex.quote(str(destination / "native_host.py")) + ' "$@"\n'
    )
    launcher.chmod(0o755)
    print(f"Load unpacked extension: {destination / 'extension'}")
    print(f"Extension ID: {extension_id()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--browser", choices=BROWSERS, action="append",
        help="Repeat for multiple browsers (default: brave-origin)",
    )
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--extension-id", action="store_true")
    args = parser.parse_args()
    if args.extension_id:
        print(extension_id())
        return
    if not sys.platform.startswith("linux"):
        parser.error("Native registration currently supports Linux only")
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    install(config, data, args.browser or ["brave-origin"], args.uninstall)


if __name__ == "__main__":
    main()
