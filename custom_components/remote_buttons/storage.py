"""Storage readers for learnt remote commands."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)


class StorageReader(ABC):
    """Read learnt commands from a remote integration's storage."""

    @abstractmethod
    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Return {subdevice: {command_name: code}}."""


def _parse_storage_data(data: Any, store_key: str) -> dict[str, dict[str, Any]]:
    """Parse storage data, skipping malformed entries."""
    if not isinstance(data, dict):
        _LOGGER.warning(
            "Storage %s has unexpected type %s, expected dict",
            store_key,
            type(data).__name__,
        )
        return {}
    result: dict[str, dict[str, Any]] = {}
    for subdevice, commands in data.items():
        if not isinstance(commands, dict):
            _LOGGER.warning(
                "Storage %s: skipping subdevice %r (expected dict, got %s)",
                store_key,
                subdevice,
                type(commands).__name__,
            )
            continue
        result[subdevice] = commands
    return result


class BroadlinkStorageReader(StorageReader):
    """Read from broadlink_remote_{unique_id}_codes."""

    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load learnt commands from Broadlink storage."""
        store_key = f"broadlink_remote_{unique_id}_codes"
        try:
            store: Store = Store(hass, 1, store_key)
            data = await store.async_load()
        except Exception:
            _LOGGER.warning("Failed to read storage %s", store_key, exc_info=True)
            return {}
        if data is None:
            return {}
        return _parse_storage_data(data, store_key)


class TuyaLocalStorageReader(StorageReader):
    """Read from tuya_local_remote_{unique_id}_codes."""

    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load learnt commands from tuya-local storage."""
        store_key = f"tuya_local_remote_{unique_id}_codes"
        try:
            store: Store = Store(hass, 1, store_key)
            data = await store.async_load()
        except Exception:
            _LOGGER.warning("Failed to read storage %s", store_key, exc_info=True)
            return {}
        if data is None:
            return {}
        return _parse_storage_data(data, store_key)


READERS: dict[str, StorageReader] = {
    "broadlink": BroadlinkStorageReader(),
    "tuya_local": TuyaLocalStorageReader(),
}
