"""Config flow for ClearSpace."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ClearSpaceApi, ClearSpaceApiError, ClearSpaceAuthError
from .const import CONF_API_TOKEN, CONF_API_URL, DEFAULT_API_URL, DOMAIN


class ClearSpaceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure ClearSpace through the Home Assistant UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
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
                await self.async_set_unique_id("clearspace_account")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "ClearSpace"), data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="ClearSpace"): str,
                vol.Required(CONF_API_TOKEN): str,
                vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

