import importlib.util
import io
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile
from unittest.mock import Mock
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "native_host.py"
SPEC = importlib.util.spec_from_file_location("theme_host", HOST)
assert SPEC is not None and SPEC.loader is not None
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


def write_theme(directory, background, foreground, accent, extra=""):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "colors.toml").write_text(
        f'background = "{background}"\n'
        f'foreground = "{foreground}"\n'
        f'accent = "{accent}"\n' + extra
    )


def receive(process):
    assert select.select([process.stdout], [], [], 5)[0], "Host timed out"
    size = struct.unpack("=I", process.stdout.read(4))[0]
    assert 0 < size < 65536
    return json.loads(process.stdout.read(size))


@pytest.mark.parametrize("poll_only", [False, True])
def test_native_host_tracks_theme_replacement_and_fallback(poll_only):
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary)
        dark, light = config / "dark", config / "light"
        write_theme(dark, "#101020", "#eeeeff", "#8888ff")
        write_theme(light, "#ffffff", "#202020", "#004499")
        current = config / "omarchy/current"
        current.mkdir(parents=True)
        link = current / "theme"
        link.symlink_to(dark, target_is_directory=True)
        command = [sys.executable, str(HOST)]
        if poll_only:
            command = [sys.executable, "-c", (
                "import native_host; "
                "native_host.ctypes.CDLL = lambda *a, **k: None; "
                "native_host.serve()"
            )]
        process = subprocess.Popen(
            command, cwd=ROOT, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "XDG_CONFIG_HOME": str(config),
                 "XDG_STATE_HOME": str(config / "state")}, bufsize=0,
        )
        assert process.stdin is not None
        try:
            first = receive(process)
            assert first["colors"]["base"] == "#101020"
            assert first["colors"]["text"] == "#eeeeff"
            assert first["colors"]["sapphire"] == "#8888ff"
            assert first["scheme"] == "dark"
            replacement = current / "next"
            replacement.symlink_to(light, target_is_directory=True)
            replacement.replace(link)
            second = receive(process)
            assert second["colors"]["base"] == "#ffffff"
            assert second["scheme"] == "light"
            (light / "colors.toml").write_text("invalid TOML !!!")
            assert receive(process) == {"type": "unavailable"}
            link.unlink()
            write_theme(dark, "#101020", "#eeeeff", "#8888ff")
            link.symlink_to(dark, target_is_directory=True)
            assert receive(process)["type"] == "palette"
            process.stdin.close()
            assert process.wait(timeout=5) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def test_palette_cache_skips_unchanged_parsing_and_tracks_replacement(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    theme = tmp_path / "state/omarchy/current/theme"
    write_theme(theme, "#111111", "#eeeeee", "#8888ff")
    load = Mock(wraps=host.tomllib.load)
    monkeypatch.setattr(host.tomllib, "load", load)
    cache = host.PaletteCache()
    first = cache.read()
    for _ in range(20):
        assert cache.read() is first
    assert load.call_count == 1
    assert cache.read(force=True) == first
    assert load.call_count == 2
    replacement = theme / "next.toml"
    replacement.write_text('background = "#222222"\nforeground = "#eeeeee"\n'
                           'accent = "#8888ff"\n')
    replacement.replace(theme / "colors.toml")
    assert cache.read()["colors"]["base"] == "#222222"
    (theme / "colors.toml").unlink()
    assert cache.read() == {"type": "unavailable"}
    write_theme(theme, "#333333", "#eeeeee", "#8888ff")
    assert cache.read()["colors"]["base"] == "#333333"


def test_watcher_tracks_missing_directories_and_symlink_targets(
    tmp_path, monkeypatch,
):
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    watcher = host.ThemeWatcher()
    try:
        if watcher.fd < 0:
            pytest.skip("inotify unavailable")

        def changed():
            assert select.select([watcher.fd], [], [], 0.5)[0]
            assert watcher.changed()
            watcher.refresh()

        current = state / "omarchy/current"
        current.mkdir(parents=True)
        changed()
        theme = tmp_path / "external"
        write_theme(theme, "#111111", "#eeeeee", "#8888ff")
        (current / "theme").symlink_to(theme, target_is_directory=True)
        changed()
        write_theme(theme, "#222222", "#eeeeee", "#8888ff")
        changed()
        (theme / "unrelated").write_text("not a palette")
        assert select.select([watcher.fd], [], [], 0.5)[0]
        assert not watcher.changed()
        replacement = tmp_path / "replacement"
        write_theme(replacement, "#333333", "#eeeeee", "#8888ff")
        (current / "next").symlink_to(replacement, target_is_directory=True)
        (current / "next").replace(current / "theme")
        changed()
        # Drain ignored-watch events caused by rearming.
        watcher.changed()
        write_theme(replacement, "#444444", "#eeeeee", "#8888ff")
        changed()
        fd = watcher.fd
    finally:
        watcher.close()
    with pytest.raises(OSError):
        os.fstat(fd)


def test_watcher_falls_back_when_inotify_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("inotify denied")
    monkeypatch.setattr(host.ctypes, "CDLL", unavailable)
    watcher = host.ThemeWatcher()
    assert watcher.fd == -1
    assert not watcher.complete
    watcher.refresh()
    watcher.close()


def test_unchanged_palette_still_sends_heartbeats_and_closes_watcher(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    theme = tmp_path / "state/omarchy/current/theme"
    write_theme(theme, "#111111", "#eeeeee", "#8888ff")
    watcher = SimpleNamespace(
        fd=-1, complete=False, refresh=Mock(), close=Mock(),
    )
    output = io.BytesIO()
    stdin = SimpleNamespace(buffer=object(), fileno=lambda: 123)
    times = iter([1, 6, 11])
    polls = iter([False, False, True])
    load = Mock(wraps=host.tomllib.load)
    with monkeypatch.context() as patch:
        patch.setattr(host, "ThemeWatcher", lambda: watcher)
        patch.setattr(host.tomllib, "load", load)
        patch.setattr(host.time, "monotonic", lambda: next(times))
        patch.setattr(host.sys, "stdin", stdin)
        patch.setattr(host.sys, "stdout", SimpleNamespace(buffer=output))
        patch.setattr(host.os, "read", lambda *args: b"")
        patch.setattr(host.select, "select", lambda *args: (
            [stdin.buffer] if next(polls) else [], [], [],
        ))
        host.serve()
    watcher.close.assert_called_once()
    assert load.call_count == 1
    output.seek(0)
    messages = []
    while header := output.read(4):
        messages.append(json.loads(output.read(struct.unpack("=I", header)[0])))
    assert len(messages) == 2
    assert messages[0] == messages[1]


def test_current_and_legacy_colors_and_invalid_values():
    base = {
        "background": "#112233", "foreground": "#eeeeff",
        "accent": "#55aaff", "mode": "dark",
    }
    modern = host.palette_from_colors({
        **base, "red": "#ff1100", "lighter_background": "#223344",
        "selection": "#334455", "light_foreground": "#ddddee",
    })
    assert modern["colors"]["red"] == "#ff1100"
    assert modern["colors"]["surface0"] == "#223344"
    assert modern["colors"]["surface2"] == "#334455"
    legacy = host.palette_from_colors({**base, "color1": "#bb0000"})
    assert legacy["colors"]["red"] == "#bb0000"
    assert len(modern["colors"]) == 26
    for invalid in ("red", "#123", "url(evil)", None, 123):
        try:
            host.palette_from_colors({**base, "accent": invalid})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Accepted invalid color: {invalid}")
    with tempfile.TemporaryDirectory() as temporary:
        assert host.read_palette(temporary, temporary) == {
            "type": "unavailable"
        }


def test_quattro_state_directory_takes_precedence_over_legacy_config():
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary) / "config"
        state = Path(temporary) / "state"
        legacy = config / "omarchy/current/theme"
        current = state / "omarchy/current/theme"
        write_theme(legacy, "#111111", "#eeeeee", "#aaaaff")
        detected = host.read_palette(config, state)
        assert detected["colors"]["base"] == "#111111"
        write_theme(current, "#222222", "#dddddd", "#9999ee")
        detected = host.read_palette(config, state)
        assert detected["colors"]["base"] == "#222222"
        (current / "colors.toml").unlink()
        assert host.read_palette(config, state) == {"type": "unavailable"}


def test_installer_is_repeatable_and_uses_stable_extension_id():
    with tempfile.TemporaryDirectory(prefix="theme home ") as temporary:
        home = Path(temporary)
        config, data = home / "config", home / "data"
        environment = {
            **os.environ, "HOME": str(home),
            "XDG_CONFIG_HOME": str(config), "XDG_DATA_HOME": str(data),
            "XDG_STATE_HOME": str(home / "state"),
        }
        command = [sys.executable, str(ROOT / "install.py")]
        for _ in range(2):
            subprocess.run(command, env=environment, check=True,
                           capture_output=True)
        registration = (
            config / "BraveSoftware/Brave-Origin/NativeMessagingHosts"
            / f"{host.HOST_NAME}.json"
        )
        manifest = json.loads(registration.read_text())
        identifier = subprocess.check_output(
            command + ["--extension-id"], text=True
        ).strip()
        assert len(identifier) == 32
        assert manifest["allowed_origins"] == [
            f"chrome-extension://{identifier}/"
        ]
        result = subprocess.check_output(
            [manifest["path"], "--print"], env=environment, text=True
        )
        assert json.loads(result) == {"type": "unavailable"}
        subprocess.run(command + ["--uninstall"], env=environment,
                       check=True, capture_output=True)
        assert not registration.exists()


def test_extension_behavior_and_syntax():
    for script in (ROOT / "extension").glob("*.js"):
        subprocess.run(["node", "--check", str(script)], check=True)
    subprocess.run(
        ["node", "--test", str(ROOT / "tests/theme_extension.cjs")],
        check=True,
    )
