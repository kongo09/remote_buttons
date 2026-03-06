"""Tests for diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.remote_buttons.diagnostics import (
    async_get_config_entry_diagnostics,
)
from tests.conftest import make_entry


async def test_diagnostics_empty(hass: HomeAssistant) -> None:
    """Test diagnostics with no known commands."""
    entry = make_entry(hass, ["remote.living_room"])

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["remote_entities"] == ["remote.living_room"]
    assert result["known_commands"] == []
    assert result["ir_subdevices"] == []
    assert result["ir_numbers_configured"] == []


async def test_diagnostics_with_data(hass: HomeAssistant) -> None:
    """Test diagnostics with commands, IR subdevices, and numbers."""
    entry = make_entry(hass, ["remote.living_room"])

    data = entry.runtime_data
    data.known_commands = {
        ("remote.living_room", "TV", "power"),
        ("remote.living_room", "TV", "mute"),
        ("remote.living_room", "AC", "cool"),
    }
    data.ir_subdevices = {("remote.living_room", "TV")}
    data.ir_numbers = {("remote.living_room", "TV"): (MagicMock(), MagicMock())}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["remote_entities"] == ["remote.living_room"]
    assert len(result["known_commands"]) == 3
    # Sorted by remote, subdevice, command.
    assert result["known_commands"][0] == {
        "remote": "remote.living_room",
        "subdevice": "AC",
        "command": "cool",
    }
    assert result["ir_subdevices"] == [
        {"remote": "remote.living_room", "subdevice": "TV"},
    ]
    assert result["ir_numbers_configured"] == ["remote.living_room_TV"]
