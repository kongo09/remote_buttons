# Remote Buttons

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HACS validation](https://github.com/kongo09/remote_buttons/actions/workflows/hacs.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/hacs.yml)
[![Linting](https://github.com/kongo09/remote_buttons/actions/workflows/ci.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/ci.yml)
[![Tests](https://github.com/kongo09/remote_buttons/actions/workflows/tests.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/kongo09/remote_buttons)](https://github.com/kongo09/remote_buttons/releases)

A Home Assistant custom integration that automatically creates **button entities** for every learnt command on your IR/RF remote entities.

Works with any remote integration that stores learnt commands using HA's `helpers.storage.Store` convention, including:

- **Broadlink** remotes
- **tuya-local** remotes

## Screenshots

| Integration overview | Device controls |
|---|---|
| ![Integration overview](images/main_screen.png) | ![Device controls](images/controls.png) |

## How it works

1. You configure which remote entities to watch.
2. The integration reads each remote's stored commands and creates a button entity per command.
3. When you press a button, it calls `remote.send_command` on the underlying remote — no direct hardware interaction.
4. When you learn or delete commands, the integration detects the change and updates buttons automatically.
5. For IR sub-devices, two configuration entities are created — **IR delay** (seconds between commands) and **IR repeat** (number of repeats) — so you can tune send behaviour per device.
6. When a compatible remote integration is added, a repair issue notifies you so you can add it to the watch list.

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS.
2. Install "Remote buttons".
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for "Remote buttons".

### Manual

Copy `custom_components/remote_buttons/` into your HA `config/custom_components/` directory and restart.

## Configuration

The config flow presents a list of remote entities that support `learn_command`. Select the ones you want to watch, and buttons will be created for all their learnt commands.

You can update the selection at any time via the integration's options flow.

## License

[MIT](LICENSE)
