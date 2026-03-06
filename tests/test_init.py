"""Tests for integration setup and scan logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_buttons import (
    _async_options_updated,
    _async_scan_remote_commands_locked,
    _make_entity_registry_listener,
    _make_service_listener,
    async_scan_remote_commands,
)
from custom_components.remote_buttons.const import DOMAIN
from tests.conftest import make_entry, setup_remote


async def test_scan_creates_buttons(hass: HomeAssistant) -> None:
    """New commands in storage → buttons are created."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1", "mute": "code2"}},
    ):
        await async_scan_remote_commands(hass, entry)

    add = entry.runtime_data.async_add_entities
    add.assert_called_once()
    buttons = add.call_args[0][0]
    assert len(buttons) == 2
    names = {b.translation_placeholders["command_name"] for b in buttons}
    assert names == {"mute", "power"}


async def test_scan_removes_buttons(hass: HomeAssistant) -> None:
    """Commands gone from storage → entities are removed from registry."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    # Pretend we already know about two commands.
    data = entry.runtime_data
    data.known_commands = {
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

    assert data.known_commands == set()
    # Verify entities were removed.
    for cmd in ("power", "mute"):
        uid = f"remote_buttons_remote.living_room_TV_{cmd}"
        assert entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid) is None


async def test_scan_no_change(hass: HomeAssistant) -> None:
    """Same commands in storage → no add/remove calls."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    data = entry.runtime_data
    data.known_commands = {("remote.living_room", "TV", "power")}

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1"}},
    ):
        await async_scan_remote_commands(hass, entry)

    add = data.async_add_entities
    add.assert_not_called()
    assert data.known_commands == {("remote.living_room", "TV", "power")}


async def test_scan_skips_unknown_platform(hass: HomeAssistant) -> None:
    """Remotes from unsupported platforms are silently skipped."""
    setup_remote(hass, platform="zigbee", device_identifier="zb123")
    entry = make_entry(hass, ["remote.living_room"])

    await async_scan_remote_commands(hass, entry)

    add = entry.runtime_data.async_add_entities
    add.assert_not_called()


async def test_service_listener_triggers_scan(hass: HomeAssistant) -> None:
    """learn_command event for a watched remote → scan is scheduled."""
    entry = make_entry(hass, ["remote.living_room"])
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
    entry = make_entry(hass, ["remote.living_room"])
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
    entry = make_entry(hass, ["remote.living_room"])
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


async def test_entity_registry_listener_creates_issue(hass: HomeAssistant) -> None:
    """New compatible remote entity → repair issue is created."""
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")
    entry = make_entry(hass, ["remote.living_room"])
    listener = _make_entity_registry_listener(hass, entry)

    listener(MagicMock(data={"action": "create", "entity_id": "remote.bedroom"}))

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_entity_registry_listener_ignores_unsupported_platform(hass: HomeAssistant) -> None:
    """New remote on unsupported platform → no issue."""
    setup_remote(hass, entity_id="remote.bedroom", platform="zigbee", device_identifier="zb1")
    entry = make_entry(hass, ["remote.living_room"])
    listener = _make_entity_registry_listener(hass, entry)

    listener(MagicMock(data={"action": "create", "entity_id": "remote.bedroom"}))

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom")
    assert issue is None


async def test_entity_registry_listener_ignores_watched(hass: HomeAssistant) -> None:
    """Already-watched remote → no issue."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])
    listener = _make_entity_registry_listener(hass, entry)

    listener(MagicMock(data={"action": "create", "entity_id": "remote.living_room"}))

    issue = ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.living_room")
    assert issue is None


async def test_options_update_dismisses_issue(hass: HomeAssistant) -> None:
    """Adding a remote via options → its repair issue is dismissed."""
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")
    entry = make_entry(hass, ["remote.living_room"])

    # Simulate the issue existing.
    ir.async_create_issue(
        hass,
        DOMAIN,
        "new_remote_remote.bedroom",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_remote_found",
        translation_placeholders={"entity_id": "remote.bedroom"},
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom") is not None

    # Update the entry data to include the new remote.
    new_data = {"remote_entities": ["remote.living_room", "remote.bedroom"]}
    hass.config_entries.async_update_entry(entry, data=new_data)
    await _async_options_updated(hass, entry)

    assert ir.async_get(hass).async_get_issue(DOMAIN, "new_remote_remote.bedroom") is None


async def test_removed_remote_cleans_up_buttons(hass: HomeAssistant) -> None:
    """Watched remote removed → button entities and devices are cleaned up."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    # Simulate known commands and registered button entities.
    data = entry.runtime_data
    data.known_commands = {
        ("remote.living_room", "TV", "power"),
        ("remote.living_room", "TV", "mute"),
    }

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    # Create the subdevice device entry.
    subdevice_dev = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "remote.living_room_TV")},
        name="TV",
    )

    # Create button entities linked to that device.
    for cmd in ("power", "mute"):
        entity_reg.async_get_or_create(
            Platform.BUTTON,
            DOMAIN,
            f"remote_buttons_remote.living_room_TV_{cmd}",
            config_entry=entry,
            device_id=subdevice_dev.id,
        )

    listener = _make_entity_registry_listener(hass, entry)
    listener(MagicMock(data={"action": "remove", "entity_id": "remote.living_room"}))

    # Button entities should be removed.
    for cmd in ("power", "mute"):
        uid = f"remote_buttons_remote.living_room_TV_{cmd}"
        assert entity_reg.async_get_entity_id(Platform.BUTTON, DOMAIN, uid) is None

    # Subdevice device should be removed (no remaining entities).
    assert device_reg.async_get_device(identifiers={(DOMAIN, "remote.living_room_TV")}) is None

    # Known commands should be empty.
    assert data.known_commands == set()

    # Remote should be removed from the watched list.
    assert "remote.living_room" not in entry.data["remote_entities"]


async def test_removed_unwatched_remote_is_ignored(hass: HomeAssistant) -> None:
    """Removing a remote we don't watch → no action."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    data = entry.runtime_data
    data.known_commands = {("remote.living_room", "TV", "power")}

    listener = _make_entity_registry_listener(hass, entry)
    listener(MagicMock(data={"action": "remove", "entity_id": "remote.bedroom"}))

    # Nothing should change.
    assert data.known_commands == {("remote.living_room", "TV", "power")}
    assert "remote.living_room" in entry.data["remote_entities"]


async def test_scan_creates_numbers_for_ir_subdevice(hass: HomeAssistant) -> None:
    """IR codes in storage → number entities are created for the subdevice."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "ir_code_1", "mute": "ir_code_2"}},
    ):
        await async_scan_remote_commands(hass, entry)

    data = entry.runtime_data
    add_numbers = data.async_add_number_entities
    add_numbers.assert_called_once()
    numbers = add_numbers.call_args[0][0]
    assert len(numbers) == 2
    keys = {n.translation_key for n in numbers}
    assert keys == {"ir_delay", "ir_repeat"}

    # ir_numbers should have the pair.
    assert ("remote.living_room", "TV") in data.ir_numbers

    # ir_subdevices should track it.
    assert ("remote.living_room", "TV") in data.ir_subdevices


async def test_scan_skips_numbers_for_rf_subdevice(hass: HomeAssistant) -> None:
    """RF-only codes in storage → no number entities created."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"Garage": {"open": "rf:code1", "close": "rf:code2"}},
    ):
        await async_scan_remote_commands(hass, entry)

    data = entry.runtime_data
    add_numbers = data.async_add_number_entities
    add_numbers.assert_not_called()

    # Buttons should still be created.
    add_buttons = data.async_add_entities
    add_buttons.assert_called_once()
    buttons = add_buttons.call_args[0][0]
    assert len(buttons) == 2


async def test_scan_removes_numbers_when_no_ir_left(hass: HomeAssistant) -> None:
    """Last IR code deleted from subdevice → number entities removed."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    data = entry.runtime_data
    data.known_commands = {("remote.living_room", "TV", "power")}
    data.ir_subdevices = {("remote.living_room", "TV")}
    data.ir_numbers = {("remote.living_room", "TV"): (MagicMock(), MagicMock())}

    # Register number entities in the entity registry so removal works.
    entity_reg = er.async_get(hass)
    our_entry = MockConfigEntry(domain=DOMAIN)
    our_entry.add_to_hass(hass)
    for param in ("delay_secs", "num_repeats"):
        entity_reg.async_get_or_create(
            Platform.NUMBER,
            DOMAIN,
            f"remote_buttons_remote.living_room_TV_ir_{param}",
            config_entry=our_entry,
        )

    # Storage now returns empty → IR codes gone.
    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={},
    ):
        await async_scan_remote_commands(hass, entry)

    # Number entities should be removed.
    for param in ("delay_secs", "num_repeats"):
        uid = f"remote_buttons_remote.living_room_TV_ir_{param}"
        assert entity_reg.async_get_entity_id(Platform.NUMBER, DOMAIN, uid) is None

    # ir_numbers and ir_subdevices should be cleared.
    assert ("remote.living_room", "TV") not in data.ir_numbers
    assert ("remote.living_room", "TV") not in data.ir_subdevices


async def test_removed_remote_cleans_up_numbers(hass: HomeAssistant) -> None:
    """Watched remote removed → IR number entities are also cleaned up."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    data = entry.runtime_data
    data.known_commands = {("remote.living_room", "TV", "power")}
    data.ir_subdevices = {("remote.living_room", "TV")}
    data.ir_numbers = {("remote.living_room", "TV"): (MagicMock(), MagicMock())}

    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    # Create subdevice device entry.
    subdevice_dev = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "remote.living_room_TV")},
        name="TV",
    )

    # Create button and number entities.
    entity_reg.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        "remote_buttons_remote.living_room_TV_power",
        config_entry=entry,
        device_id=subdevice_dev.id,
    )
    for param in ("delay_secs", "num_repeats"):
        entity_reg.async_get_or_create(
            Platform.NUMBER,
            DOMAIN,
            f"remote_buttons_remote.living_room_TV_ir_{param}",
            config_entry=entry,
            device_id=subdevice_dev.id,
        )

    listener = _make_entity_registry_listener(hass, entry)
    listener(MagicMock(data={"action": "remove", "entity_id": "remote.living_room"}))

    # Number entities should be removed.
    for param in ("delay_secs", "num_repeats"):
        uid = f"remote_buttons_remote.living_room_TV_ir_{param}"
        assert entity_reg.async_get_entity_id(Platform.NUMBER, DOMAIN, uid) is None

    # ir_numbers and ir_subdevices should be cleared.
    assert ("remote.living_room", "TV") not in data.ir_numbers
    assert ("remote.living_room", "TV") not in data.ir_subdevices


async def test_scan_mixed_ir_rf_subdevice(hass: HomeAssistant) -> None:
    """Subdevice with both IR and RF codes → number entities created."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "ir_code", "rf_cmd": "rf:code"}},
    ):
        await async_scan_remote_commands(hass, entry)

    data = entry.runtime_data
    # Should create numbers because there's at least one IR code.
    add_numbers = data.async_add_number_entities
    add_numbers.assert_called_once()
    assert ("remote.living_room", "TV") in data.ir_subdevices


async def test_concurrent_scans_are_serialized(hass: HomeAssistant) -> None:
    """Two concurrent scans don't interleave — the lock serializes them."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    call_count = 0
    original = _async_scan_remote_commands_locked

    async def _counting_scan(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await original(*args, **kwargs)

    with (
        patch(
            "custom_components.remote_buttons.storage.Store.async_load",
            new_callable=AsyncMock,
            return_value={"TV": {"power": "code1"}},
        ),
        patch(
            "custom_components.remote_buttons._async_scan_remote_commands_locked",
            side_effect=_counting_scan,
        ),
    ):
        import asyncio

        await asyncio.gather(
            async_scan_remote_commands(hass, entry),
            async_scan_remote_commands(hass, entry),
        )

    # Both should have run (serialized, not skipped).
    assert call_count == 2


async def test_scan_handles_storage_read_error(hass: HomeAssistant) -> None:
    """Storage read failure → remote is skipped, no crash."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        side_effect=OSError("disk error"),
    ):
        await async_scan_remote_commands(hass, entry)

    # No buttons created, no crash.
    data = entry.runtime_data
    data.async_add_entities.assert_not_called()
    assert data.known_commands == set()


async def test_scan_handles_malformed_storage(hass: HomeAssistant) -> None:
    """Malformed storage data (not a dict) → remote is skipped gracefully."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value="not a dict",
    ):
        await async_scan_remote_commands(hass, entry)

    data = entry.runtime_data
    data.async_add_entities.assert_not_called()
    assert data.known_commands == set()


async def test_scan_skips_malformed_subdevice(hass: HomeAssistant) -> None:
    """Subdevice with non-dict commands → skipped, others still processed."""
    setup_remote(hass)
    entry = make_entry(hass, ["remote.living_room"])

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1"}, "bad": "not_a_dict"},
    ):
        await async_scan_remote_commands(hass, entry)

    data = entry.runtime_data
    add = data.async_add_entities
    add.assert_called_once()
    buttons = add.call_args[0][0]
    # Only the valid TV subdevice should produce a button.
    assert len(buttons) == 1
    assert buttons[0].translation_placeholders["command_name"] == "power"


async def test_service_listener_handles_entity_id_list(hass: HomeAssistant) -> None:
    """Service event with entity_id as a list → scan triggered for watched remote."""
    entry = make_entry(hass, ["remote.living_room"])
    listener = _make_service_listener(hass, entry)

    with patch("custom_components.remote_buttons._schedule_scan") as mock_schedule:
        listener(
            MagicMock(
                data={
                    "domain": "remote",
                    "service": "learn_command",
                    "service_data": {
                        "entity_id": ["remote.living_room", "remote.bedroom"],
                    },
                }
            )
        )
        mock_schedule.assert_called_once()


async def test_service_listener_ignores_entity_id_list_unwatched(
    hass: HomeAssistant,
) -> None:
    """Service event with entity_id list of only unwatched remotes → no scan."""
    entry = make_entry(hass, ["remote.living_room"])
    listener = _make_service_listener(hass, entry)

    with patch("custom_components.remote_buttons._schedule_scan") as mock_schedule:
        listener(
            MagicMock(
                data={
                    "domain": "remote",
                    "service": "learn_command",
                    "service_data": {
                        "entity_id": ["remote.bedroom", "remote.kitchen"],
                    },
                }
            )
        )
        mock_schedule.assert_not_called()


async def test_targeted_scan_preserves_other_remotes(hass: HomeAssistant) -> None:
    """Targeted rescan for one remote doesn't affect another remote's known state."""
    setup_remote(hass)
    setup_remote(hass, entity_id="remote.bedroom", device_identifier="ff1122")
    entry = make_entry(hass, ["remote.living_room", "remote.bedroom"])

    data = entry.runtime_data
    data.known_commands = {
        ("remote.living_room", "TV", "power"),
        ("remote.bedroom", "Fan", "speed1"),
    }

    with patch(
        "custom_components.remote_buttons.storage.Store.async_load",
        new_callable=AsyncMock,
        return_value={"TV": {"power": "code1", "mute": "code2"}},
    ):
        await async_scan_remote_commands(hass, entry, remote_entity_ids=["remote.living_room"])

    # Bedroom commands should be untouched.
    assert ("remote.bedroom", "Fan", "speed1") in data.known_commands
    # Living room should have the new command.
    assert ("remote.living_room", "TV", "mute") in data.known_commands
    assert ("remote.living_room", "TV", "power") in data.known_commands
