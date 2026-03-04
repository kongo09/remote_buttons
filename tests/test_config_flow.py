"""Tests for the Remote Buttons config flow."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.remote_buttons.const import DOMAIN


async def test_flow_aborts_when_no_remotes(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test that the flow aborts if no learning remotes exist."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remotes"
