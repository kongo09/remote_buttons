"""Tests for storage readers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.remote_buttons.storage import (
    BroadlinkStorageReader,
    TuyaLocalStorageReader,
)


async def test_broadlink_reader_returns_commands(hass: HomeAssistant) -> None:
    """Test BroadlinkStorageReader loads commands from storage."""
    mock_data = {
        "TV": {"power": "base64code1", "mute": "base64code2"},
        "AC": {"cool": "base64code3"},
    }
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value=mock_data,
    ):
        reader = BroadlinkStorageReader()
        result = await reader.async_read_commands(hass, "test_uid")

    assert "TV" in result
    assert result["TV"]["power"] == "base64code1"
    assert "AC" in result


async def test_broadlink_reader_returns_empty_on_missing(hass: HomeAssistant) -> None:
    """Test BroadlinkStorageReader returns empty dict when no storage exists."""
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value=None,
    ):
        reader = BroadlinkStorageReader()
        result = await reader.async_read_commands(hass, "missing_uid")

    assert result == {}


async def test_tuya_local_reader_returns_commands(hass: HomeAssistant) -> None:
    """Test TuyaLocalStorageReader loads commands from storage."""
    mock_data = {
        "Fan": {"speed1": "code1", "speed2": "code2"},
    }
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value=mock_data,
    ):
        reader = TuyaLocalStorageReader()
        result = await reader.async_read_commands(hass, "tuya_uid")

    assert "Fan" in result
    assert result["Fan"]["speed1"] == "code1"
