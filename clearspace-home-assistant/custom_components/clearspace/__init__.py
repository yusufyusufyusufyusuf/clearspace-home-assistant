"""ClearSpace integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClearSpaceApi, ClearSpaceApiError, ClearSpaceAuthError
from .const import CONF_API_TOKEN, CONF_API_URL, DOMAIN, PLATFORMS


class ClearSpaceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh ClearSpace task and Space data."""

    def __init__(self, hass: HomeAssistant, api: ClearSpaceApi) -> None:
        super().__init__(hass, logger=__import__("logging").getLogger(__name__), name=DOMAIN, update_interval=timedelta(minutes=1))
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return {"tasks": await self.api.tasks(), "spaces": await self.api.spaces()}
        except ClearSpaceAuthError as error:
            raise ConfigEntryAuthFailed from error
        except ClearSpaceApiError as error:
            raise UpdateFailed(str(error)) from error


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = ClearSpaceApi(async_get_clientsession(hass), entry.data[CONF_API_URL], entry.data[CONF_API_TOKEN])
    coordinator = ClearSpaceCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def create_task(call: ServiceCall) -> None:
        data = {key: value for key, value in call.data.items() if value is not None}
        if "space_id" in data:
            data["spaceId"] = data.pop("space_id")
        await api.create_task(data)
        await coordinator.async_request_refresh()

    async def complete_task(call: ServiceCall) -> None:
        await api.update_task(call.data["task_id"], {"status": "done"})
        await coordinator.async_request_refresh()

    async def delete_task(call: ServiceCall) -> None:
        await api.delete_task(call.data["task_id"])
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, "create_task", create_task,
        schema=vol.Schema({vol.Required("name"): cv.string, vol.Optional("due"): cv.string, vol.Optional("priority", default="medium"): vol.In(["low", "medium", "high", "urgent"]), vol.Optional("space_id"): cv.string, vol.Optional("description"): cv.string}),
    )
    hass.services.async_register(DOMAIN, "complete_task", complete_task, schema=vol.Schema({vol.Required("task_id"): cv.string}))
    hass.services.async_register(DOMAIN, "delete_task", delete_task, schema=vol.Schema({vol.Required("task_id"): cv.string}))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for service in ("create_task", "complete_task", "delete_task"):
            hass.services.async_remove(DOMAIN, service)
    return unloaded
