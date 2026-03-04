"""Remote Buttons — auto-create button entities for learnt remote commands."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later

from .button import RemoteCommandButton
from .const import DELETE_SCAN_DELAY, DOMAIN, LEARN_SCAN_DELAY
from .storage import READERS

_LOGGER = logging.getLogger(__name__)

type RemoteButtonsConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> bool:
    """Set up Remote Buttons from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "known_commands": set(),
        "async_add_entities": None,
        "scan_unsub": None,
    }

    # Forward to the button platform (stores async_add_entities callback).
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.BUTTON])

    # Initial scan of all watched remotes' storage.
    await async_scan_remote_commands(hass, entry)

    # Listen for learn/delete service calls.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_CALL_SERVICE, _make_service_listener(hass, entry))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, [Platform.BUTTON])
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

    entity_reg = er.async_get(hass)
    watched = entry.data.get("remote_entities", [])

    current: set[tuple[str, str, str]] = set()
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
                )
            )
        add_entities(new_buttons)

    # Removed commands → remove entities from registry.
    removed = known - current
    for remote_entity_id, subdevice, cmd_name in removed:
        uid = f"remote_buttons_{remote_entity_id}_{subdevice}_{cmd_name}"
        ent_id = entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid)
        if ent_id:
            entity_reg.async_remove(ent_id)

    data["known_commands"] = current

    _LOGGER.debug(
        "Scan complete: %d current, %d added, %d removed",
        len(current),
        len(added),
        len(removed),
    )
