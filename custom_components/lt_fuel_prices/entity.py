"""Base entity for the ENA fuel prices integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, WEB_URL
from .coordinator import EnaFuelPricesCoordinator


class EnaFuelPricesEntity(CoordinatorEntity[EnaFuelPricesCoordinator]):
    """Common base for all ENA fuel prices entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnaFuelPricesCoordinator,
        *,
        name: str | None = None,
        unique_id: str,
        entity_id: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        if name is not None:
            self._attr_name = name
        self._attr_unique_id = unique_id
        if entity_id is not None:
            # Keep entity IDs stable when the display name or UI language changes.
            self.entity_id = entity_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about the configuration entry."""
        entry = self.coordinator.config_entry
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Degalų kainos Lietuvoje",
            name=entry.title,
            configuration_url=WEB_URL,
        )
