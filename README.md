# Remote Buttons

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HACS validation](https://github.com/kongo09/remote_buttons/actions/workflows/hacs.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/hacs.yml)
[![Hassfest validation](https://github.com/kongo09/remote_buttons/actions/workflows/hassfest.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/hassfest.yml)
[![Linting](https://github.com/kongo09/remote_buttons/actions/workflows/ci.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/ci.yml)
[![Tests](https://github.com/kongo09/remote_buttons/actions/workflows/tests.yml/badge.svg)](https://github.com/kongo09/remote_buttons/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/kongo09/remote_buttons)](https://github.com/kongo09/remote_buttons/releases)

A Home Assistant custom integration that automatically creates **button entities** for every learnt command on your IR/RF remote entities.

Works with any remote integration that stores learnt commands using HA's `helpers.storage.Store` convention, especially:

- **[Broadlink](https://www.home-assistant.io/integrations/broadlink/)** remotes
- **[Tuya Local](https://github.com/make-all/tuya-local)** remotes

## Screenshots

| Integration overview | Device controls |
|---|---|
| ![Integration overview](images/main_screen.png) | ![Device controls](images/controls.png) |

## Coffee

<a href="https://www.buymeacoffee.com/kongo09" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## How it works

1. You configure which remote entities to watch.
2. The integration reads each remote's stored commands and creates a button entity per command.
3. When you press a button, it calls `remote.send_command` on the underlying remote — no direct hardware interaction.
4. When you learn or delete commands, the integration detects the change and updates buttons automatically.
5. For IR sub-devices, two configuration entities are created — **IR delay** (seconds between commands) and **IR repeat** (number of repeats) — so you can tune send behaviour per device.
6. When a compatible remote integration is added, a repair issue notifies you so you can add it to the watch list.

## Installation

### HACS (recommended)

1. If you haven't already, install [HACS](https://hacs.xyz/).
2. [![Add repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kongo09&repository=remote_buttons&category=integration)
3. Install **Remote Buttons** from the HACS integration list.
4. Restart Home Assistant.

### Manual

1. Download the [latest release](https://github.com/kongo09/remote_buttons/releases).
2. Extract and copy `custom_components/remote_buttons/` into your `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

1. [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=remote_buttons)
2. Select the remote entities you want to watch — only remotes that support `learn_command` are shown.
3. Button entities are created automatically for all learnt commands on the selected remotes.

You can update the selection at any time via **Settings > Devices & Services > Remote Buttons > Configure**.

## Removal

1. Go to **Settings > Devices & Services > Remote Buttons**.
2. Click the three-dot menu and select **Delete**.
3. All button and number entities created by the integration will be removed automatically.
