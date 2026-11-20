"""Constants for the ENA (LEA) fuel prices integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "lt_fuel_prices"
MANUFACTURER: Final = "richka"

API_BASE_URL: Final = "https://api-degalukainos.ena.lt/api/v1"
WEB_URL: Final = "https://degalukainos.ena.lt"

REQUEST_TIMEOUT: Final = 25
UPDATE_INTERVAL: Final = timedelta(minutes=30)
STALE_AFTER: Final = timedelta(days=3)
# How long a previously known price may be carried over when LEA publishes a
# snapshot with empty price fields (happens on some days).
PRICE_CACHE_MAX_AGE: Final = timedelta(days=7)
# Virš šios ribos „visos degalinės" režimui prašomas papildomas patvirtinimas.
ALL_STATIONS_WARNING_THRESHOLD: Final = 40

CONF_TOKEN: Final = "token"
CONF_TOKEN_AUTO: Final = "token_auto"
CONF_MUNICIPALITY: Final = "municipality"
CONF_CITY_PREFIX: Final = "city_prefix"
CONF_STATIONS_MODE: Final = "stations_mode"
CONF_STATIONS: Final = "stations"
CONF_CONFIRM: Final = "confirm"

STATIONS_MODE_NONE: Final = "none"
STATIONS_MODE_SELECTED: Final = "selected"
STATIONS_MODE_ALL: Final = "all"

FUEL_95: Final = "benzinas_95"
FUEL_DIESEL: Final = "dyzelinas"
FUEL_LPG: Final = "snd"

# API kuro raktas -> kortelės ženklo etiketė
FUEL_LABELS: Final[dict[str, str]] = {
    FUEL_95: "95",
    FUEL_DIESEL: "Dyzelinas",
    FUEL_LPG: "Dujos",
}

# Etiketė -> rodomas pavadinimas kortelėje
FUEL_NAMES: Final[dict[str, str]] = {
    "95": "95 benzinas",
    "Dyzelinas": "Dyzelinas",
    "Dujos": "LPG dujos",
}

# Duomenų šaltinio nurodymas (LEA reikalavimas).
SOURCE_URL: Final = "https://degalukainos.ena.lt/"
SOURCE_STATE: Final = "LEA"
ATTRIBUTION_TEXT: Final = (
    "Duomenų šaltinis – Lietuvos energetikos agentūra (LEA), "
    "https://degalukainos.ena.lt/. Pirminiai degalų kainų duomenų teikėjai – "
    "degalines valdančios įmonės."
)
DISCLAIMER_TEXT: Final = (
    "Tai nepriklausoma trečiosios šalies sukurta integracija. "
    "Už jos veikimą, duomenų nuskaitymą, atnaujinimą ir atvaizdavimą "
    "integracijoje atsako jos kūrėjas. "
    "LEA šios integracijos nekuria ir neadministruoja."
)

# Degalinių tinklų pavadinimų normalizavimas (API grąžina filialų pavadinimus,
# pvz. "Neste Tarpučiai"). Raktas - pirmas žodis mažosiomis raidėmis.
BRAND_PREFIXES: Final[dict[str, str]] = {
    "neste": "Neste",
    "emsi": "Emsi",
    "circle": "Circle K",
    "baltic": "Baltic Petroleum",
    "alauša": "Alauša",
    "alausa": "Alauša",
    "osijos": "Osijos dujos",
    "viada": "VIADA",
    "saurida": "Saurida",
    "orlen": "Orlen",
    "virši": "VIRŠI",
    "virsi": "VIRŠI",
}
