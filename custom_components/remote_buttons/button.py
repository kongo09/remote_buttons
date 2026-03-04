"""Button entities for learnt remote commands."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

ATTR_COMMAND = "command"
ATTR_DELAY_SECS = "delay_secs"
ATTR_DEVICE = "device"
ATTR_ENTITY_ID = "entity_id"
ATTR_NUM_REPEATS = "num_repeats"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button platform — stores callback for dynamic entity creation."""
    hass.data[DOMAIN][entry.entry_id]["async_add_entities"] = async_add_entities


class RemoteCommandButton(ButtonEntity):
    """A button that sends a single learnt remote command."""

    _attr_has_entity_name = True

    def __init__(
        self,
        remote_entity_id: str,
        remote_device_id: str,
        remote_domain: str,
        subdevice: str,
        command_name: str,
        config_entry_id: str | None = None,
    ) -> None:
        """Initialise the button."""
        self._remote_entity_id = remote_entity_id
        self._remote_domain = remote_domain
        self._remote_device_id = remote_device_id
        self._subdevice = subdevice
        self._command = command_name
        self._config_entry_id = config_entry_id

        self._attr_unique_id = f"remote_buttons_{remote_entity_id}_{subdevice}_{command_name}"
        self._attr_name = f"{subdevice} {command_name}" if subdevice else command_name

    @property
    def device_info(self) -> DeviceInfo:
        """Link this button to a device grouped by subdevice."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._remote_entity_id}_{self._subdevice}")},
            name=self._subdevice or "Remote",
            via_device=(self._remote_domain, self._remote_device_id),
        )

    async def async_press(self) -> None:
        """Send the learnt command via remote.send_command."""
        service_data: dict[str, Any] = {
            ATTR_ENTITY_ID: self._remote_entity_id,
            ATTR_DEVICE: self._subdevice,
            ATTR_COMMAND: [self._command],
        }

        # Apply IR delay/repeats from the subdevice's number entities.
        ir_numbers = self._get_ir_numbers()
        if ir_numbers:
            delay_entity, repeats_entity = ir_numbers
            service_data[ATTR_DELAY_SECS] = delay_entity.native_value
            service_data[ATTR_NUM_REPEATS] = int(repeats_entity.native_value)

        await self.hass.services.async_call(
            "remote",
            "send_command",
            service_data,
            blocking=True,
        )

    def _get_ir_numbers(self) -> tuple | None:
        """Look up the IR number entities for this button's subdevice."""
        if not self._config_entry_id:
            return None
        data = self.hass.data.get(DOMAIN, {}).get(self._config_entry_id, {})
        return data.get("ir_numbers", {}).get((self._remote_entity_id, self._subdevice))
