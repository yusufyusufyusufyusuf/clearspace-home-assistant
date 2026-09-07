"""ClearSpace task sensors."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([ClearSpaceTaskSensor(coordinator, entry, "open"), ClearSpaceTaskSensor(coordinator, entry, "due_today"), ClearSpaceTaskSensor(coordinator, entry, "overdue")])


class ClearSpaceTaskSensor(CoordinatorEntity, SensorEntity):
    """A ClearSpace task count sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "tasks"

    def __init__(self, coordinator, entry: ConfigEntry, kind: str) -> None:
        super().__init__(coordinator)
        self._kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{kind}"
        self._attr_name = kind.replace("_", " ").title()

    @property
    def native_value(self) -> int:
        tasks = self.coordinator.data.get("tasks", [])
        today = date.today().isoformat()
        if self._kind == "open":
            return sum(task.get("status") != "done" for task in tasks)
        if self._kind == "due_today":
            return sum(task.get("status") != "done" and task.get("due") == today for task in tasks)
        return sum(task.get("status") != "done" and bool(task.get("due")) and task["due"] < today for task in tasks)

