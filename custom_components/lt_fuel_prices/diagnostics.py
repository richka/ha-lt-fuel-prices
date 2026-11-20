"""Diagnostics support for the ENA fuel prices integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN

REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data

    data = dict(entry.data)
    if CONF_TOKEN in data:
        data[CONF_TOKEN] = REDACTED

    return {
        "entry": {
            "title": entry.title,
            "data": data,
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "updated_at": snapshot.updated_at.isoformat() if snapshot else None,
            "station_count": len(snapshot.stations) if snapshot else 0,
            "stations": [
                {
                    "brand": station.brand,
                    "address": station.address,
                    "prices": station.prices,
                }
                for station in (snapshot.stations if snapshot else ())
            ],
        },
    }
