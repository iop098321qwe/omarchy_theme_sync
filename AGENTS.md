# AGENTS.md

## Purpose

This file guides AI coding agents working in `omarchy_theme_sync`.
All work must follow best practices and industry standards where
applicable.

## Scope

This file covers repository-wide expectations for code, docs, and git
work.
It does not replace verified instructions in source files, tooling
configs,
or release automation.

## Formatting Rules

- Keep lines at 80 characters or fewer when practical.
- Allow longer lines only for URLs, code blocks, hashes, or commands
  that cannot be wrapped cleanly.

## Quick Start

- Read `README.md` first for project context and setup notes.
- Run `git status --short --branch` before editing to confirm repo
  state.
- Run `git diff --stat` before committing to review the change scope.
- Run `python3 -m pytest -q`.
- Install with `python3 install.py --browser brave-origin` only on request.

## Environment

- Git is required for day-to-day work in this repository.
- Linux, Python 3.11+, and Chromium 105+ support live native messaging.
- Tests require pytest and Node.js; npm provides commitlint and Husky.
- `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME` override defaults.

## Repository Overview

- `extension/` holds the browser extension; `tests/` holds Python/Node tests.
- Root Python scripts install the companion and publish native palettes.
- `docs/` links root documentation; `site/` is generated docs output.

## Tracked Files Overview

- `.github/workflows/docs.yml`: Zensical Pages build and deployment.
- `.gitignore`: local dependency, Python cache, and test exclusions.
- `.husky/commit-msg`: commitlint hook.
- `AGENTS.md`: repository instructions.
- `LICENSE`: repository license.
- `README.md`: installation, deployment, and recovery guide.
- `commitlint.config.cjs`: Conventional Commit validation.
- `docs/AGENTS.md`, `docs/README.md`: root documentation symlinks.
- `done.txt`: bootstrap completed-task placeholder.
- `extension/background.js`: shared native connection and retries.
- `extension/content.js`: live CSS palette overrides.
- `extension/manifest.json`: scoped MV3 permissions and stable public key.
- `inbox.txt.tuxedo-lock`: bootstrap inbox lock placeholder.
- `install.py`: native registration and companion installation.
- `native_host.py`: palette parsing and native messaging.
- `package-lock.json`: npm dependency lock.
- `package.json`: metadata, test command, and commitlint dependencies.
- `site/`: generated documentation; contents omitted from per-file listing.
- `tests/fixtures/palette.css`: standalone main_page palette test fixture.
- `tests/test_theme_companion.py`: host and installer regression tests.
- `tests/theme_extension.cjs`: mocked browser lifecycle tests.
- `todo.txt`: user-only task file; agents must not touch it.
- `zensical.toml`: documentation site configuration.

## Architecture

- The native host reads Omarchy TOML colors and sends framed JSON.
- The worker forwards validated palettes to matching main_page tabs.
- The content script sets CSS tokens; host failures restore site defaults.
- State-path theme discovery precedes legacy config-path discovery.
- Keep the manifest key, native host name, and installed paths stable.

## Commands

- `git status --short --branch`: show the current branch and worktree
  state.
- `git diff --stat`: review the size and spread of pending changes.
- `git log --oneline --decorate -5`: inspect recent commit history.
- `npm test`: run pytest, which also invokes the Node extension tests.
- `python3 native_host.py --print`: print the detected palette.
- `python3 install.py --extension-id`: print the stable extension ID.
- `zensical build --clean`: build documentation when installed.

## Testing

- `python3 -m pytest -q` covers framing, replacement, recovery, and install.
- Tests use isolated temporary directories and mocked browser APIs.
- Do not claim coverage, test gates, or suites that are not verified.

## Linting and Formatting

- Commitlint validates messages through the Husky commit hook.
- Python tests check extension JavaScript syntax using Node.
- No source formatter is configured.
- Keep changes minimal and consistent with the existing code style.

## CI and Release

- `.github/workflows/docs.yml` builds Zensical on `main` and `master`.
- Releases are manual; release-note filters are not defined here.
- Use Conventional Commits for every commit. Prefer a scope when it
  adds clarity.
- Never create, edit, or update `CHANGELOG.md` manually.
- `CHANGELOG.md` is generated and maintained by release tooling only.
- If release automation adds or changes generated files, let the
  tooling own those updates.

## Conventions

- Use small, correct changes that fit the existing project structure.
- Agents must never read, create, edit, delete, move, stage, commit, or
  otherwise touch `todo.txt`; only the user may modify it manually.
- Prefer amending small related corrections into the relevant unshared
  current-branch commit instead of separate fixup or cleanup commits.
- Use standalone, changelog-ready Conventional Commit headers.
- Verify behavior from the actual codebase before documenting or
  changing it.
- Keep `AGENTS.md` as instructions, not as a changelog, diary, or work
  log.
- Do not add update notes, status logs, or change summaries to
  `AGENTS.md`.

## Security and Compliance

- Never commit secrets, credentials, tokens, or private keys.
- Verify new dependencies, automation, and scripts before trusting
  them.

## Dependencies and Services

- No network listener, systemd service, or theme hook is installed.
- Only the main_page GitHub Pages path receives palette overrides.
- Releases are manual; do not change versions as part of migration.

## Troubleshooting

- If repo behavior is unclear, inspect tracked files and git history
  before making assumptions.
- If a generated or managed file changes unexpectedly, verify which
  tool owns it before editing.

## Refining Existing AGENTS.md

- Re-check every statement against the repository before keeping it.
- Remove stale, duplicated, or vague guidance.
- Replace placeholders with exact commands, paths, and verified
  workflows.
- Keep bullets short and easy for AI agents to scan.
- Preserve this section order when improving the file.

## Maintenance

- After any code, config, or doc change, verify that `AGENTS.md` still
  matches the repository.
- When `AGENTS.md` needs an update, make it in a separate `docs`
  Conventional Commit such as `docs(agents): update repo instructions`.
- Keep `AGENTS.md` out of mixed code commits whenever possible.
- Remove stale instructions instead of appending historical notes.
