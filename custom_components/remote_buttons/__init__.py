"""Remote Buttons — auto-create button entities for learnt remote commands."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DELETE_SCAN_DELAY, DOMAIN, LEARN_SCAN_DELAY
from .storage import READERS

_LOGGER = logging.getLogger(__name__)

type RemoteButtonsConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: RemoteButtonsConfigEntry) -> bool:
    """Set up Remote Buttons from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "known_commands": {},
        "scan_unsub": None,
    }

    # Forward to the button platform.
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
def _make_service_listener(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry
):
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
def _schedule_scan(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry, delay: float
) -> None:
    """Cancel any pending scan and schedule a new one after *delay* seconds."""
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    cancel = data.get("scan_unsub")
    if cancel is not None:
        cancel()

    async def _run_scan(_now=None):
        await async_scan_remote_commands(hass, entry)

    data["scan_unsub"] = hass.helpers.event.async_call_later(delay, _run_scan)


async def async_scan_remote_commands(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry
) -> None:
    """Scan storage for all watched remotes and add/remove button entities."""
    # TODO: Implement full scan logic — read storage per remote, diff against
    # known commands, call async_add_entities / async_remove for changes.
    _LOGGER.debug("Scanning remote commands for entry %s", entry.entry_id)
