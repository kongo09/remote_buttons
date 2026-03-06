# Agent Guidelines for Remote Buttons

This file provides context for AI coding agents working on this codebase.

## Project overview

A Home Assistant (HA) custom integration that auto-creates button entities for every learnt IR/RF command stored by Broadlink or Tuya Local remote integrations. Distributed via HACS.

- Domain: `remote_buttons`
- Platforms: `button`, `number`
- No external dependencies — uses only HA core APIs
- No polling — fully event-driven
- Quality scale: Gold (see checklist below)

## File structure

```
custom_components/remote_buttons/
  __init__.py      # Entry setup/unload, scanning, service & entity registry listeners
  button.py        # RemoteCommandButton entity (one per learnt command)
  number.py        # RemoteCommandNumber entity (IR delay + repeat per sub-device)
  config_flow.py   # Config flow, reconfigure flow, options flow
  storage.py       # StorageReader abstraction (Broadlink, Tuya Local)
  repairs.py       # Repair issue flow for newly detected remotes
  diagnostics.py   # Config entry diagnostics
  const.py         # Constants (DOMAIN, delays, defaults)
  icons.json       # Entity icon mappings
  strings.json     # English strings (auto-synced to translations/ by HA tooling)
  manifest.json    # Integration metadata
  brand/           # Brand icons
  translations/    # en, de, es, fr

tests/
  conftest.py          # Shared fixtures: setup_remote(), make_entry()
  test_init.py         # Core logic: scanning, listeners, cleanup
  test_button.py       # Button entity behaviour
  test_number.py       # Number entity behaviour
  test_config_flow.py  # Config, options, and reconfigure flows
  test_diagnostics.py  # Diagnostics output
  test_repairs.py      # Repair flow
  test_storage.py      # Storage readers
```

## Architecture

### Data flow

1. User selects remote entities to watch (config flow stores list in `entry.data`)
2. `async_setup_entry` forwards to button/number platforms, runs initial scan
3. `async_scan_remote_commands` reads each remote's storage via platform-specific `StorageReader`
4. New commands -> new `RemoteCommandButton` entities; deleted commands -> entities removed from registry
5. IR sub-devices get `RemoteCommandNumber` pairs (delay + repeats)
6. Service listener detects `remote.learn_command` / `remote.delete_command` -> schedules delayed re-scan
7. Entity registry listener detects new/removed remotes -> creates repair issues or cleans up

### Key patterns

- **RuntimeData**: `RemoteButtonsData` dataclass on `entry.runtime_data` holds known commands, IR state, entity callbacks, scan lock
- **Scan lock**: `asyncio.Lock` serialises concurrent scans to prevent state corruption
- **Targeted scans**: When a specific remote triggers a re-scan, only that remote is scanned; other known state is preserved
- **Dynamic entity creation**: `async_add_entities` callbacks are stored in runtime data and called during scans — entities are not created in platform setup
- **Device hierarchy**: Sub-device devices use `(DOMAIN, "{remote_entity_id}_{subdevice}")` identifiers, linked to the physical remote via `via_device`

### Storage readers

Each supported platform has a `StorageReader` that reads `{subdevice: {command_name: code}}` from HA's `helpers.storage.Store`. To add a new platform:

1. Create a new `StorageReader` subclass in `storage.py`
2. Add it to the `READERS` dict
3. Add the platform to `after_dependencies` in `manifest.json`

## Development

### Prerequisites

- Python 3.13+
- Linux (HA core requires `fcntl`, unavailable on Windows/macOS)
- Devcontainer recommended

### Linting

Always run both checks:

```bash
ruff check
ruff format --check
```

Fix formatting with `ruff format`. No mypy — HA core lacks complete type stubs.

### Testing

```bash
python -m pytest tests/ -x -q
```

Coverage target: 95%+ (currently 96%). Check with:

```bash
python -m pytest tests/ --cov=custom_components.remote_buttons --cov-report=term-missing
```

Key testing notes:

- Config flow tests require the `enable_custom_integrations` fixture
- Patch `ServiceRegistry.async_call` at the class level, not the instance
- Use `setup_remote()` and `make_entry()` helpers from `conftest.py`
- Mock storage reads via `patch("custom_components.remote_buttons.storage.Store.async_load", ...)`

### Translations

- Edit `strings.json` — a pre-commit hook syncs it to `translations/en.json` automatically
- Maintain translations in `de.json`, `es.json`, `fr.json` manually
- All config flow steps, abort reasons, exceptions, and entity names must have translation strings

### Commits and PRs

- One commit per logical change, one PR per phase/theme
- Commit messages: imperative mood, short first line, body explains "why"
- CI runs: HACS validation, hassfest, ruff lint, ruff format, pytest

## HA conventions used

| Convention | Implementation |
|---|---|
| `has_entity_name = True` | All entities use translation keys, not hardcoded names |
| `ConfigEntry.runtime_data` | Typed `RemoteButtonsData` dataclass |
| `entry.async_on_unload` | All listeners registered with cleanup |
| `_async_abort_entries_match()` | Prevents duplicate config entries |
| `async_update_reload_and_abort` | Used in reconfigure flow |
| `EntityCategory.CONFIG` | Number entities are configuration, not primary |
| `RestoreEntity` | Number entities restore last value on restart |
| `HomeAssistantError` with `translation_key` | Translated exceptions on button press failure |
| `icons.json` | Static icon assignments per entity translation key |
| Repair issues with fix flows | Auto-detected new remotes prompt user to add them |
| `PARALLEL_UPDATES = 0` | No throttling (entities delegate to `remote.send_command`) |

## Quality scale status (Gold)

### Bronze (all met)
`brands`, `common-modules`, `config-flow`, `config-flow-test-coverage`, `dependency-transparency`, `docs-high-level-description`, `docs-installation-instructions`, `docs-removal-instructions`, `entity-event-setup`, `entity-unique-id`, `has-entity-name`, `runtime-data`, `unique-config-entry`

### Silver (all met)
`config-entry-unloading`, `docs-configuration-parameters`, `docs-installation-parameters`, `integration-owner`, `log-when-unavailable`, `parallel-updates`, `test-coverage`

### Gold (all met)
`devices`, `diagnostics`, `dynamic-devices`, `entity-category`, `entity-translations`, `exception-translations`, `icon-translations`, `reconfiguration-flow`, `repair-issues`, `stale-devices`, `docs-data-update`, `docs-examples`, `docs-known-limitations`, `docs-supported-devices`, `docs-supported-functions`, `docs-troubleshooting`, `docs-use-cases`

### N/A rules
`action-setup`, `appropriate-polling`, `docs-actions`, `action-exceptions`, `reauthentication-flow`, `entity-unavailable`, `discovery`, `discovery-update-info`, `entity-device-class`, `entity-disabled-by-default`, `test-before-configure`, `test-before-setup`, `async-dependency`, `inject-websession`

### Platinum (not pursued)
`strict-typing` — HA core lacks complete type stubs, making full mypy compliance impractical for custom integrations.
