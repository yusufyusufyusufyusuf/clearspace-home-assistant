"""Shared helpers for the ClearSpace integration."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_API_TOKEN,
    CONF_API_URL,
    CONF_ENTITY_PREFIX,
    CONF_IS_DEFAULT,
    CONF_REFRESH_INTERVAL,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_REFRESH_INTERVAL,
)

_PREFIX_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str | None, default: str = DEFAULT_ENTITY_PREFIX) -> str:
    """Convert a human label into a safe entity prefix."""
    text = str(value or "").strip().lower()
    text = _PREFIX_RE.sub("_", text).strip("_")
    return text or default


def entry_settings(entry: ConfigEntry) -> dict[str, Any]:
    """Return normalized settings for a config entry."""
    data = dict(entry.data or {})
    options = dict(entry.options or {})

    name = str(entry.title or data.get("name") or "ClearSpace")
    prefix_source = options.get(CONF_ENTITY_PREFIX) or data.get(CONF_ENTITY_PREFIX) or name

    return {
        "name": name,
        "api_url": str(data.get(CONF_API_URL, "")).rstrip("/"),
        "api_token": str(data.get(CONF_API_TOKEN, "")),
        "entity_prefix": slugify(prefix_source),
        "refresh_interval": int(
            options.get(CONF_REFRESH_INTERVAL, data.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
        ),
        "is_default": bool(options.get(CONF_IS_DEFAULT, data.get(CONF_IS_DEFAULT, False))),
    }


def unique_entity_prefix(
    desired_prefix: str | None,
    entries: list[ConfigEntry],
    current_entry_id: str | None = None,
) -> str:
    """Ensure the generated entity prefix does not collide with another entry."""
    base = slugify(desired_prefix)
    used = {
        entry_settings(entry)["entity_prefix"]
        for entry in entries
        if entry.entry_id != current_entry_id
    }
    if base not in used:
        return base

    suffix = 2
    candidate = f"{base}_{suffix}"
    while candidate in used:
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


def entry_state_ids(entity_prefix: str) -> dict[str, str]:
    """Build the Home Assistant state IDs for an entry."""
    prefix = slugify(entity_prefix)
    return {
        "tasks": f"sensor.{prefix}_tasks",
        "open": f"sensor.{prefix}_open",
        "due_today": f"sensor.{prefix}_due_today",
        "overdue": f"sensor.{prefix}_overdue",
    }


def resolve_entry_record(
    domain_data: dict[str, Any],
    *,
    entry_id: str | None = None,
    entity_prefix: str | None = None,
) -> dict[str, Any] | None:
    """Find the record to use for a service call."""
    entries: dict[str, dict[str, Any]] = domain_data.get("entries", {}) or {}
    records = list(entries.values())
    if not records:
        return None

    if entry_id and entry_id in entries:
        return entries[entry_id]

    if entity_prefix:
        wanted = slugify(entity_prefix)
        for record in records:
            if record.get("entity_prefix") == wanted:
                return record

    for record in records:
        if record.get("is_default"):
            return record

    return records[0]
