# Omarchy theme sync

Apply the current Omarchy theme to the main_page site automatically.
The site falls back to Catppuccin Mocha when the companion is unavailable.

## What is downloaded

Cloning downloads the `main` branch: the browser extension, Python native
host, installer, browser setup helper, documentation, and tests.

Installation copies the extension and host to
`~/.local/share/grymm-theme-companion`, registers the native host with Brave
Origin, and adds the installed extension to Brave Origin's launch flags.
Existing browser flags and stock extensions are preserved.

Requires Linux with Omarchy, Git, Python 3.11+, and Brave Origin.
No administrator privileges are needed.

## Install

Run once in a terminal:

```sh
git clone --branch main https://github.com/iop098321qwe/omarchy_theme_sync.git
cd omarchy_theme_sync
python3 install.py --browser brave-origin --configure-browser
```

Fully exit Brave Origin, including all web-app windows, and reopen it.
Open <https://iop098321qwe.github.io/main_page/> and change your Omarchy theme
to check that the site's colors follow it.

## Update

Run from your existing checkout:

```sh
git switch main
git pull --ff-only origin main
python3 install.py --browser brave-origin --configure-browser
```

Fully exit Brave Origin and its web apps, then reopen them.
Pulling downloads the latest source; running the installer updates the
installed files and native host registration. Updates are not automatic.
Existing users keep the same installed paths and extension ID.

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

## Other browsers and installation details

For standard Brave, run `python3 install.py --browser brave` instead.
Repeat `--browser` to register multiple browsers, on both install and update.
Run `python3 install.py --help` for the supported browser list.
Flatpak and Snap browser packages are not supported.

For browsers other than Brave Origin, or if automatic loading is unavailable:

1. Open `brave://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select the `extension` subdirectory at the
   path printed by the installer.
3. Check that the extension ID matches the printed ID.
4. Open or reload the GitHub Pages site.

After updating a manually loaded extension, click **Reload** on its browser
settings card and reload the site tabs.

Private repository access requires GitHub authentication.
`XDG_DATA_HOME` and `XDG_CONFIG_HOME` override installation base directories.
The native registration is written under the selected browser's
`NativeMessagingHosts` directory. The launcher uses the Python executable
running the installer; rerun installation after replacing that interpreter.
The manifest's public key preserves the extension ID; it is not a credential.

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
