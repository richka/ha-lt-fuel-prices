"""Shared helpers for the ENA fuel prices test suite."""

from __future__ import annotations

from typing import Any

from yarl import URL

from custom_components.lt_fuel_prices.const import (
    API_BASE_URL,
    CONF_CITY_PREFIX,
    CONF_MUNICIPALITY,
    CONF_STATIONS,
    CONF_STATIONS_MODE,
    CONF_TOKEN,
    CONF_TOKEN_AUTO,
    STATIONS_MODE_NONE,
    WEB_URL,
)

MUNICIPALITY = "Marijampolės sav."
TOKEN = "1|TESTTOKEN"
UPDATED_AT = "2026-11-10 10:00:00"
WEBSITE = WEB_URL

DISCOVER_HTML = (
    '<script type="module" crossorigin src="./assets/index-TEST.js"></script>'
)
DISCOVER_INDEX_JS = 'const bundle = "./FuelPriceSiteApp-TEST.js";'
DISCOVER_APP_JS = (
    'ii={apiBase:"https://api-degalukainos.ena.lt/api/v1",token:"1|TESTTOKEN"}'
)


def row(
    name: str,
    address: str,
    fuel: str,
    price: str | None,
    municipality: str = MUNICIPALITY,
) -> dict[str, Any]:
    """Build one API price row."""
    return {
        "gas_station_name": name,
        "address": address,
        "fuel_type": fuel,
        "price": price,
        "municipality": municipality,
    }


ROWS: list[dict[str, Any]] = [
    row(
        "Neste Tarpučiai",
        "Marijampolė, Vilkaviškio g. 61D, 68153",
        "benzinas_95",
        "1.794",
    ),
    row(
        "Neste Tarpučiai",
        "Marijampolė, Vilkaviškio g. 61D, 68153",
        "dyzelinas",
        "2.194",
    ),
    row(
        "Baltic Petroleum",
        "Marijampolė,\u00a0Vasaros g. 15, 68266",
        "benzinas_95",
        "1.789",
    ),
    row(
        "Baltic Petroleum",
        "Marijampolė,\u00a0Vasaros g. 15, 68266",
        "dyzelinas",
        "2.179",
    ),
    row("Alauša", "Marijampolė, Stoties g. 49, 68261", "benzinas_95", "1.799"),
    row("Alauša", "Marijampolė, Stoties g. 49, 68261", "dyzelinas", "2.189"),
    row("Alauša", "Marijampolė, Stoties g. 49, 68261", "snd", "0.989"),
    row("Saurida", "Marijampolė, Statybininkų g. 8, 68108", "benzinas_95", None),
    row("Saurida", "Marijampolė, Statybininkų g. 8, 68108", "dyzelinas", None),
    row("Valdegra", "Igliauka, Prienų g. 7, 69117", "benzinas_95", "1.700"),
]


def prices_payload(
    rows: list[dict[str, Any]] | None = None,
    updated_at: str | None = UPDATED_AT,
) -> dict[str, Any]:
    """Build a prices API payload."""
    data = ROWS if rows is None else rows
    return {
        "data": data,
        "meta": {"total": len(data), "per_page": 100, "current_page": 1},
        "last_updated": updated_at,
    }


def prices_url(municipality: str = MUNICIPALITY) -> str:
    """Return the URL the integration uses for municipal prices."""
    return str(
        URL(f"{API_BASE_URL}/read/prices").with_query(
            {"municipality": municipality}
        )
    )


def latest_url() -> str:
    """Return the latest prices URL."""
    return f"{API_BASE_URL}/read/prices/latest"


def validate_url() -> str:
    """Return the URL used to validate a token."""
    return str(
        URL(f"{API_BASE_URL}/read/prices").with_query({"per_page": 1})
    )


def mock_token_discovery(aioclient_mock) -> None:
    """Register the three requests used to scrape a token."""
    aioclient_mock.get(f"{WEB_URL}/", text=DISCOVER_HTML)
    aioclient_mock.get(f"{WEB_URL}/assets/index-TEST.js", text=DISCOVER_INDEX_JS)
    aioclient_mock.get(
        f"{WEB_URL}/assets/FuelPriceSiteApp-TEST.js", text=DISCOVER_APP_JS
    )


def entry_data(**overrides: Any) -> dict[str, Any]:
    """Build config entry data."""
    data = {
        CONF_TOKEN: TOKEN,
        CONF_TOKEN_AUTO: True,
        CONF_MUNICIPALITY: MUNICIPALITY,
    }
    data.update(overrides)
    return data


def entry_options(
    prefix: str = "Marijampolė",
    mode: str = STATIONS_MODE_NONE,
    stations: list[str] | None = None,
) -> dict[str, Any]:
    """Build config entry options."""
    return {
        CONF_CITY_PREFIX: prefix,
        CONF_STATIONS_MODE: mode,
        CONF_STATIONS: stations or [],
    }
