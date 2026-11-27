"""The ENA (LEA) fuel prices integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_MUNICIPALITY, DOMAIN
from .coordinator import (
    STORAGE_VERSION,
    EnaFuelPricesCoordinator,
    storage_key,
)
from .frontend import async_register_frontend, async_unregister_frontend
from .helpers import async_remove_obsolete_station_entities

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type EnaConfigEntry = ConfigEntry[EnaFuelPricesCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EnaConfigEntry) -> bool:
    """Set up ENA fuel prices from a config entry."""
    coordinator = EnaFuelPricesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Bundle the Lovelace card with the integration: serve it and load it.
    await async_register_frontend(hass)

    # Drop station sensors that were deselected while the entry was unloaded.
    async_remove_obsolete_station_entities(
        hass, entry, {station.key for station in coordinator.data.stations}
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnaConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not _has_loaded_entries(hass, entry):
        async_unregister_frontend(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: EnaConfigEntry) -> None:
    """Remove the persisted price cache of a deleted entry."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()


def _has_loaded_entries(hass: HomeAssistant, entry: EnaConfigEntry) -> bool:
    """Return True when another loaded entry still needs the card."""
    return any(
        other.entry_id != entry.entry_id and other.state is ConfigEntryState.LOADED
        for other in hass.config_entries.async_entries(DOMAIN)
    )


async def _async_update_listener(
    hass: HomeAssistant, entry: EnaConfigEntry
) -> None:
    """Reload the entry only when its configuration changed."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is not None and coordinator.config_snapshot == (
        dict(entry.options),
        entry.data.get(CONF_MUNICIPALITY),
    ):
        # A token refresh updates entry.data; it must not rebuild the entry.
        return
    await hass.config_entries.async_reload(entry.entry_id)
