"""Remote Buttons — auto-create button entities for learnt remote commands."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from .button import RemoteCommandButton
from .const import DELETE_SCAN_DELAY, DOMAIN, LEARN_SCAN_DELAY
from .number import create_ir_number_pair
from .storage import READERS

_LOGGER = logging.getLogger(__name__)

type RemoteButtonsConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> bool:
    """Set up Remote Buttons from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "known_commands": set(),
        "ir_subdevices": set(),
        "ir_numbers": {},
        "async_add_entities": None,
        "async_add_number_entities": None,
        "scan_unsub": None,
    }

    # Forward to button and number platforms (stores async_add_entities callbacks).
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.BUTTON, Platform.NUMBER]
    )

    # Initial scan of all watched remotes' storage.
    await async_scan_remote_commands(hass, entry)

    # Listen for learn/delete service calls.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CALL_SERVICE, _make_service_listener(hass, entry))
    )

    # Listen for new remote entities being registered.
    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            _make_entity_registry_listener(hass, entry),
        )
    )

    # Dismiss stale repair issues when options are updated.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.BUTTON, Platform.NUMBER]
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        cancel = data.get("scan_unsub")
        if cancel is not None:
            cancel()
    return unload_ok


@callback
def _make_service_listener(hass: HomeAssistant, entry: RemoteButtonsConfigEntry):
    """Return an event listener that triggers a delayed re-scan on learn/delete."""
    watched = set(entry.data.get("remote_entities", []))

    @callback
    def _listener(event: Event) -> None:
        service_data: dict[str, Any] = event.data
        domain = service_data.get("domain", "")
        service = service_data.get("service", "")

        if domain != "remote":
            return

        if service == "learn_command":
            delay = LEARN_SCAN_DELAY
        elif service == "delete_command":
            delay = DELETE_SCAN_DELAY
        else:
            return

        # Check whether the targeted entity is one we watch.
        call_data = service_data.get("service_data", {})
        entity_id = call_data.get("entity_id")
        if isinstance(entity_id, list):
            entity_id = entity_id[0] if entity_id else None
        if entity_id not in watched:
            return

        _LOGGER.debug(
            "Detected remote.%s for %s — scheduling re-scan in %ss",
            service,
            entity_id,
            delay,
        )
        _schedule_scan(hass, entry, delay)

    return _listener


@callback
def _schedule_scan(hass: HomeAssistant, entry: RemoteButtonsConfigEntry, delay: float) -> None:
    """Cancel any pending scan and schedule a new one after *delay* seconds."""
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    cancel = data.get("scan_unsub")
    if cancel is not None:
        cancel()

    @callback
    def _run_scan(_now) -> None:
        hass.async_create_task(async_scan_remote_commands(hass, entry))

    data["scan_unsub"] = async_call_later(hass, delay, _run_scan)


@callback
def _make_entity_registry_listener(hass: HomeAssistant, entry: RemoteButtonsConfigEntry):
    """Return a listener for entity registry changes (new/removed remotes)."""

    @callback
    def _listener(event: Event) -> None:
        action = event.data.get("action")
        entity_id = event.data.get("entity_id", "")

        if not entity_id.startswith("remote."):
            return

        if action == "create":
            _handle_new_remote(hass, entry, entity_id)
        elif action == "remove":
            _handle_removed_remote(hass, entry, entity_id)

    return _listener


@callback
def _handle_new_remote(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry, entity_id: str
) -> None:
    """Raise a repair issue when a new compatible remote appears."""
    watched = set(entry.data.get("remote_entities", []))
    if entity_id in watched:
        return

    entity_reg = er.async_get(hass)
    reg_entry = entity_reg.async_get(entity_id)
    if not reg_entry or reg_entry.platform not in READERS:
        return

    _LOGGER.info("New compatible remote detected: %s", entity_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"new_remote_{entity_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_remote_found",
        translation_placeholders={"entity_id": entity_id},
    )


@callback
def _handle_removed_remote(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry, entity_id: str
) -> None:
    """Clean up buttons, devices, and config when a watched remote is removed."""
    watched = list(entry.data.get("remote_entities", []))
    if entity_id not in watched:
        return

    _LOGGER.info("Watched remote removed: %s — cleaning up", entity_id)

    data = hass.data[DOMAIN].get(entry.entry_id, {})
    known: set[tuple[str, str, str]] = data.get("known_commands", set())

    # Find all commands belonging to this remote.
    to_remove = {(r, s, c) for r, s, c in known if r == entity_id}

    # Remove button entities and collect affected subdevices.
    entity_reg = er.async_get(hass)
    subdevices: set[str] = set()
    for _remote, subdevice, cmd_name in to_remove:
        subdevices.add(subdevice)
        uid = f"remote_buttons_{entity_id}_{subdevice}_{cmd_name}"
        ent_id = entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid)
        if ent_id:
            entity_reg.async_remove(ent_id)

    # Remove IR number entities for affected subdevices.
    ir_numbers: dict = data.get("ir_numbers", {})
    ir_subdevices: set = data.get("ir_subdevices", set())
    for subdevice in subdevices:
        _remove_ir_numbers(entity_reg, entity_id, subdevice, ir_numbers, ir_subdevices)

    # Remove subdevice device entries that have no remaining entities.
    device_reg = dr.async_get(hass)
    for subdevice in subdevices:
        dev_identifier = (DOMAIN, f"{entity_id}_{subdevice}")
        device_entry = device_reg.async_get_device(identifiers={dev_identifier})
        if device_entry:
            # Check if any entities still reference this device.
            remaining = er.async_entries_for_device(entity_reg, device_entry.id)
            if not remaining:
                device_reg.async_remove_device(device_entry.id)

    # Update known commands.
    data["known_commands"] = known - to_remove

    # Remove this remote from the watched list.
    watched.remove(entity_id)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "remote_entities": watched}
    )

    # Dismiss any repair issue for this remote.
    ir.async_delete_issue(hass, DOMAIN, f"new_remote_{entity_id}")


async def _async_options_updated(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> None:
    """Dismiss repair issues for remotes that are now watched."""
    watched = set(entry.data.get("remote_entities", []))
    for entity_id in watched:
        ir.async_delete_issue(hass, DOMAIN, f"new_remote_{entity_id}")


def _get_remote_info(hass: HomeAssistant, remote_entity_id: str) -> tuple[str, str] | None:
    """Return (platform, device_identifier) for a remote entity, or None."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    reg_entry = entity_reg.async_get(remote_entity_id)
    if not reg_entry or not reg_entry.device_id:
        return None

    platform = reg_entry.platform
    if platform not in READERS:
        return None

    device_entry = device_reg.async_get(reg_entry.device_id)
    if not device_entry:
        return None

    for ident_domain, identifier in device_entry.identifiers:
        if ident_domain == platform:
            return (platform, identifier)

    return None


async def async_scan_remote_commands(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> None:
    """Scan storage for all watched remotes and add/remove button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    known: set[tuple[str, str, str]] = data["known_commands"]
    add_entities = data.get("async_add_entities")
    add_number_entities = data.get("async_add_number_entities")
    ir_numbers: dict = data.setdefault("ir_numbers", {})
    ir_subdevices: set = data.setdefault("ir_subdevices", set())

    entity_reg = er.async_get(hass)
    watched = entry.data.get("remote_entities", [])

    current: set[tuple[str, str, str]] = set()
    current_ir_subdevices: set[tuple[str, str]] = set()
    remote_info: dict[str, tuple[str, str]] = {}

    for remote_entity_id in watched:
        info = _get_remote_info(hass, remote_entity_id)
        if not info:
            _LOGGER.debug("Skipping %s: not found or unsupported platform", remote_entity_id)
            continue

        platform, dev_id_str = info
        remote_info[remote_entity_id] = info

        reader = READERS[platform]
        commands = await reader.async_read_commands(hass, dev_id_str)
        for subdevice, cmds in commands.items():
            for cmd_name in cmds:
                current.add((remote_entity_id, subdevice, cmd_name))
            if _has_ir_codes(cmds):
                current_ir_subdevices.add((remote_entity_id, subdevice))

    # New commands → create buttons.
    added = current - known
    if added and add_entities:
        new_buttons = []
        for remote_entity_id, subdevice, cmd_name in sorted(added):
            platform, dev_id_str = remote_info[remote_entity_id]
            new_buttons.append(
                RemoteCommandButton(
                    remote_entity_id=remote_entity_id,
                    remote_device_id=dev_id_str,
                    remote_domain=platform,
                    subdevice=subdevice,
                    command_name=cmd_name,
                    config_entry_id=entry.entry_id,
                )
            )
        add_entities(new_buttons)

    # New IR subdevices → create number entities.
    new_ir = current_ir_subdevices - ir_subdevices
    if new_ir and add_number_entities:
        new_numbers = []
        for remote_entity_id, subdevice in sorted(new_ir):
            platform, dev_id_str = remote_info[remote_entity_id]
            delay, repeats = create_ir_number_pair(
                remote_entity_id=remote_entity_id,
                remote_device_id=dev_id_str,
                remote_domain=platform,
                subdevice=subdevice,
            )
            ir_numbers[(remote_entity_id, subdevice)] = (delay, repeats)
            new_numbers.extend([delay, repeats])
        add_number_entities(new_numbers)

    # Removed commands → remove entities from registry.
    removed = known - current
    for remote_entity_id, subdevice, cmd_name in removed:
        uid = f"remote_buttons_{remote_entity_id}_{subdevice}_{cmd_name}"
        ent_id = entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid)
        if ent_id:
            entity_reg.async_remove(ent_id)

    # IR subdevices that lost all IR codes → remove number entities.
    removed_ir = ir_subdevices - current_ir_subdevices
    for remote_entity_id, subdevice in removed_ir:
        _remove_ir_numbers(
            entity_reg, remote_entity_id, subdevice, ir_numbers, ir_subdevices
        )

    data["known_commands"] = current
    data["ir_subdevices"] = current_ir_subdevices

    _LOGGER.debug(
        "Scan complete: %d current, %d added, %d removed",
        len(current),
        len(added),
        len(removed),
    )


def _has_ir_codes(commands: dict[str, Any]) -> bool:
    """Return True if any command in the dict has an IR (non-RF) code."""
    for code_val in commands.values():
        if isinstance(code_val, list):
            if any(not str(c).startswith("rf:") for c in code_val):
                return True
        elif not str(code_val).startswith("rf:"):
            return True
    return False


@callback
def _remove_ir_numbers(
    entity_reg: er.EntityRegistry,
    remote_entity_id: str,
    subdevice: str,
    ir_numbers: dict,
    ir_subdevices: set,
) -> None:
    """Remove IR number entities for a subdevice."""
    key = (remote_entity_id, subdevice)
    ir_numbers.pop(key, None)
    ir_subdevices.discard(key)
    for param in ("delay_secs", "num_repeats"):
        uid = f"remote_buttons_{remote_entity_id}_{subdevice}_ir_{param}"
        ent_id = entity_reg.async_get_entity_id(Platform.NUMBER, DOMAIN, uid)
        if ent_id:
            entity_reg.async_remove(ent_id)
