"""Repair flows for Remote Buttons integration."""

from __future__ import annotations

from typing import Any

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


class AddRemoteRepairFlow(RepairsFlow):
    """Repair flow to add a newly detected remote to the watched list."""

    def __init__(self, entity_id: str) -> None:
        """Initialise the flow with the remote entity_id to add."""
        super().__init__()
        self._entity_id = entity_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Confirm adding the remote."""
        if user_input is not None:
            return await self._async_add_remote()

        return self.async_show_form(
            step_id="init",
            description_placeholders={"entity_id": self._entity_id},
        )

    async def _async_add_remote(self) -> data_entry_flow.FlowResult:
        """Add the remote to the config entry and dismiss the issue."""
        entry = self.hass.config_entries.async_entries(DOMAIN)[0]
        current = list(entry.data.get("remote_entities", []))

        if self._entity_id not in current:
            current.append(self._entity_id)
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, "remote_entities": current}
            )

        ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)

        # Trigger a rescan so buttons appear immediately.
        from . import async_scan_remote_commands

        await async_scan_remote_commands(self.hass, entry, remote_entity_ids=[self._entity_id])

        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a repair flow for the given issue."""
    entity_id = data["entity_id"] if data else issue_id.removeprefix("new_remote_")
    return AddRemoteRepairFlow(entity_id)
