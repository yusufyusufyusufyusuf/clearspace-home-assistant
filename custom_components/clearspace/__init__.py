"""ClearSpace integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ClearSpaceApi, ClearSpaceApiError, ClearSpaceAuthError
from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_ENTITY_PREFIX,
    CONF_IS_DEFAULT,
    CONF_REFRESH_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .helpers import entry_settings, entry_state_ids, resolve_entry_record

_LOGGER = logging.getLogger(__name__)
TARGET_FIELDS = {vol.Optional("entry_id"): cv.string, vol.Optional("entity_prefix"): cv.string}


class ClearSpaceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Refresh ClearSpace task and Space data."""

    def __init__(self, hass: HomeAssistant, api: ClearSpaceApi, refresh_interval: int) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=refresh_interval),
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


def _domain_store(hass: HomeAssistant) -> dict[str, Any]:
    """Return the integration store."""
    return hass.data.setdefault(DOMAIN, {"entries": {}, "services_registered": False})


async def _async_update_virtual_sensors(hass: HomeAssistant, record: dict[str, Any]) -> None:
    """Mirror the coordinator data into stable Home Assistant states."""
    data = record["coordinator"].data or {"tasks": [], "spaces": []}
    tasks = data.get("tasks", []) or []
    today = datetime.now(timezone.utc).date().isoformat()
    open_count = sum(1 for task in tasks if task.get("status") != "done")
    due_today_count = sum(1 for task in tasks if task.get("status") != "done" and task.get("due") == today)
    overdue_count = sum(
        1
        for task in tasks
        if task.get("status") != "done" and bool(task.get("due")) and task["due"] < today
    )

    settings = record["settings"]
    prefix = settings["entity_prefix"]
    names = settings["name"]
    state_ids = entry_state_ids(prefix)

    common_attrs = {
        "tasks": tasks,
        "open_tasks": open_count,
        "due_today_tasks": due_today_count,
        "overdue_tasks": overdue_count,
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "unit_of_measurement": "tasks",
        "icon": "mdi:checkbox-marked-circle-outline",
    }

    hass.states.async_set(
        state_ids["tasks"],
        open_count,
        {
            **common_attrs,
            "friendly_name": f"{names} Tasks",
        },
    )
    hass.states.async_set(
        state_ids["open"],
        open_count,
        {
            "friendly_name": f"{names} Open Tasks",
            "unit_of_measurement": "tasks",
            "icon": "mdi:checkbox-marked-circle-outline",
            "tasks": tasks,
        },
    )
    hass.states.async_set(
        state_ids["due_today"],
        due_today_count,
        {
            "friendly_name": f"{names} Due Today",
            "unit_of_measurement": "tasks",
            "icon": "mdi:calendar-today",
            "tasks": tasks,
        },
    )
    hass.states.async_set(
        state_ids["overdue"],
        overdue_count,
        {
            "friendly_name": f"{names} Overdue",
            "unit_of_measurement": "tasks",
            "icon": "mdi:alert-circle",
            "tasks": tasks,
        },
    )


def _clear_virtual_sensors(hass: HomeAssistant, record: dict[str, Any]) -> None:
    """Remove virtual states for an unloaded entry."""
    for entity_id in entry_state_ids(record["settings"]["entity_prefix"]).values():
        remover = getattr(hass.states, "async_remove", None)
        if remover is not None:
            remover(entity_id)


def _resolve_record(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any] | None:
    """Resolve a target ClearSpace account for a service call."""
    store = _domain_store(hass)
    return resolve_entry_record(
        store,
        entry_id=call.data.get("entry_id"),
        entity_prefix=call.data.get("entity_prefix"),
    )


async def _register_services(hass: HomeAssistant) -> None:
    """Register the global ClearSpace services once."""

    async def create_task(call: ServiceCall) -> None:
        record = _resolve_record(hass, call)
        if record is None:
            raise HomeAssistantError("No ClearSpace accounts are configured")
        data = {key: value for key, value in call.data.items() if key not in {"entry_id", "entity_prefix"} and value is not None}
        if "space_id" in data:
            data["spaceId"] = data.pop("space_id")
        await record["api"].create_task(data)
        await record["coordinator"].async_request_refresh()

    async def complete_task(call: ServiceCall) -> None:
        record = _resolve_record(hass, call)
        if record is None:
            raise HomeAssistantError("No ClearSpace accounts are configured")
        await record["api"].update_task(call.data["task_id"], {"status": "done"})
        await record["coordinator"].async_request_refresh()

    async def delete_task(call: ServiceCall) -> None:
        record = _resolve_record(hass, call)
        if record is None:
            raise HomeAssistantError("No ClearSpace accounts are configured")
        await record["api"].delete_task(call.data["task_id"])
        await record["coordinator"].async_request_refresh()

    async def refresh(call: ServiceCall) -> None:
        record = _resolve_record(hass, call)
        if record is None:
            raise HomeAssistantError("No ClearSpace accounts are configured")
        await record["coordinator"].async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        "create_task",
        create_task,
        schema=vol.Schema(
            {
                **TARGET_FIELDS,
                vol.Required("name"): cv.string,
                vol.Optional("due"): cv.string,
                vol.Optional("priority", default="medium"): vol.In(["low", "medium", "high", "urgent"]),
                vol.Optional("space_id"): cv.string,
                vol.Optional("description"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "complete_task",
        complete_task,
        schema=vol.Schema({**TARGET_FIELDS, vol.Required("task_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "delete_task",
        delete_task,
        schema=vol.Schema({**TARGET_FIELDS, vol.Required("task_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "refresh",
        refresh,
        schema=vol.Schema(TARGET_FIELDS),
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ClearSpace component."""
    store = _domain_store(hass)
    if not store["services_registered"]:
        await _register_services(hass)
        store["services_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ClearSpace from a config entry."""
    settings = entry_settings(entry)
    _LOGGER.debug("Setting up ClearSpace entry %s (%s)", entry.entry_id, settings["entity_prefix"])

    api = ClearSpaceApi(async_get_clientsession(hass), settings["api_url"], settings["api_token"])
    coordinator = ClearSpaceCoordinator(hass, api, settings["refresh_interval"])
    record = {
        "entry": entry,
        "api": api,
        "coordinator": coordinator,
        "settings": settings,
        "entity_prefix": settings["entity_prefix"],
        "is_default": settings["is_default"],
    }
    store = _domain_store(hass)
    store["entries"][entry.entry_id] = record

    async def _async_entry_updated(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        _LOGGER.error("ClearSpace authentication failed; creating entities with empty data")
        coordinator.data = {"tasks": [], "spaces": []}
    except Exception as err:
        _LOGGER.error("ClearSpace initial refresh failed: %s; creating entities with empty data", err)
        coordinator.data = {"tasks": [], "spaces": []}

    await _async_update_virtual_sensors(hass, record)
    coordinator.async_add_listener(lambda: hass.async_create_task(_async_update_virtual_sensors(hass, record)))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("ClearSpace platforms setup complete for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        store = _domain_store(hass)
        record = store["entries"].pop(entry.entry_id, None)
        if record is not None:
            _clear_virtual_sensors(hass, record)
    return unloaded
