"""ClearSpace task sensors."""

from __future__ import annotations

from datetime import date
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helpers import entry_settings

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ClearSpace sensors."""
    _LOGGER.info("Setting up ClearSpace sensors for entry %s", entry.entry_id)

    coordinator = hass.data.get(DOMAIN, {}).get("entries", {}).get(entry.entry_id, {}).get("coordinator")
    if coordinator is None:
        _LOGGER.error("ClearSpace coordinator not found for entry %s", entry.entry_id)
        return

    async_add_entities(
        [
            ClearSpaceTaskSensor(coordinator, entry, "open"),
            ClearSpaceTaskSensor(coordinator, entry, "due_today"),
            ClearSpaceTaskSensor(coordinator, entry, "overdue"),
        ]
    )


class ClearSpaceTaskSensor(CoordinatorEntity, SensorEntity):
    """A ClearSpace task count sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "tasks"

    def __init__(self, coordinator, entry: ConfigEntry, kind: str) -> None:
        super().__init__(coordinator)
        self._kind = kind
        self._entry = entry
        self._settings = entry_settings(entry)
        self._attr_unique_id = f"{entry.entry_id}_{kind}"
        self._attr_name = f"{self._settings['name']} {kind.replace('_', ' ').title()}"
        _LOGGER.debug("Created ClearSpace sensor: %s (%s)", self._attr_unique_id, kind)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._settings["name"],
            "manufacturer": "ClearSpace",
            "model": "Task Manager",
        }

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        tasks = self.coordinator.data.get("tasks", [])
        if not tasks:
            return 0
        today = date.today().isoformat()
        if self._kind == "open":
            return sum(1 for task in tasks if task.get("status") != "done")
        if self._kind == "due_today":
            return sum(
                1
                for task in tasks
                if task.get("status") != "done" and task.get("due") == today
            )
        return sum(
            1
            for task in tasks
            if task.get("status") != "done"
            and bool(task.get("due"))
            and task["due"] < today
        )

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        tasks = self.coordinator.data.get("tasks", [])
        return {"tasks": tasks}
