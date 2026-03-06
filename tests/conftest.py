"""Shared fixtures for Remote Buttons tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_buttons import RemoteButtonsData
from custom_components.remote_buttons.const import DOMAIN


@pytest.fixture
def remote_entity_id() -> str:
    """Return a test remote entity ID."""
    return "remote.living_room"


def setup_remote(
    hass: HomeAssistant,
    entity_id: str = "remote.living_room",
    platform: str = "broadlink",
    device_identifier: str = "aabbccddeeff",
) -> None:
    """Register a fake remote entity and device in the HA registries."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    config_entry = MockConfigEntry(domain=platform)
    config_entry.add_to_hass(hass)

    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(platform, device_identifier)},
        name="Living Room Remote",
    )
    object_id = entity_id.split(".", 1)[1]
    entity_reg.async_get_or_create(
        "remote",
        platform,
        device_identifier,
        config_entry=config_entry,
        device_id=device.id,
        suggested_object_id=object_id,
    )


def make_entry(hass: HomeAssistant, watched: list[str]) -> MockConfigEntry:
    """Create and register our integration's config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={"remote_entities": watched})
    entry.add_to_hass(hass)
    data = RemoteButtonsData(
        async_add_entities=MagicMock(),
        async_add_number_entities=MagicMock(),
    )
    entry.runtime_data = data
    return entry
