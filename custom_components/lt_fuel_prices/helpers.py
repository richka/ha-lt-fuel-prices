"""Helpers shared by the ENA fuel prices platforms and the options flow."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    CONF_STATIONS,
    CONF_STATIONS_MODE,
    STATIONS_MODE_ALL,
    STATIONS_MODE_NONE,
    STATIONS_MODE_SELECTED,
)

STATION_UNIQUE_ID_PREFIX = "station_"


def station_unique_id(entry_id: str, station_key: str) -> str:
    """Return the registry unique id for a station sensor."""
    return f"{entry_id}_{STATION_UNIQUE_ID_PREFIX}{slugify(station_key)}"


def wanted_station_unique_ids(entry: ConfigEntry, station_keys: set[str]) -> set[str]:
    """Return the unique ids of the station sensors that should exist."""
    mode = entry.options.get(CONF_STATIONS_MODE, STATIONS_MODE_NONE)
    if mode == STATIONS_MODE_ALL:
        keys = station_keys
    elif mode == STATIONS_MODE_SELECTED:
        keys = set(entry.options.get(CONF_STATIONS, []))
    else:
        keys = set()
    return {station_unique_id(entry.entry_id, key) for key in keys}


def async_remove_obsolete_station_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    station_keys: set[str],
) -> None:
    """Remove registry entries of station sensors that are no longer wanted."""
    registry = er.async_get(hass)
    wanted = wanted_station_unique_ids(entry, station_keys)
    prefix = f"{entry.entry_id}_{STATION_UNIQUE_ID_PREFIX}"

    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id.startswith(prefix) and entity.unique_id not in wanted:
            registry.async_remove(entity.entity_id)
