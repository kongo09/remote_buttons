"""Tests for RemoteCommandNumber."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTime

from custom_components.remote_buttons.const import (
    DEFAULT_IR_DELAY,
    DEFAULT_IR_REPEATS,
    DOMAIN,
)
from custom_components.remote_buttons.number import create_ir_number_pair


def test_number_unique_id() -> None:
    """Test that unique IDs follow the expected pattern."""
    delay, repeats = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )
    assert delay.unique_id == "remote_buttons_remote.living_room_TV_ir_delay_secs"
    assert repeats.unique_id == "remote_buttons_remote.living_room_TV_ir_num_repeats"


def test_number_device_info() -> None:
    """Test device info links to same subdevice as buttons."""
    delay, repeats = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )
    for entity in (delay, repeats):
        info = entity.device_info
        assert (DOMAIN, "remote.living_room_TV") in info["identifiers"]
        assert info["via_device"] == ("broadlink", "abc123")


def test_number_defaults() -> None:
    """Test default values for delay and repeats."""
    delay, repeats = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )
    assert delay.native_value == DEFAULT_IR_DELAY
    assert repeats.native_value == DEFAULT_IR_REPEATS


def test_number_attributes() -> None:
    """Test entity category, mode, and ranges."""
    delay, repeats = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )

    # Both should be CONFIG category and BOX mode.
    for entity in (delay, repeats):
        assert entity.entity_category == EntityCategory.CONFIG
        assert entity.mode == NumberMode.BOX

    # Delay ranges.
    assert delay.native_min_value == 0.0
    assert delay.native_max_value == 10.0
    assert delay.native_step == 0.1
    assert delay.native_unit_of_measurement == UnitOfTime.SECONDS
    assert delay.translation_key == "ir_delay"

    # Repeats ranges.
    assert repeats.native_min_value == 1.0
    assert repeats.native_max_value == 20.0
    assert repeats.native_step == 1.0
    assert repeats.native_unit_of_measurement is None
    assert repeats.translation_key == "ir_repeat"


async def test_number_set_native_value() -> None:
    """Test that setting a value updates the attribute and writes state."""
    delay, _ = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )
    delay.async_write_ha_state = MagicMock()

    await delay.async_set_native_value(2.5)
    assert delay.native_value == 2.5
    delay.async_write_ha_state.assert_called_once()


async def test_number_restores_last_state() -> None:
    """Test that the number restores its value from the last known state."""
    delay, _ = create_ir_number_pair(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
    )

    last_state = MagicMock()
    last_state.state = "3.0"
    delay.async_get_last_state = AsyncMock(return_value=last_state)

    with patch.object(type(delay).__mro__[2], "async_added_to_hass", new_callable=AsyncMock):
        await delay.async_added_to_hass()

    assert delay.native_value == 3.0
