"""Serve the bundled Lovelace card and register it with the frontend."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
FRONTEND_URL = "/lt_fuel_prices"
CARD_FILE = "fuel-prices-card.js"
_DATA_KEY = f"{DOMAIN}_frontend"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static file path and the card module (idempotent)."""
    data = hass.data.setdefault(_DATA_KEY, {})
    if data.get("registered"):
        return

    if hass.http is not None:
        try:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        FRONTEND_URL,
                        str(FRONTEND_DIR),
                        cache_headers=True,
                    )
                ]
            )
        except RuntimeError:
            _LOGGER.debug("Static path %s is already registered", FRONTEND_URL)

    integration = await async_get_integration(hass, DOMAIN)
    url = f"{FRONTEND_URL}/{CARD_FILE}?v={integration.version or '0'}"
    if DATA_EXTRA_MODULE_URL in hass.data:
        frontend.add_extra_js_url(hass, url)
    else:
        _LOGGER.debug("Frontend is not set up yet; card module not registered")

    data["registered"] = True
    data["url"] = url
    _LOGGER.debug("Registered fuel prices card at %s", url)


def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Stop loading the card when the last config entry is unloaded."""
    data = hass.data.get(_DATA_KEY, {})
    url = data.pop("url", None)
    if url and url in hass.data.get(DATA_EXTRA_MODULE_URL, set()):
        frontend.remove_extra_js_url(hass, url)
    data["registered"] = False
