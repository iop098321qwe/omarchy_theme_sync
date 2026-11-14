#!/usr/bin/env python3
"""Read Omarchy colors for Brave native messaging; never open a socket."""

import json
import os
from pathlib import Path
import re
import select
import struct
import sys
import time
import tomllib

HOST_NAME = "io.github.iop098321qwe.omarchy_theme"
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")


def blend(background, foreground, amount):
    channels = []
    for offset in (1, 3, 5):
        start = int(background[offset:offset + 2], 16)
        end = int(foreground[offset:offset + 2], 16)
        channels.append(round(start + (end - start) * amount))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def palette_from_colors(colors):
    """Map current and legacy flat Omarchy TOML keys to site tokens."""
    if not isinstance(colors, dict):
        raise ValueError("Expected a color table")
    for key in ("background", "foreground", "accent"):
        if not isinstance(colors.get(key), str) or not COLOR.fullmatch(
            colors[key]
        ):
            raise ValueError(f"Missing or invalid {key}")
    for key, value in colors.items():
        if key != "mode" and (
            not isinstance(value, str) or not COLOR.fullmatch(value)
        ):
            raise ValueError(f"Invalid color: {key}")
    bg, fg, accent = (colors[k] for k in (
        "background", "foreground", "accent"
    ))
    aliases = {
        "rosewater": "red", "flamingo": "red", "pink": "magenta",
        "mauve": "magenta", "red": "red", "maroon": "red",
        "peach": "yellow", "yellow": "yellow", "green": "green",
        "teal": "cyan", "sky": "cyan", "blue": "blue",
        "lavender": "magenta",
    }
    legacy = {
        "red": "color1", "green": "color2", "yellow": "color3",
        "blue": "color4", "magenta": "color5", "cyan": "color6",
    }
    tokens = {
        name: colors.get(source, colors.get(legacy[source], accent))
        for name, source in aliases.items()
    }
    tokens.update({
        "sapphire": accent,
        "text": fg,
        "base": bg,
        "mantle": colors.get("dark_background", blend(bg, fg, 0.025)),
        "crust": colors.get("darker_background", bg),
    })
    for name, amount in {
        "surface0": 0.08, "surface1": 0.12, "surface2": 0.20,
        "overlay0": 0.40, "overlay1": 0.55, "overlay2": 0.65,
        "subtext0": 0.75, "subtext1": 0.85,
    }.items():
        tokens[name] = blend(bg, fg, amount)
    # Use authored supporting shades where the current format provides them.
    for name, source in {
        "surface0": "lighter_background", "surface2": "selection",
        "overlay0": "muted", "subtext1": "light_foreground",
    }.items():
        tokens[name] = colors.get(source, tokens[name])
    rgb = [int(bg[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    luminance = sum(v * w for v, w in zip(rgb, (0.2126, 0.7152, 0.0722)))
    scheme = colors.get("mode", "light" if luminance > 0.5 else "dark")
    if scheme not in ("light", "dark"):
        raise ValueError("Invalid mode")
    return {"type": "palette", "colors": tokens, "scheme": scheme}


def read_palette(config_home=None, state_home=None):
    config = Path(config_home or os.environ.get(
        "XDG_CONFIG_HOME", str(Path.home() / ".config")
    ))
    state = Path(state_home or os.environ.get(
        "XDG_STATE_HOME", str(Path.home() / ".local/state")
    ))
    # Quattro moved runtime theme data to state; older releases use config.
    # Once the current state directory exists, a missing/invalid palette must
    # clear overrides rather than resurrect a stale legacy config palette.
    current = state / "omarchy/current"
    if not current.exists():
        current = config / "omarchy/current"
    try:
        path = current / "theme/colors.toml"
        # Reopen on every tick: Omarchy can replace the current-theme symlink.
        with path.open("rb") as source:
            return palette_from_colors(tomllib.load(source))
    except (OSError, ValueError, TypeError):
        return {"type": "unavailable"}


def write_message(message, stream):
    payload = json.dumps(message).encode("utf-8")
    stream.write(struct.pack("=I", len(payload)))
    stream.write(payload)
    stream.flush()


def serve():
    previous = None
    last_sent = 0
    while True:
        palette = read_palette()
        now = time.monotonic()
        if palette != previous or now - last_sent >= 10:
            write_message(palette, sys.stdout.buffer)
            previous, last_sent = palette, now
        # Browser closes stdin when its native port disconnects. Exit then,
        # including when there are no site tabs left; no daemon is installed.
        readable, _, _ = select.select([sys.stdin.buffer], [], [], 1)
        if readable and not os.read(sys.stdin.fileno(), 4096):
            return


if __name__ == "__main__":
    try:
        if "--print" in sys.argv:
            print(json.dumps(read_palette(), indent=2))
        else:
            serve()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
