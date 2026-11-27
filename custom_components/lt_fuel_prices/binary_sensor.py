"""Binary sensor platform for the ENA fuel prices integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import STALE_AFTER
from .coordinator import EnaFuelPricesCoordinator
from .entity import EnaFuelPricesEntity

PARALLEL_UPDATES = 0


class EnaDataStaleSensor(EnaFuelPricesEntity, BinarySensorEntity):
    """Problem sensor that turns on when the LEA data is too old."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "stale"

    def __init__(self, coordinator: EnaFuelPricesCoordinator) -> None:
        """Initialize the sensor."""
        entry = coordinator.config_entry
        super().__init__(
            coordinator,
            unique_id=f"{entry.entry_id}_stale",
            suggested_object_id="duomenys_pasene",
        )

    @property
    def is_on(self) -> bool:
        """Return True if the last real prices are older than the threshold."""
        updated_at = (
            self.coordinator.data.prices_updated_at if self.coordinator.data else None
        )
        if updated_at is None:
            return True
        return dt_util.now(UTC) - updated_at > STALE_AFTER

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the price and publication timestamps."""
        snapshot = self.coordinator.data
        prices_updated_at = snapshot.prices_updated_at if snapshot else None
        published_at = snapshot.updated_at if snapshot else None
        return {
            "prices_updated_at": (
                prices_updated_at.isoformat() if prices_updated_at else None
            ),
            "data_updated": published_at.isoformat() if published_at else None,
            "stale_after": str(STALE_AFTER),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the stale data binary sensor."""
    coordinator: EnaFuelPricesCoordinator = entry.runtime_data
    async_add_entities([EnaDataStaleSensor(coordinator)])
