import importlib.util
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile


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


def test_native_host_tracks_theme_replacement_and_fallback():
    with tempfile.TemporaryDirectory() as temporary:
        config = Path(temporary)
        dark, light = config / "dark", config / "light"
        write_theme(dark, "#101020", "#eeeeff", "#8888ff")
        write_theme(light, "#ffffff", "#202020", "#004499")
        current = config / "omarchy/current"
        current.mkdir(parents=True)
        link = current / "theme"
        link.symlink_to(dark, target_is_directory=True)
        process = subprocess.Popen(
            [sys.executable, str(HOST)], stdin=subprocess.PIPE,
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
