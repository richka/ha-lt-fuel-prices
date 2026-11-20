"""Tests for coordinator error handling and diagnostics."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lt_fuel_prices.const import (
    CONF_TOKEN,
    CONF_TOKEN_AUTO,
    DOMAIN,
)
from custom_components.lt_fuel_prices.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
)
from tests.helpers import (
    MUNICIPALITY,
    TOKEN,
    entry_data,
    entry_options,
    mock_token_discovery,
    prices_payload,
    prices_url,
)


async def test_auth_error_refreshes_auto_token(hass, aioclient_mock) -> None:
    """A rejected token is rediscovered and stored on the entry."""
    mock_token_discovery(aioclient_mock)
    aioclient_mock.get(prices_url(), status=401)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(**{CONF_TOKEN: "1|EXPIRED"}),
        options=entry_options(),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_TOKEN] == TOKEN
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_error_manual_token_starts_reauth(hass, aioclient_mock) -> None:
    """A manual token that is rejected triggers the reauth flow."""
    aioclient_mock.get(prices_url(), status=401)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(**{CONF_TOKEN: "1|EXPIRED", CONF_TOKEN_AUTO: False}),
        options=entry_options(),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    progress = hass.config_entries.flow.async_progress()
    assert any(
        flow["context"].get("source") == "reauth"
        and flow["context"].get("entry_id") == entry.entry_id
        for flow in progress
    )


async def test_server_error_retries(hass, aioclient_mock) -> None:
    """A server error schedules a retry instead of failing the entry."""
    aioclient_mock.get(prices_url(), status=500)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=entry_options(),
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_diagnostics_redacts_token(hass, aioclient_mock) -> None:
    """Diagnostics never expose the bearer token."""
    aioclient_mock.get(prices_url(), json=prices_payload())

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=entry_options(),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"][CONF_TOKEN] == REDACTED
    assert diagnostics["coordinator"]["station_count"] == 4
    assert len(diagnostics["coordinator"]["stations"]) == 4
