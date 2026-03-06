"""Diagnostics support for Remote Buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import RemoteButtonsConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RemoteButtonsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return {
        "remote_entities": entry.data.get("remote_entities", []),
        "known_commands": sorted(
            [{"remote": r, "subdevice": s, "command": c} for r, s, c in data.known_commands],
            key=lambda x: (x["remote"], x["subdevice"], x["command"]),
        ),
        "ir_subdevices": sorted(
            [{"remote": r, "subdevice": s} for r, s in data.ir_subdevices],
            key=lambda x: (x["remote"], x["subdevice"]),
        ),
        "ir_numbers_configured": sorted(
            [f"{r}_{s}" for r, s in data.ir_numbers],
        ),
    }
