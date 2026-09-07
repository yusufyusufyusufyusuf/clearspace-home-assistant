"""Config flow for ClearSpace."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ClearSpaceApi, ClearSpaceApiError, ClearSpaceAuthError
from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_ENTITY_PREFIX,
    CONF_IS_DEFAULT,
    CONF_REFRESH_INTERVAL,
    DEFAULT_API_URL,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
)
from .helpers import entry_settings, unique_entity_prefix


class ClearSpaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure ClearSpace through the Home Assistant UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial configuration form."""
        errors: dict[str, str] = {}
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        if user_input is not None:
            api = ClearSpaceApi(
                async_get_clientsession(self.hass),
                user_input[CONF_API_URL],
                user_input[CONF_API_TOKEN],
            )
            try:
                await api.tasks()
            except ClearSpaceAuthError:
                errors["base"] = "invalid_auth"
            except ClearSpaceApiError:
                errors["base"] = "cannot_connect"
            else:
                unique_id = hashlib.sha256(
                    f"{user_input[CONF_API_URL].rstrip('/')}/{user_input[CONF_API_TOKEN]}".encode()
                ).hexdigest()[:16]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                desired_prefix = user_input.get(CONF_ENTITY_PREFIX) or user_input[CONF_NAME]
                entity_prefix = unique_entity_prefix(desired_prefix, list(existing_entries))
                options = {
                    CONF_ENTITY_PREFIX: entity_prefix,
                    CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL),
                    CONF_IS_DEFAULT: user_input.get(CONF_IS_DEFAULT, not existing_entries),
                }
                data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    CONF_API_URL: user_input[CONF_API_URL],
                }
                return self.async_create_entry(title=user_input[CONF_NAME], data=data, options=options)

        default_name = "ClearSpace"
        default_prefix = unique_entity_prefix(default_name, list(existing_entries))
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Required(CONF_API_TOKEN): str,
                vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
                vol.Optional(CONF_ENTITY_PREFIX, default=default_prefix): str,
                vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_REFRESH_INTERVAL): vol.All(
                    int, vol.Range(min=15, max=3600)
                ),
                vol.Optional(CONF_IS_DEFAULT, default=not existing_entries): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class ClearSpaceOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ClearSpace options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options for an existing entry."""
        errors: dict[str, str] = {}
        settings = entry_settings(self.config_entry)
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        if user_input is not None:
            desired_prefix = user_input.get(CONF_ENTITY_PREFIX) or settings["entity_prefix"]
            entity_prefix = unique_entity_prefix(
                desired_prefix,
                list(existing_entries),
                current_entry_id=self.config_entry.entry_id,
            )
            options = {
                CONF_ENTITY_PREFIX: entity_prefix,
                CONF_REFRESH_INTERVAL: user_input[CONF_REFRESH_INTERVAL],
                CONF_IS_DEFAULT: user_input[CONF_IS_DEFAULT],
            }
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema(
            {
                vol.Optional(CONF_ENTITY_PREFIX, default=settings["entity_prefix"]): str,
                vol.Optional(
                    CONF_REFRESH_INTERVAL, default=settings["refresh_interval"]
                ): vol.All(int, vol.Range(min=15, max=3600)),
                vol.Optional(CONF_IS_DEFAULT, default=settings["is_default"]): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


async def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> ClearSpaceOptionsFlowHandler:
    """Return the options flow handler."""
    return ClearSpaceOptionsFlowHandler(config_entry)
