"""Storage readers for learnt remote commands."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


class StorageReader(ABC):
    """Read learnt commands from a remote integration's storage."""

    @abstractmethod
    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Return {subdevice: {command_name: code}}."""


class BroadlinkStorageReader(StorageReader):
    """Read from broadlink_remote_{unique_id}_codes."""

    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load learnt commands from Broadlink storage."""
        store: Store = Store(hass, 1, f"broadlink_remote_{unique_id}_codes")
        data = await store.async_load()
        if data is None:
            return {}
        # Broadlink stores {subdevice: {command: code}}.
        return {k: v for k, v in data.items() if isinstance(v, dict)}


class TuyaLocalStorageReader(StorageReader):
    """Read from tuya_local_remote_{unique_id}_codes."""

    async def async_read_commands(
        self, hass: HomeAssistant, unique_id: str
    ) -> dict[str, dict[str, Any]]:
        """Load learnt commands from tuya-local storage."""
        store: Store = Store(hass, 1, f"tuya_local_remote_{unique_id}_codes")
        data = await store.async_load()
        if data is None:
            return {}
        # Same structure as Broadlink.
        return {k: v for k, v in data.items() if isinstance(v, dict)}


READERS: dict[str, StorageReader] = {
    "broadlink": BroadlinkStorageReader(),
    "tuya_local": TuyaLocalStorageReader(),
}
