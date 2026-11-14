# Omarchy theme sync

The main_page site defaults to its existing Catppuccin Mocha colors.
This optional Linux companion applies the local Omarchy palette to open tabs,
without a page reload or site redeployment. Fresh/Classic selection is removed;
old saved selections are ignored.

## How it works

1. Brave starts `native_host.py` through native messaging.
2. The host reopens `$XDG_STATE_HOME/omarchy/current/theme/colors.toml`
   every second, following replacements of the current theme directory.
   `XDG_STATE_HOME` defaults to `~/.local/state`, as used by Omarchy Quattro.
   Older releases use `$XDG_CONFIG_HOME/omarchy/current/theme/colors.toml`,
   with `XDG_CONFIG_HOME` defaulting to `~/.config`. The legacy path is used
   only if the state `omarchy/current` directory does not exist.
3. The extension receives changes and forwards them to matching tabs.
4. An isolated content script overrides the site's shared CSS color tokens.

Background, foreground, and accent colors are used directly. Authored
supporting shades and named terminal colors are used when present. Missing
supporting shades are derived from background and foreground, not taken from
another theme. Current named-color and legacy `color1` through `color6` TOML
palettes are supported. Python 3.11 or newer is required for `tomllib`.

The extension is Manifest V3 and requires Chromium 105 or newer. It connects
only while matching site tabs exist. There is no HTTP server, listening port,
systemd service, theme hook, or modification to Omarchy settings. The host
sends a heartbeat every ten seconds. A disconnected, missing, malformed, or
stalled host restores Catppuccin; a stalled connection expires after 25 seconds.
The background worker retries failed native connections every five seconds.
Palettes are not persisted in site storage or synced between machines.

The extension can access only this project path:
<https://iop098321qwe.github.io/main_page/>. Other sites, local files, custom
domains, and preview servers are excluded. Change both the manifest match
pattern and the background sender check if the deployment URL changes.

## Install in Brave Origin

Install Git and Python 3.11+ first, then clone from GitHub:

```sh
mkdir -p ~/Documents/github_repositories
cd ~/Documents/github_repositories
git clone https://github.com/iop098321qwe/omarchy_theme_sync.git
cd omarchy_theme_sync
git switch develop
python3 install.py --browser brave-origin --configure-browser
```

Until a release is cut, use `develop`, where the extension source lives.
Private repository access requires GitHub authentication.
No administrator privileges are needed.

The installer copies companion files to
`~/.local/share/grymm-theme-companion` and writes a native messaging manifest
under `~/.config/BraveSoftware/Brave-Origin/NativeMessagingHosts`.
`XDG_DATA_HOME` and `XDG_CONFIG_HOME` override those base directories.
The launcher uses the exact Python executable running the installer. Rerun
installation after replacing that interpreter, for example after a major
Python upgrade or removing a virtual environment.

For Brave Origin, fully exit all browser and web-app windows and reopen.
`--configure-browser` merges the installed companion and an installed Calendar
bridge into launch flags without dropping stock extensions or other flags.
It backs up changed flags and preserves file permissions and symlinks.

For other supported browsers, or when automatic loading is unavailable,
perform these steps once per browser profile:

1. Open `brave://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select the `extension` subdirectory at the
   path printed by the installer.
3. Check that the extension ID matches the printed ID.
4. Open or reload the GitHub Pages site.

The public manifest key gives the unpacked extension a stable ID across
machines and paths. It is not a credential. The key is an unbreakable hash-like
value and is the documented 80-column exception in `manifest.json`.

For standard Brave, use `--browser brave`. Repeat `--browser` to register
multiple supported browsers. Run `python3 install.py --help` for
the complete list. Native messaging support in other packaging formats,
such as Flatpak or Snap, is not provided by this installer.

## Update from GitHub

```sh
cd ~/Documents/github_repositories/omarchy_theme_sync
git switch develop
git pull --ff-only origin develop
python3 install.py --browser brave-origin --browser brave --configure-browser
```

Use only the `--browser` values for browsers you use; repeat them on updates.
For browsers other than Brave Origin, omit `--configure-browser` unless you
also want to configure Brave Origin.

Fully exit Brave Origin, including web-app windows, and reopen it.
For manually loaded extensions, open the browser's extensions page, click
**Reload** on the companion card, and reload all open main_page tabs.
Verify a theme change updates the site. Git pull alone does not update the
installed files; rerun the installer every time.

Chezmoi no longer installs or updates the companion. The installed path,
native host name, and extension ID are unchanged for existing users.
Brave does not automatically update unpacked extensions like store extensions.

Non-Omarchy computers skip deployment and see Catppuccin. If companion files
remain after removing Omarchy, the host reports unavailable when there is no
valid active palette. Remove the native registration to explicitly disable
integration even if old Omarchy theme files remain on disk.

## Verify and troubleshoot

Print the detected palette without starting native messaging:

```sh
python3 native_host.py --print
python3 install.py --extension-id
```

`{"type": "unavailable"}` means that the current theme file is absent,
unreadable, or invalid. `background`, `foreground`, and `accent` must be
six-digit hexadecimal colors. Current palettes can declare `mode = "light"`
or `mode = "dark"`; otherwise the host infers the scheme from the background.

To test the live integration after the site changes have been deployed:

1. Open two site tabs, including a nested section page.
2. Change Omarchy themes through your normal desktop controls.
3. Confirm both tabs update, including inputs, notes, and the quick launcher.
4. Test a light palette as well as a dark palette.
5. Disable the extension and reload: both tabs should use Catppuccin.

If colors do not update, inspect the extension's service worker at
`brave://extensions`, verify the installed ID and native registration path,
and compare the host's printed palette with the active theme. Site inspection
shows `data-omarchy-theme="active"` on `<html>` while a palette is applied.

Automated tests cover native framing, live symlink changes, malformed themes,
recovery, installer repeatability, multi-tab delivery, reconnection, input
validation, and stale-connection fallback:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

With pytest available in the active Python environment, you can also run:

```sh
python -m pytest -q
```

## Remove

```sh
python3 install.py --browser brave-origin --uninstall
```

Repeat for other registered browsers, remove the extension from each profile,
and reload the site. The installer retains shared companion files so other
registered browsers keep working. Once all registrations are removed, the
`grymm-theme-companion` data directory can be deleted manually. If configured
through Brave Origin flags, remove only the companion path from
`~/.config/brave-origin-flags.conf`; preserve other extensions and flags.

## Repository maintenance

This repository maintains the companion previously hosted in
`main_page/companion`. Its extension version, stable manifest key, native host
name, and installed paths are unchanged. Releases are cut manually; migration
does not set a release version.

Installation and updates are owned by this repository, not by dotfiles sync.
