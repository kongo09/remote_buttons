"""Tests for integration setup and scan logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_buttons import (
    _make_service_listener,
    async_scan_remote_commands,
)
from custom_components.remote_buttons.const import DOMAIN


def _setup_remote(
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


def _make_entry(hass: HomeAssistant, watched: list[str]) -> MockConfigEntry:
    """Create and register our integration's config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={"remote_entities": watched})
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "known_commands": set(),
        "async_add_entities": MagicMock(),
        "scan_unsub": None,
    }
    return entry


async def test_scan_creates_buttons(hass: HomeAssistant) -> None:
    """New commands in storage → buttons are created."""
    _setup_remote(hass)
    entry = _make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1", "mute": "code2"}},
    ):
        await async_scan_remote_commands(hass, entry)

    add = hass.data[DOMAIN][entry.entry_id]["async_add_entities"]
    add.assert_called_once()
    buttons = add.call_args[0][0]
    assert len(buttons) == 2
    names = {b.name for b in buttons}
    assert names == {"TV mute", "TV power"}


async def test_scan_removes_buttons(hass: HomeAssistant) -> None:
    """Commands gone from storage → entities are removed from registry."""
    _setup_remote(hass)
    entry = _make_entry(hass, ["remote.living_room"])

    # Pretend we already know about two commands.
    data = hass.data[DOMAIN][entry.entry_id]
    data["known_commands"] = {
        ("remote.living_room", "TV", "power"),
        ("remote.living_room", "TV", "mute"),
    }

    # Register button entities in the entity registry so removal works.
    entity_reg = er.async_get(hass)
    our_entry = MockConfigEntry(domain=DOMAIN)
    our_entry.add_to_hass(hass)
    for cmd in ("power", "mute"):
        entity_reg.async_get_or_create(
            Platform.BUTTON,
            DOMAIN,
            f"remote_buttons_remote.living_room_TV_{cmd}",
            config_entry=our_entry,
        )

    # Storage now returns empty → both commands should be removed.
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={},
    ):
        await async_scan_remote_commands(hass, entry)

    assert data["known_commands"] == set()
    # Verify entities were removed.
    for cmd in ("power", "mute"):
        uid = f"remote_buttons_remote.living_room_TV_{cmd}"
        assert entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid) is None


async def test_scan_no_change(hass: HomeAssistant) -> None:
    """Same commands in storage → no add/remove calls."""
    _setup_remote(hass)
    entry = _make_entry(hass, ["remote.living_room"])

    data = hass.data[DOMAIN][entry.entry_id]
    data["known_commands"] = {("remote.living_room", "TV", "power")}

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1"}},
    ):
        await async_scan_remote_commands(hass, entry)

    add = data["async_add_entities"]
    add.assert_not_called()
    assert data["known_commands"] == {("remote.living_room", "TV", "power")}


async def test_scan_skips_unknown_platform(hass: HomeAssistant) -> None:
    """Remotes from unsupported platforms are silently skipped."""
    _setup_remote(hass, platform="zigbee", device_identifier="zb123")
    entry = _make_entry(hass, ["remote.living_room"])

    await async_scan_remote_commands(hass, entry)

    add = hass.data[DOMAIN][entry.entry_id]["async_add_entities"]
    add.assert_not_called()


async def test_service_listener_triggers_scan(hass: HomeAssistant) -> None:
    """learn_command event for a watched remote → scan is scheduled."""
    entry = _make_entry(hass, ["remote.living_room"])
    listener = _make_service_listener(hass, entry)

    with patch("custom_components.remote_buttons._schedule_scan") as mock_schedule:
        listener(
            MagicMock(
                data={
                    "domain": "remote",
                    "service": "learn_command",
                    "service_data": {"entity_id": "remote.living_room"},
                }
            )
        )
        mock_schedule.assert_called_once()


async def test_service_listener_ignores_unwatched(hass: HomeAssistant) -> None:
    """learn_command for an unwatched remote → no scan."""
    entry = _make_entry(hass, ["remote.living_room"])
    listener = _make_service_listener(hass, entry)

    with patch("custom_components.remote_buttons._schedule_scan") as mock_schedule:
        listener(
            MagicMock(
                data={
                    "domain": "remote",
                    "service": "learn_command",
                    "service_data": {"entity_id": "remote.bedroom"},
                }
            )
        )
        mock_schedule.assert_not_called()


async def test_service_listener_ignores_other_services(hass: HomeAssistant) -> None:
    """Non-learn/delete service → no scan."""
    entry = _make_entry(hass, ["remote.living_room"])
    listener = _make_service_listener(hass, entry)

    with patch("custom_components.remote_buttons._schedule_scan") as mock_schedule:
        listener(
            MagicMock(
                data={
                    "domain": "remote",
                    "service": "send_command",
                    "service_data": {"entity_id": "remote.living_room"},
                }
            )
        )
        mock_schedule.assert_not_called()
