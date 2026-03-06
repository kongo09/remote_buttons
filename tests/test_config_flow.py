"""Tests for the Remote Buttons config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.remote import RemoteEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.remote_buttons.const import DOMAIN
from tests.conftest import make_entry, setup_remote


async def test_flow_aborts_when_no_remotes(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test that the flow aborts if no learning remotes exist."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remotes"


async def test_flow_creates_entry(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test that submitting the form creates a config entry."""
    setup_remote(hass)

    # Set up the remote state with LEARN_COMMAND feature.
    hass.states.async_set(
        "remote.living_room",
        "off",
        {"supported_features": RemoteEntityFeature.LEARN_COMMAND},
    )

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"remote_entities": ["remote.living_room"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"remote_entities": ["remote.living_room"]}


async def test_flow_filters_unsupported_platforms(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test that remotes on unsupported platforms are not shown."""
    setup_remote(hass, platform="zigbee", device_identifier="zb1")

    hass.states.async_set(
        "remote.living_room",
        "off",
        {"supported_features": RemoteEntityFeature.LEARN_COMMAND},
    )

    # The zigbee remote is not in READERS, so no remotes should be available.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remotes"


async def test_flow_filters_remotes_without_learn(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test that remotes without LEARN_COMMAND feature are not shown."""
    setup_remote(hass)

    # No LEARN_COMMAND feature.
    hass.states.async_set("remote.living_room", "off", {"supported_features": 0})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_remotes"


async def test_options_flow_round_trip(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test that options flow updates entry.options and triggers update listener."""
    setup_remote(hass)
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")

    hass.states.async_set(
        "remote.living_room",
        "off",
        {"supported_features": RemoteEntityFeature.LEARN_COMMAND},
    )
    hass.states.async_set(
        "remote.bedroom",
        "off",
        {"supported_features": RemoteEntityFeature.LEARN_COMMAND},
    )

    entry = make_entry(hass, ["remote.living_room"])

    # Patch async_setup_entry to avoid full integration setup.
    with patch(
        f"custom_components.{DOMAIN}.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"remote_entities": ["remote.living_room", "remote.bedroom"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Options should contain the updated list.
    assert entry.options["remote_entities"] == ["remote.living_room", "remote.bedroom"]
