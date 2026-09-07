"""ClearSpace integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
import logging

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

_LOGGER = logging.getLogger(__name__)


class ClearSpaceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh ClearSpace task and Space data."""

    def __init__(self, hass: HomeAssistant, api: ClearSpaceApi) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            tasks = await self.api.tasks()
            spaces = await self.api.spaces()
            _LOGGER.debug("Fetched %d tasks and %d spaces", len(tasks), len(spaces))
            return {"tasks": tasks, "spaces": spaces}
        except ClearSpaceAuthError as error:
            raise ConfigEntryAuthFailed from error
        except ClearSpaceApiError as error:
            raise UpdateFailed(str(error)) from error


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ClearSpace component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ClearSpace from a config entry."""
    _LOGGER.debug("Setting up ClearSpace entry %s", entry.entry_id)
    _LOGGER.debug("Entry data keys: %s", list(entry.data.keys()) if entry.data else "None")

    if not entry.data:
        _LOGGER.warning("ClearSpace config entry has no data; using defaults and empty state")
        entry_data = {}
    else:
        entry_data = entry.data

    api = ClearSpaceApi(
        async_get_clientsession(hass),
        entry_data.get(CONF_API_URL, "https://clearspace-billing.yusuf-145.workers.dev"),
        entry_data.get(CONF_API_TOKEN, ""),
    )
    coordinator = ClearSpaceCoordinator(hass, api)

    async def async_update_virtual_sensors() -> None:
        data = coordinator.data or {"tasks": [], "spaces": []}
        tasks = data.get("tasks", []) or []
        from datetime import date as _date

        today = _date.today().isoformat()
        open_count = sum(1 for task in tasks if task.get("status") != "done")
        due_today_count = sum(1 for task in tasks if task.get("status") != "done" and task.get("due") == today)
        overdue_count = sum(
            1
            for task in tasks
            if task.get("status") != "done" and bool(task.get("due")) and task["due"] < today
        )

        common_attrs = {
            "tasks": tasks,
            "open_tasks": open_count,
            "due_today_tasks": due_today_count,
            "overdue_tasks": overdue_count,
            "unit_of_measurement": "tasks",
            "icon": "mdi:checkbox-marked-circle-outline",
        }

        hass.states.async_set(
            "sensor.clearspace_tasks",
            open_count,
            {
                **common_attrs,
                "friendly_name": "ClearSpace Tasks",
            },
        )
        hass.states.async_set(
            "sensor.clearspace_open",
            open_count,
            {
                "friendly_name": "Open Tasks",
                "unit_of_measurement": "tasks",
                "icon": "mdi:checkbox-marked-circle-outline",
                "tasks": tasks,
            },
        )
        hass.states.async_set(
            "sensor.clearspace_due_today",
            due_today_count,
            {
                "friendly_name": "Due Today",
                "unit_of_measurement": "tasks",
                "icon": "mdi:calendar-today",
                "tasks": tasks,
            },
        )
        hass.states.async_set(
            "sensor.clearspace_overdue",
            overdue_count,
            {
                "friendly_name": "Overdue",
                "unit_of_measurement": "tasks",
                "icon": "mdi:alert-circle",
                "tasks": tasks,
            },
        )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        _LOGGER.error("ClearSpace authentication failed; creating entities with empty data")
        coordinator.data = {"tasks": [], "spaces": []}
    except Exception as err:
        _LOGGER.error("ClearSpace initial refresh failed: %s; creating entities with empty data", err)
        coordinator.data = {"tasks": [], "spaces": []}

    await async_update_virtual_sensors()
    coordinator.async_add_listener(lambda: hass.async_create_task(async_update_virtual_sensors()))

    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.debug("ClearSpace coordinator stored for entry %s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("ClearSpace platforms setup complete for entry %s", entry.entry_id)

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
        DOMAIN,
        "create_task",
        create_task,
        schema=vol.Schema(
            {
                vol.Required("name"): cv.string,
                vol.Optional("due"): cv.string,
                vol.Optional("priority", default="medium"): vol.In(
                    ["low", "medium", "high", "urgent"]
                ),
                vol.Optional("space_id"): cv.string,
                vol.Optional("description"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "complete_task",
        complete_task,
        schema=vol.Schema({vol.Required("task_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "delete_task",
        delete_task,
        schema=vol.Schema({vol.Required("task_id"): cv.string}),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for service in ("create_task", "complete_task", "delete_task"):
            hass.services.async_remove(DOMAIN, service)
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
