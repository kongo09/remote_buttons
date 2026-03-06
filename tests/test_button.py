"""Tests for RemoteCommandButton."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.remote_buttons import RemoteButtonsData
from custom_components.remote_buttons.button import RemoteCommandButton
from custom_components.remote_buttons.const import DOMAIN


def test_button_unique_id() -> None:
    """Test that the unique ID is deterministic."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    assert button.unique_id == "remote_buttons_remote.living_room_TV_power"


def test_button_translation_key() -> None:
    """Test button uses translation_key with command_name placeholder."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    assert button.translation_key == "remote_command"
    assert button.translation_placeholders == {"command_name": "power"}


def test_button_device_info() -> None:
    """Test device info links via via_device."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    info = button.device_info
    assert (DOMAIN, "remote.living_room_TV") in info["identifiers"]
    assert info["via_device"] == ("broadlink", "abc123")


async def test_button_press_calls_send_command(hass: HomeAssistant) -> None:
    """Test pressing the button calls remote.send_command."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    button.hass = hass

    mock_call = AsyncMock()
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        mock_call,
    ):
        await button.async_press()

    mock_call.assert_called_once_with(
        "remote",
        "send_command",
        {
            "entity_id": "remote.living_room",
            "device": "TV",
            "command": ["power"],
        },
        blocking=True,
    )


async def test_button_press_uses_ir_numbers(hass: HomeAssistant) -> None:
    """Test pressing the button passes delay/repeats from IR number entities."""
    delay_entity = MagicMock(native_value=1.5)
    repeats_entity = MagicMock(native_value=3.0)
    data = RemoteButtonsData(
        ir_numbers={
            ("remote.living_room", "TV"): (delay_entity, repeats_entity),
        },
    )
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
        runtime_data=data,
    )
    button.hass = hass

    mock_call = AsyncMock()
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        mock_call,
    ):
        await button.async_press()

    mock_call.assert_called_once_with(
        "remote",
        "send_command",
        {
            "entity_id": "remote.living_room",
            "device": "TV",
            "command": ["power"],
            "delay_secs": 1.5,
            "num_repeats": 3,
        },
        blocking=True,
    )


async def test_button_press_without_ir_numbers(hass: HomeAssistant) -> None:
    """Test pressing the button works without IR numbers (RF or no config)."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
        runtime_data=RemoteButtonsData(),
    )
    button.hass = hass

    mock_call = AsyncMock()
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        mock_call,
    ):
        await button.async_press()

    # No delay_secs or num_repeats in the call.
    call_data = mock_call.call_args[0][2]
    assert "delay_secs" not in call_data
    assert "num_repeats" not in call_data


async def test_button_press_raises_translated_error(hass: HomeAssistant) -> None:
    """Test that a service call failure raises HomeAssistantError with translation."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    button.hass = hass

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            AsyncMock(side_effect=Exception("connection lost")),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await button.async_press()

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_placeholders["command"] == "power"
    assert exc_info.value.translation_placeholders["remote"] == "remote.living_room"
