"""Number entities for IR command parameters (delay and repeat)."""

from __future__ import annotations

import contextlib

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_IR_DELAY, DEFAULT_IR_REPEATS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number platform — stores callback for dynamic entity creation."""
    hass.data[DOMAIN][entry.entry_id]["async_add_number_entities"] = async_add_entities


class RemoteCommandNumber(RestoreEntity, NumberEntity):
    """A number entity controlling an IR parameter for a virtual sub-device."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        remote_entity_id: str,
        remote_device_id: str,
        remote_domain: str,
        subdevice: str,
        param: str,
        name: str,
        default: float,
        min_val: float,
        max_val: float,
        step: float,
        unit: str | None = None,
    ) -> None:
        """Initialise the number entity."""
        self._remote_entity_id = remote_entity_id
        self._remote_domain = remote_domain
        self._remote_device_id = remote_device_id
        self._subdevice = subdevice

        self._attr_unique_id = f"remote_buttons_{remote_entity_id}_{subdevice}_ir_{param}"
        self._attr_name = name
        self._attr_native_value = default
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self) -> DeviceInfo:
        """Link this number to the same subdevice as buttons."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._remote_entity_id}_{self._subdevice}")},
            name=self._subdevice or "Remote",
            via_device=(self._remote_domain, self._remote_device_id),
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last known value on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            with contextlib.suppress(ValueError, TypeError):
                self._attr_native_value = float(last_state.state)

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        self._attr_native_value = value
        self.async_write_ha_state()


def create_ir_number_pair(
    remote_entity_id: str,
    remote_device_id: str,
    remote_domain: str,
    subdevice: str,
) -> tuple[RemoteCommandNumber, RemoteCommandNumber]:
    """Create the delay and repeats number entities for an IR sub-device."""
    delay = RemoteCommandNumber(
        remote_entity_id=remote_entity_id,
        remote_device_id=remote_device_id,
        remote_domain=remote_domain,
        subdevice=subdevice,
        param="delay_secs",
        name="IR delay",
        default=DEFAULT_IR_DELAY,
        min_val=0.0,
        max_val=10.0,
        step=0.1,
        unit=UnitOfTime.SECONDS,
    )
    repeats = RemoteCommandNumber(
        remote_entity_id=remote_entity_id,
        remote_device_id=remote_device_id,
        remote_domain=remote_domain,
        subdevice=subdevice,
        param="num_repeats",
        name="IR repeat",
        default=DEFAULT_IR_REPEATS,
        min_val=1.0,
        max_val=20.0,
        step=1.0,
    )
    return delay, repeats
