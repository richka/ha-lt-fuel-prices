"""Tests for the LEA API client."""

from __future__ import annotations

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.lt_fuel_prices.api import (
    EnaApiAuthError,
    EnaApiConnectionError,
    EnaApiError,
    async_discover_token,
    async_get_municipalities,
    async_get_prices,
    async_validate_token,
    normalize_token,
)
from tests.helpers import (
    DISCOVER_HTML,
    DISCOVER_INDEX_JS,
    MUNICIPALITY,
    ROWS,
    TOKEN,
    UPDATED_AT,
    WEBSITE,
    latest_url,
    mock_token_discovery,
    prices_payload,
    prices_url,
    validate_url,
)


def test_normalize_token():
    """A pasted token may include the Bearer prefix."""
    assert normalize_token("1|abc") == "1|abc"
    assert normalize_token("Bearer 1|abc") == "1|abc"
    assert normalize_token("  bearer   1|abc  ") == "1|abc"


async def test_discover_token(hass, aioclient_mock):
    """The token is scraped from the public web app bundle."""
    mock_token_discovery(aioclient_mock)
    session = async_get_clientsession(hass)
    assert await async_discover_token(session) == TOKEN


async def test_discover_token_missing_bundle(hass, aioclient_mock):
    """An unexpected page raises a clean API error."""
    aioclient_mock.get(f"{WEBSITE}/", text="<html><body>maintenance</body></html>")
    session = async_get_clientsession(hass)
    with pytest.raises(EnaApiError):
        await async_discover_token(session)


async def test_discover_token_missing_token(hass, aioclient_mock):
    """A bundle without a token raises a clean API error."""
    aioclient_mock.get(f"{WEBSITE}/", text=DISCOVER_HTML)
    aioclient_mock.get(f"{WEBSITE}/assets/index-TEST.js", text=DISCOVER_INDEX_JS)
    aioclient_mock.get(
        f"{WEBSITE}/assets/FuelPriceSiteApp-TEST.js", text="no token here"
    )
    session = async_get_clientsession(hass)
    with pytest.raises(EnaApiError):
        await async_discover_token(session)


async def test_get_prices(hass, aioclient_mock):
    """Price rows and the update timestamp are returned."""
    aioclient_mock.get(prices_url(), json=prices_payload())
    session = async_get_clientsession(hass)

    response = await async_get_prices(session, TOKEN, MUNICIPALITY)

    assert response.rows == ROWS
    assert response.updated_at == UPDATED_AT


async def test_get_prices_unauthorized(hass, aioclient_mock):
    """401 responses turn into an auth error."""
    aioclient_mock.get(prices_url(), status=401)
    session = async_get_clientsession(hass)

    with pytest.raises(EnaApiAuthError):
        await async_get_prices(session, TOKEN, MUNICIPALITY)


async def test_get_prices_server_error(hass, aioclient_mock):
    """Server errors turn into a connection error."""
    aioclient_mock.get(prices_url(), status=500)
    session = async_get_clientsession(hass)

    with pytest.raises(EnaApiConnectionError):
        await async_get_prices(session, TOKEN, MUNICIPALITY)


async def test_get_prices_invalid_payload(hass, aioclient_mock):
    """A payload without a data list is rejected."""
    aioclient_mock.get(prices_url(), json={"unexpected": True})
    session = async_get_clientsession(hass)

    with pytest.raises(EnaApiConnectionError):
        await async_get_prices(session, TOKEN, MUNICIPALITY)


async def test_get_municipalities(hass, aioclient_mock):
    """Municipalities are de-duplicated and sorted."""
    rows = [
        {"municipality": "Vilniaus m. sav.", "fuel_type": "dyzelinas", "price": "2.1"},
        {"municipality": "Kauno m. sav.", "fuel_type": "dyzelinas", "price": "2.1"},
        {
            "municipality": "Vilniaus m. sav.",
            "fuel_type": "benzinas_95",
            "price": "1.8",
        },
        {"municipality": None},
    ]
    aioclient_mock.get(latest_url(), json=prices_payload(rows=rows))
    session = async_get_clientsession(hass)

    assert await async_get_municipalities(session, TOKEN) == [
        "Kauno m. sav.",
        "Vilniaus m. sav.",
    ]


async def test_validate_token(hass, aioclient_mock):
    """Validation uses a tiny request."""
    aioclient_mock.get(validate_url(), json={"data": []})
    session = async_get_clientsession(hass)
    await async_validate_token(session, TOKEN)


async def test_validate_token_rejected(hass, aioclient_mock):
    """A rejected token raises an auth error."""
    aioclient_mock.get(validate_url(), status=403)
    session = async_get_clientsession(hass)
    with pytest.raises(EnaApiAuthError):
        await async_validate_token(session, "bad")
