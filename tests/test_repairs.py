"""Tests for the repair flow that adds a new remote."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.remote_buttons.const import DOMAIN
from custom_components.remote_buttons.repairs import AddRemoteRepairFlow, async_create_fix_flow
from tests.conftest import make_entry, setup_remote


async def test_create_fix_flow_uses_data(hass: HomeAssistant) -> None:
    """async_create_fix_flow extracts entity_id and name from issue data."""
    flow = await async_create_fix_flow(
        hass,
        issue_id="new_remote_remote.bedroom",
        data={"entity_id": "remote.bedroom", "name": "Bedroom Remote"},
    )
    assert isinstance(flow, AddRemoteRepairFlow)
    assert flow._entity_id == "remote.bedroom"
    assert flow._name == "Bedroom Remote"


async def test_create_fix_flow_fallback_without_data(hass: HomeAssistant) -> None:
    """async_create_fix_flow falls back to parsing issue_id and registry lookup if data is None."""
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")
    flow = await async_create_fix_flow(
        hass,
        issue_id="new_remote_remote.bedroom",
        data=None,
    )
    assert isinstance(flow, AddRemoteRepairFlow)
    assert flow._entity_id == "remote.bedroom"
    assert flow._name == "remote.bedroom"  # no name in registry, falls back to entity_id


async def test_repair_flow_confirm_adds_remote(hass: HomeAssistant) -> None:
    """Confirming the repair flow adds the remote and dismisses the issue."""
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")
    entry = make_entry(hass, ["remote.living_room"])

    # Create the repair issue.
    ir.async_create_issue(
        hass,
        DOMAIN,
        "new_remote_remote.bedroom",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_remote_found",
        translation_placeholders={"entity_id": "remote.bedroom", "name": "Bedroom Remote"},
        data={"entity_id": "remote.bedroom", "name": "Bedroom Remote"},
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom") is not None

    flow = AddRemoteRepairFlow("remote.bedroom", "Bedroom Remote")
    flow.hass = hass
    flow.issue_id = "new_remote_remote.bedroom"

    # Step 1: show the confirm form.
    result = await flow.async_step_init(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["description_placeholders"]["name"] == "Bedroom Remote"

    # Step 2: confirm.
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"

    # The remote should now be in the watched list.
    assert "remote.bedroom" in entry.data["remote_entities"]

    # The issue should be dismissed.
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom") is None


async def test_repair_flow_does_not_duplicate(hass: HomeAssistant) -> None:
    """If the remote is already watched, confirming doesn't add a duplicate."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    flow = AddRemoteRepairFlow("remote.living_room", "Living Room Remote")
    flow.hass = hass
    flow.issue_id = "new_remote_remote.living_room"

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={},
    ):
        result = await flow.async_step_init(user_input={})

    assert result["type"] == "create_entry"
    # Should still only appear once.
    assert entry.data["remote_entities"].count("remote.living_room") == 1
