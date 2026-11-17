#!/usr/bin/env python3
"""Read Omarchy colors for Brave native messaging; never open a socket."""

import ctypes
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


def theme_roots(config_home=None, state_home=None):
    config = Path(config_home or os.environ.get(
        "XDG_CONFIG_HOME", str(Path.home() / ".config")
    ))
    state = Path(state_home or os.environ.get(
        "XDG_STATE_HOME", str(Path.home() / ".local/state")
    ))
    return state / "omarchy/current", config / "omarchy/current"


def palette_path(config_home=None, state_home=None):
    # Quattro moved runtime theme data to state; older releases use config.
    # Once the current state directory exists, a missing/invalid palette must
    # clear overrides rather than resurrect a stale legacy config palette.
    current, legacy = theme_roots(config_home, state_home)
    if not current.exists():
        current = legacy
    return current / "theme/colors.toml"


def read_palette(config_home=None, state_home=None):
    try:
        path = palette_path(config_home, state_home)
        with path.open("rb") as source:
            return palette_from_colors(tomllib.load(source))
    except (OSError, ValueError, TypeError):
        return {"type": "unavailable"}


class PaletteCache:
    """Avoid reopening and parsing unchanged files during reconciliation."""

    def __init__(self):
        self.signature = None
        self.palette = {"type": "unavailable"}

    def read(self, force=False):
        path = palette_path()
        try:
            info = path.stat()
            signature = (
                path, info.st_dev, info.st_ino, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns,
            )
        except OSError:
            signature = (path, None)
        if force or signature != self.signature:
            self.palette = read_palette()
            self.signature = signature
        return self.palette


class ThemeWatcher:
    """Dependency-free Linux inotify; poll if unavailable or watches fail."""

    MASK = 0x0000000E | 0x00000FC0  # modify, attrib, close-write, moves, deletes
    IGNORED = 0x00008000

    def __init__(self):
        self.fd = -1
        self.watches = {}
        self.complete = False
        try:
            self.libc = ctypes.CDLL(None, use_errno=True)
            self.libc.inotify_init1.argtypes = [ctypes.c_int]
            self.libc.inotify_init1.restype = ctypes.c_int
            self.libc.inotify_add_watch.argtypes = [
                ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32,
            ]
            self.libc.inotify_add_watch.restype = ctypes.c_int
            self.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
            self.libc.inotify_rm_watch.restype = ctypes.c_int
            self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
            if self.fd >= 0:
                self.refresh()
        except (AttributeError, OSError):
            self.close()

    def refresh(self):
        if self.fd < 0:
            return
        watches = {}
        self.complete = True
        for root in theme_roots():
            # Watch each ancestor, including the nearest existing one when
            # XDG directories are absent. add_watch follows theme symlinks.
            path = root / "theme/colors.toml"
            child = None
            boundary = root.parent.parent
            for candidate in [path, *path.parents]:
                wd = self.libc.inotify_add_watch(
                    self.fd, os.fsencode(candidate), self.MASK
                )
                if wd >= 0:
                    names = watches.setdefault(wd, set())
                    names.add(child.name if child else "")
                    if candidate == boundary or candidate in boundary.parents:
                        break
                elif candidate.exists():
                    self.complete = False
                child = candidate
        for wd in self.watches.keys() - watches.keys():
            self.libc.inotify_rm_watch(self.fd, wd)
        self.watches = watches

    def changed(self):
        changed = False
        while True:
            try:
                events = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not events:
                break
            offset = 0
            while offset < len(events):
                wd, mask, _, length = struct.unpack_from("iIII", events, offset)
                name = os.fsdecode(events[offset + 16:offset + 16 + length])
                name = name.rstrip("\0")
                offset += 16 + length
                if mask & self.IGNORED:
                    self.watches.pop(wd, None)
                elif not name or name in self.watches.get(wd, ()):
                    # Includes queue overflow: reconcile paths and contents.
                    changed = True
        return changed

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        self.watches.clear()


def write_message(message, stream):
    payload = json.dumps(message).encode("utf-8")
    stream.write(struct.pack("=I", len(payload)))
    stream.write(payload)
    stream.flush()


def serve():
    previous = None
    last_sent = 0
    cache = PaletteCache()
    watcher = ThemeWatcher()
    force = True
    try:
        while True:
            signature = cache.signature
            palette = cache.read(force)
            if force or signature != cache.signature or not watcher.complete:
                watcher.refresh()
            now = time.monotonic()
            if palette != previous or now - last_sent >= 10:
                write_message(palette, sys.stdout.buffer)
                previous, last_sent = palette, now
            inputs = [sys.stdin.buffer]
            if watcher.fd >= 0:
                inputs.append(watcher.fd)
            # Reconcile missed events/failed watches; fallback is subsecond.
            timeout = 1 if watcher.complete else 0.25
            readable, _, _ = select.select(inputs, [], [], timeout)
            if sys.stdin.buffer in readable:
                if not os.read(sys.stdin.fileno(), 4096):
                    return
            force = watcher.fd in readable and watcher.changed()
    finally:
        watcher.close()


if __name__ == "__main__":
    try:
        if "--print" in sys.argv:
            print(json.dumps(read_palette(), indent=2))
        else:
            serve()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
