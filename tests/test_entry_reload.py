"""Tests for the config entry update listener.

The listener exists to reload the entry when the *configuration* changes. It is
registered with ``entry.add_update_listener``, and Home Assistant calls update
listeners after any ``async_update_entry`` — including a token refresh, which
changes data, not configuration.

The listener must ignore data-only updates and reload only when options change.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lt_fuel_prices.api import EnaApiAuthError, PricesResponse
from custom_components.lt_fuel_prices.const import (
    CONF_CITY_PREFIX,
    CONF_TOKEN,
    CONF_TOKEN_AUTO,
    DOMAIN,
)
from tests.helpers import (
    MUNICIPALITY,
    ROWS,
    TOKEN,
    UPDATED_AT,
    entry_data,
    entry_options,
)

OLD_TOKEN = "1|OLDTOKEN"


def response() -> PricesResponse:
    """Return a valid prices response."""
    return PricesResponse(rows=list(ROWS), updated_at=UPDATED_AT)


async def setup_entry(hass, token: str = OLD_TOKEN) -> MockConfigEntry:
    """Set up a loaded entry with a patched API."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MUNICIPALITY,
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(**{CONF_TOKEN: token, CONF_TOKEN_AUTO: True}),
        options=entry_options(),
    )
    entry.add_to_hass(hass)

    async def fake_get_prices(session, token, municipality):
        return response()

    with patch(
        "custom_components.lt_fuel_prices.coordinator.async_get_prices",
        side_effect=fake_get_prices,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_token_refresh_does_not_reload_the_entry(hass) -> None:
    """A refreshed token changes data, so the entry must not be set up again."""
    entry = await setup_entry(hass)
    original_coordinator = entry.runtime_data

    attempts = {"count": 0}

    async def fake_get_prices(session, token, municipality):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise EnaApiAuthError("token expired")
        return response()

    async def fake_discover(session):
        return TOKEN

    reload_mock = AsyncMock(return_value=True)

    with (
        patch(
            "custom_components.lt_fuel_prices.coordinator.async_get_prices",
            side_effect=fake_get_prices,
        ),
        patch(
            "custom_components.lt_fuel_prices.coordinator.async_discover_token",
            side_effect=fake_discover,
        ),
        patch.object(ConfigEntries, "async_reload", reload_mock),
    ):
        await original_coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.data[CONF_TOKEN] == TOKEN, "the token should have been refreshed"
    assert reload_mock.await_count == 0, (
        "refreshing a token is not a configuration change"
    )
    assert entry.runtime_data is original_coordinator, "the entry must not be rebuilt"


async def test_options_change_still_reloads(hass) -> None:
    """The listener must keep working for the case it was written for."""
    entry = await setup_entry(hass)

    reload_mock = AsyncMock(return_value=True)
    with patch.object(ConfigEntries, "async_reload", reload_mock):
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_CITY_PREFIX: "Vilnius"},
        )
        await hass.async_block_till_done()

    assert reload_mock.await_count == 1
