"""Sensor platform for the ENA fuel prices integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    ATTRIBUTION_TEXT,
    CONF_STATIONS,
    CONF_STATIONS_MODE,
    DISCLAIMER_TEXT,
    FUEL_95,
    FUEL_DIESEL,
    FUEL_LABELS,
    FUEL_LPG,
    FUEL_NAMES,
    SOURCE_STATE,
    SOURCE_URL,
    STATIONS_MODE_ALL,
    STATIONS_MODE_NONE,
    STATIONS_MODE_SELECTED,
)
from .coordinator import EnaFuelPricesCoordinator
from .entity import EnaFuelPricesEntity
from .helpers import station_unique_id
from .snapshot import Snapshot, Station

PRICE_UNIT = "€/l"


@dataclass(frozen=True, kw_only=True)
class EnaSensorDescription(SensorEntityDescription):
    """Describes an ENA fuel prices sensor."""

    object_id: str
    value_fn: Callable[[Snapshot], float | str | datetime | None]
    attrs_fn: Callable[[Snapshot], Mapping[str, Any]] | None = None

def _stations_attributes(snapshot: Snapshot) -> Mapping[str, Any]:
    return {
        "stations": [
            {
                "brand": station.brand,
                "address": station.address,
                "prices": station.card_prices,
            }
            for station in snapshot.stations
        ],
        "fuel_names": dict(FUEL_NAMES),
        "data_updated": (
            snapshot.updated_at.isoformat() if snapshot.updated_at else None
        ),
        "prices_updated_at": (
            snapshot.prices_updated_at.isoformat()
            if snapshot.prices_updated_at
            else None
        ),
        "municipality": snapshot.municipality,
    }


def _cheapest_label(snapshot: Snapshot, fuel: str) -> str | None:
    station = snapshot.cheapest_station(fuel)
    return station.label if station else None


def _cheapest_attributes(snapshot: Snapshot, fuel: str) -> Mapping[str, Any]:
    station = snapshot.cheapest_station(fuel)
    if station is None:
        return {}
    return {
        "brand": station.brand,
        "address": station.address,
        "price": station.price(fuel),
    }


def _source_attributes(_snapshot: Snapshot) -> Mapping[str, Any]:
    return {
        "attribution": ATTRIBUTION_TEXT,
        "disclaimer": DISCLAIMER_TEXT,
        "url": SOURCE_URL,
    }


DESCRIPTIONS: tuple[EnaSensorDescription, ...] = (
    EnaSensorDescription(
        key="average_95",
        object_id="vidutine_95",
        translation_key="average_95",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda snapshot: snapshot.average(FUEL_95),
    ),
    EnaSensorDescription(
        key="average_diesel",
        object_id="vidutine_dyzelinas",
        translation_key="average_diesel",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda snapshot: snapshot.average(FUEL_DIESEL),
    ),
    EnaSensorDescription(
        key="cheapest_95",
        object_id="pigiausia_95",
        translation_key="cheapest_95",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda snapshot: snapshot.cheapest(FUEL_95),
    ),
    EnaSensorDescription(
        key="cheapest_diesel",
        object_id="pigiausia_dyzelinas",
        translation_key="cheapest_diesel",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=3,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda snapshot: snapshot.cheapest(FUEL_DIESEL),
    ),
    EnaSensorDescription(
        key="cheapest_95_station",
        object_id="pigiausia_95_degaline",
        translation_key="cheapest_95_station",
        icon="mdi:gas-station",
        value_fn=lambda snapshot: _cheapest_label(snapshot, FUEL_95),
        attrs_fn=lambda snapshot: _cheapest_attributes(snapshot, FUEL_95),
    ),
    EnaSensorDescription(
        key="cheapest_diesel_station",
        object_id="pigiausia_dyzelinas_degaline",
        translation_key="cheapest_diesel_station",
        icon="mdi:gas-station",
        value_fn=lambda snapshot: _cheapest_label(snapshot, FUEL_DIESEL),
        attrs_fn=lambda snapshot: _cheapest_attributes(snapshot, FUEL_DIESEL),
    ),
    # Diagnostika: techninis kortelės duomenų laikiklis (state = degalinių sk.)
    EnaSensorDescription(
        key="stations",
        object_id="degalines",
        translation_key="stations",
        icon="mdi:gas-station",
        native_unit_of_measurement="vnt.",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda snapshot: len(snapshot.stations),
        attrs_fn=_stations_attributes,
    ),
    # Diagnostika: kada LEA paskelbė / atnaujino duomenis
    EnaSensorDescription(
        key="updated_at",
        object_id="paskutini_karta_atnaujinta",
        translation_key="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda snapshot: snapshot.prices_updated_at,
    ),
    # Diagnostika: duomenų šaltinis ir neoficialumo įspėjimas
    EnaSensorDescription(
        key="source",
        object_id="duomenu_saltinis",
        translation_key="source",
        icon="mdi:database",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda snapshot: SOURCE_STATE,
        attrs_fn=_source_attributes,
    ),
)


class EnaFuelPricesSensor(EnaFuelPricesEntity, SensorEntity):
    """Sensor with a value derived from the current snapshot."""

    _unrecorded_attributes = frozenset({"stations"})
    entity_description: EnaSensorDescription

    def __init__(
        self,
        coordinator: EnaFuelPricesCoordinator,
        description: EnaSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        entry = coordinator.config_entry
        super().__init__(
            coordinator,
            unique_id=f"{entry.entry_id}_{description.key}",
            entity_id=f"sensor.{slugify(entry.title)}_{description.object_id}",
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return dict(self.entity_description.attrs_fn(self.coordinator.data))


class EnaStationSensor(EnaFuelPricesEntity, SensorEntity):
    """Price sensor for a single, user selected station."""

    _attr_native_unit_of_measurement = PRICE_UNIT
    _attr_suggested_display_precision = 3
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: EnaFuelPricesCoordinator, station: Station
    ) -> None:
        """Initialize the station sensor."""
        super().__init__(
            coordinator,
            name=f"{station.brand} {station.short_address}",
            unique_id=station_unique_id(
                coordinator.config_entry.entry_id, station.key
            ),
        )
        self._station_key = station.key

    @property
    def _station(self) -> Station | None:
        """Return the current snapshot of this station."""
        if self.coordinator.data is None:
            return None
        return next(
            (
                station
                for station in self.coordinator.data.stations
                if station.key == self._station_key
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Return False when the station is no longer reported by the API."""
        return super().available and self._station is not None

    @property
    def native_value(self) -> float | None:
        """Return the 95 petrol price of the station."""
        station = self._station
        return station.price(FUEL_95) if station else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return all known prices of the station."""
        station = self._station
        if station is None:
            return {}
        updated_at = self.coordinator.data.updated_at if self.coordinator.data else None
        return {
            "benzinas_95": station.price(FUEL_95),
            "dyzelinas": station.price(FUEL_DIESEL),
            "snd": station.price(FUEL_LPG),
            "address": station.address,
            "station": station.name,
            "fuel_names": {
                "benzinas_95": FUEL_LABELS[FUEL_95],
                "dyzelinas": FUEL_LABELS[FUEL_DIESEL],
                "snd": FUEL_LABELS[FUEL_LPG],
            },
            "data_updated": updated_at.isoformat() if updated_at else None,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENA fuel prices sensors."""
    coordinator: EnaFuelPricesCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        EnaFuelPricesSensor(coordinator, description)
        for description in DESCRIPTIONS
    ]
    entities.extend(_station_sensors(entry, coordinator))
    async_add_entities(entities)


def _station_sensors(
    entry: ConfigEntry, coordinator: EnaFuelPricesCoordinator
) -> list[EnaStationSensor]:
    """Return the station sensors the user opted in to."""
    if coordinator.data is None:
        return []

    mode = entry.options.get(CONF_STATIONS_MODE, STATIONS_MODE_NONE)
    if mode == STATIONS_MODE_NONE:
        return []
    if mode == STATIONS_MODE_ALL:
        selected = {station.key for station in coordinator.data.stations}
    elif mode == STATIONS_MODE_SELECTED:
        selected = set(entry.options.get(CONF_STATIONS, []))
    else:
        return []

    return [
        EnaStationSensor(coordinator, station)
        for station in coordinator.data.stations
        if station.key in selected
    ]
