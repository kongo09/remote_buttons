"""Config flow for Remote Buttons integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.remote import RemoteEntityFeature
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN

CONF_REMOTE_ENTITIES = "remote_entities"


class RemoteButtonsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remote Buttons."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step: select remote entities to watch."""
        if user_input is not None:
            return self.async_create_entry(
                title="Remote buttons",
                data={CONF_REMOTE_ENTITIES: user_input[CONF_REMOTE_ENTITIES]},
            )

        # Find all remote entities that support learn_command.
        remotes = _get_learning_remotes(self.hass)

        if not remotes:
            return self.async_abort(reason="no_remotes")

        schema = vol.Schema(
            {
                vol.Required(CONF_REMOTE_ENTITIES): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=eid, label=name) for eid, name in remotes.items()
                        ],
                        multiple=True,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return RemoteButtonsOptionsFlow(config_entry)


class RemoteButtonsOptionsFlow(OptionsFlow):
    """Handle options flow to add/remove watched remotes."""

    def __init__(self, config_entry) -> None:
        """Initialise options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_REMOTE_ENTITIES: user_input[CONF_REMOTE_ENTITIES]},
            )

        remotes = _get_learning_remotes(self.hass)
        current = self.config_entry.data.get(CONF_REMOTE_ENTITIES, [])

        schema = vol.Schema(
            {
                vol.Required(CONF_REMOTE_ENTITIES, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=eid, label=name) for eid, name in remotes.items()
                        ],
                        multiple=True,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _get_learning_remotes(hass) -> dict[str, str]:
    """Return {entity_id: friendly_name} for remotes that support learn_command."""
    registry = er.async_get(hass)
    remotes: dict[str, str] = {}

    for state in hass.states.async_all("remote"):
        entity_id = state.entity_id
        supported = state.attributes.get("supported_features", 0)

        has_learn = bool(supported & RemoteEntityFeature.LEARN_COMMAND)
        if has_learn:
            entry = registry.async_get(entity_id)
            name = (entry.name or entry.original_name) if entry else entity_id
            remotes[entity_id] = name or entity_id

    return remotes
