"""Tests for the bundled Lovelace card and its static hosting."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.lt_fuel_prices.frontend import (
    FRONTEND_DIR,
    async_register_frontend,
    async_unregister_frontend,
)


def _registered_urls(hass: HomeAssistant) -> list[str]:
    return sorted(
        url
        for url in hass.data.get(DATA_EXTRA_MODULE_URL, set())
        if url.startswith("/lt_fuel_prices/")
    )


def test_frontend_files_are_bundled():
    """The card and its assets ship inside the integration."""
    assert (FRONTEND_DIR / "fuel-prices-card.js").is_file()
    for name in (
        "alausa",
        "balticpetroleum",
        "circlek",
        "default",
        "emsi",
        "neste",
        "saurida",
        "viada",
    ):
        assert (FRONTEND_DIR / "logos" / f"{name}.png").is_file()


def test_card_is_configurable_and_escapes_markup():
    """The card is not tied to one entity and escapes interpolated data."""
    body = (FRONTEND_DIR / "fuel-prices-card.js").read_text(encoding="utf-8")

    assert "DEFAULT_ENTITY" not in body
    assert "sensor.marijampole_degalines" not in body
    assert "Neste - Marijampolė" not in body
    assert "ha-entity-picker" in body
    assert "static getStubConfig(hass" in body
    assert "const esc =" in body


def test_readme_documents_card_keys():
    """The card options are documented for YAML users."""
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    for key in (
        "data_entity",
        "mode",
        "fuel",
        "station",
        "show_logo",
        "show_petrol",
        "show_diesel",
        "show_lpg",
    ):
        assert key in readme


async def test_register_frontend_is_idempotent(hass: HomeAssistant) -> None:
    """The card module is registered once per Home Assistant instance."""
    hass.data.setdefault(DATA_EXTRA_MODULE_URL, set())

    await async_register_frontend(hass)
    urls = _registered_urls(hass)
    assert len(urls) == 1
    assert urls[0].startswith("/lt_fuel_prices/fuel-prices-card.js?v=")

    await async_register_frontend(hass)
    assert _registered_urls(hass) == urls


async def test_unregister_frontend(hass: HomeAssistant) -> None:
    """Unloading the last entry stops loading the card."""
    hass.data.setdefault(DATA_EXTRA_MODULE_URL, set())

    await async_register_frontend(hass)
    assert _registered_urls(hass)

    async_unregister_frontend(hass)
    assert _registered_urls(hass) == []


async def test_card_is_served(hass: HomeAssistant, hass_client) -> None:
    """The card JavaScript is served from the integration static path."""
    assert await async_setup_component(hass, "http", {})
    hass.data.setdefault(DATA_EXTRA_MODULE_URL, set())
    await async_register_frontend(hass)

    client = await hass_client()
    response = await client.get("/lt_fuel_prices/fuel-prices-card.js")
    assert response.status == 200
    body = await response.text()
    assert "fuel-prices-card" in body, body[:300]
    assert 'const ASSET_BASE = "/lt_fuel_prices"' in body, body[:600]
    assert "/logos/" in body, body[:600]
