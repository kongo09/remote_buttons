"""Button entities for learnt remote commands."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

ATTR_COMMAND = "command"
ATTR_DEVICE = "device"
ATTR_ENTITY_ID = "entity_id"


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
    ) -> None:
        """Initialise the button."""
        self._remote_entity_id = remote_entity_id
        self._remote_domain = remote_domain
        self._remote_device_id = remote_device_id
        self._subdevice = subdevice
        self._command = command_name

        self._attr_unique_id = (
            f"remote_buttons_{remote_entity_id}_{subdevice}_{command_name}"
        )
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
        await self.hass.services.async_call(
            "remote",
            "send_command",
            {
                ATTR_ENTITY_ID: self._remote_entity_id,
                ATTR_DEVICE: self._subdevice,
                ATTR_COMMAND: [self._command],
            },
            blocking=True,
        )
