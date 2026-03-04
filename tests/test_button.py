"""Tests for RemoteCommandButton."""

from __future__ import annotations

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


def test_button_name_with_subdevice() -> None:
    """Test button name includes subdevice."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="TV",
        command_name="power",
    )
    assert button.name == "TV power"


def test_button_name_without_subdevice() -> None:
    """Test button name without subdevice."""
    button = RemoteCommandButton(
        remote_entity_id="remote.living_room",
        remote_device_id="abc123",
        remote_domain="broadlink",
        subdevice="",
        command_name="power",
    )
    assert button.name == "power"


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
