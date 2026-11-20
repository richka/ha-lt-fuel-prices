"""Data update coordinator for the ENA fuel prices integration."""

from __future__ import annotations

import logging
from datetime import UTC

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    EnaApiAuthError,
    EnaApiConnectionError,
    EnaApiError,
    async_discover_token,
    async_get_prices,
)
from .const import (
    CONF_CITY_PREFIX,
    CONF_MUNICIPALITY,
    CONF_TOKEN,
    CONF_TOKEN_AUTO,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .snapshot import PriceCache, Snapshot, build_snapshot

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.{{entry_id}}_prices"


def storage_key(entry_id: str) -> str:
    """Return the storage key of the price cache for an entry."""
    return STORAGE_KEY.format(entry_id=entry_id)


class EnaFuelPricesCoordinator(DataUpdateCoordinator[Snapshot]):
    """Fetch and transform fuel prices for a single municipality."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self._store: Store[dict[str, object]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._cache = PriceCache()
        self._cache_loaded = False

    async def _async_update_data(self) -> Snapshot:
        """Fetch the latest prices from the LEA API."""
        entry = self.config_entry
        municipality: str = entry.data[CONF_MUNICIPALITY]

        try:
            response = await async_get_prices(
                self._session, entry.data[CONF_TOKEN], municipality
            )
        except EnaApiAuthError as err:
            token = await self._async_resolve_new_token(err)
            try:
                response = await async_get_prices(self._session, token, municipality)
            except EnaApiConnectionError as retry_err:
                raise UpdateFailed(
                    f"Failed to fetch LEA data: {retry_err}"
                ) from retry_err
            except EnaApiError as retry_err:
                raise UpdateFailed(str(retry_err)) from retry_err
        except EnaApiConnectionError as err:
            raise UpdateFailed(f"Failed to fetch LEA data: {err}") from err
        except EnaApiError as err:
            raise UpdateFailed(str(err)) from err

        if not self._cache_loaded:
            await self._async_load_cache()

        snapshot = build_snapshot(
            response.rows,
            municipality=municipality,
            city_prefix=entry.options.get(CONF_CITY_PREFIX, ""),
            updated_at=response.updated_at,
        )
        effective = self._cache.apply(snapshot, dt_util.now(UTC))
        await self._async_save_cache()
        return effective

    async def _async_load_cache(self) -> None:
        """Restore the last known prices from storage."""
        try:
            data = await self._store.async_load()
        except (OSError, ValueError) as err:
            _LOGGER.debug("Could not load the price cache: %s", err)
            data = None
        if data:
            self._cache = PriceCache.from_dict(data)
        self._cache_loaded = True

    async def _async_save_cache(self) -> None:
        """Persist the last known prices."""
        try:
            await self._store.async_save(self._cache.as_dict())
        except (OSError, ValueError) as err:  # pragma: no cover - disk issues
            _LOGGER.warning("Could not save the price cache: %s", err)

    async def _async_resolve_new_token(self, auth_error: Exception) -> str:
        """Discover a fresh token when the stored one was rejected."""
        if not self.config_entry.data.get(CONF_TOKEN_AUTO):
            raise ConfigEntryAuthFailed(
                "LEA rejected the provided access token"
            ) from auth_error

        try:
            token = await async_discover_token(self._session)
        except EnaApiError as err:
            raise ConfigEntryAuthFailed(
                "Could not discover a new LEA access token"
            ) from err

        _LOGGER.info("Automatically refreshed the LEA API access token")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_TOKEN: token},
        )
        return token
