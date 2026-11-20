"""Tests for the pure snapshot transformation logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.lt_fuel_prices.const import FUEL_95, FUEL_DIESEL, FUEL_LPG
from custom_components.lt_fuel_prices.snapshot import (
    PriceCache,
    build_snapshot,
    count_stations,
    format_price,
    normalize_brand,
    normalize_text,
    parse_price,
    parse_updated_at,
    suggest_city_prefix,
)
from tests.helpers import MUNICIPALITY, ROWS, UPDATED_AT


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.794", 1.794),
        ("0,989", None),
        (None, None),
        ("", None),
        ("-", None),
        ("0.000", None),
        ("not-a-number", None),
        (2.179, 2.179),
    ],
)
def test_parse_price(raw, expected):
    """Prices are parsed to rounded floats, zero/empty means no data."""
    assert parse_price(raw) == expected


def test_format_price():
    """Prices are formatted the way the card expects them."""
    assert format_price(1.789) == "1,789 €"
    assert format_price(0.989) == "0,989 €"
    assert format_price(None) == "—"


def test_normalize_brand():
    """Branch names are collapsed to their network brand."""
    assert normalize_brand("Neste Tarpučiai") == "Neste"
    assert normalize_brand("VIADA LT") == "VIADA"
    assert normalize_brand("Baltic Petroleum") == "Baltic Petroleum"
    assert normalize_brand("Nežinomas Tinklas") == "Nežinomas Tinklas"


def test_normalize_text():
    """Whitespace is collapsed and non-breaking spaces become regular ones."""
    assert normalize_text("Marijampolė,\u00a0Vasaros g. 15") == (
        "Marijampolė, Vasaros g. 15"
    )
    assert normalize_text("  A   B  ") == "A B"
    assert normalize_text(None) == ""


def test_parse_updated_at_adds_timezone():
    """The naive API timestamp is treated as the Home Assistant timezone."""
    parsed = parse_updated_at(UPDATED_AT)
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parse_updated_at(None) is None
    assert parse_updated_at("nonsense") is None


def _snapshot(city_prefix: str | None = "Marijampolė"):
    return build_snapshot(
        ROWS,
        municipality=MUNICIPALITY,
        city_prefix=city_prefix,
        updated_at=UPDATED_AT,
    )


def test_build_snapshot_groups_stations():
    """Rows are grouped per address and missing prices are dropped."""
    snapshot = _snapshot()
    assert len(snapshot.stations) == 4

    by_brand = {station.brand: station for station in snapshot.stations}
    assert set(by_brand) == {"Neste", "Baltic Petroleum", "Alauša", "Saurida"}

    neste = by_brand["Neste"]
    assert neste.prices == {FUEL_95: 1.794, FUEL_DIESEL: 2.194}
    assert neste.name == "Neste Tarpučiai"
    assert neste.label == "Neste - Marijampolė, Vilkaviškio g. 61D, 68153"
    assert neste.short_address == "Vilkaviškio g. 61D"

    assert by_brand["Saurida"].prices == {}


def test_build_snapshot_without_city_filter():
    """Without a city prefix all stations of the municipality are kept."""
    assert len(_snapshot(None).stations) == 5
    assert len(_snapshot("").stations) == 5


def test_build_snapshot_city_filter_is_case_insensitive():
    """The city prefix filter ignores case."""
    assert len(_snapshot("marijampolė").stations) == 4


def test_aggregates_ignore_stations_without_prices():
    """Averages, minimums and the cheapest station skip missing prices."""
    snapshot = _snapshot()

    assert snapshot.average(FUEL_95) == round((1.794 + 1.789 + 1.799) / 3, 3)
    assert snapshot.cheapest(FUEL_95) == 1.789
    assert snapshot.cheapest_station(FUEL_95).brand == "Baltic Petroleum"

    assert snapshot.average(FUEL_DIESEL) == round((2.194 + 2.179 + 2.189) / 3, 3)
    assert snapshot.cheapest(FUEL_DIESEL) == 2.179

    assert snapshot.average(FUEL_LPG) == 0.989
    assert snapshot.cheapest(FUEL_LPG) == 0.989


def test_aggregates_without_data():
    """Aggregates return None when no station has the fuel."""
    snapshot = build_snapshot(
        [ROWS[0]],
        municipality=MUNICIPALITY,
        city_prefix="Marijampolė",
        updated_at=UPDATED_AT,
    )
    assert snapshot.average(FUEL_LPG) is None
    assert snapshot.cheapest(FUEL_LPG) is None
    assert snapshot.cheapest_station(FUEL_LPG) is None


def test_card_prices_shape():
    """Station prices are shaped for the fuel-prices-card."""
    snapshot = _snapshot()
    baltic = next(s for s in snapshot.stations if s.brand == "Baltic Petroleum")
    assert baltic.card_prices == [
        {"label": "95", "value": "1,789 €"},
        {"label": "Dyzelinas", "value": "2,179 €"},
        {"label": "Dujos", "value": "—"},
    ]


def test_suggest_city_prefix_and_counts():
    """The suggested prefix is the most common address prefix."""
    assert suggest_city_prefix(ROWS) == "Marijampolė"
    assert count_stations(ROWS, "Marijampolė") == (5, 4)
    assert count_stations(ROWS, "marijampolė") == (5, 4)
    assert count_stations(ROWS, "") == (5, 5)
    assert count_stations(ROWS, "Niekur") == (5, 0)
    assert suggest_city_prefix([]) == ""


def _empty_rows() -> list[dict]:
    return [{**row, "price": None} for row in ROWS]


def _snapshot_from_rows(rows: list[dict], updated_at: str = UPDATED_AT):
    return build_snapshot(
        rows,
        municipality=MUNICIPALITY,
        city_prefix="Marijampolė",
        updated_at=updated_at,
    )


def test_price_cache_carries_over_missing_prices():
    """A snapshot with empty prices keeps the previously known values."""
    now = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    cache = PriceCache()

    good = cache.apply(_snapshot_from_rows(ROWS), now)
    assert any(station.prices for station in good.stations)
    assert good.prices_updated_at == parse_updated_at(UPDATED_AT)

    empty = cache.apply(
        _snapshot_from_rows(_empty_rows(), "2026-11-11 10:00:00"),
        now + timedelta(days=1),
    )
    assert any(station.prices for station in empty.stations)
    # The sparse snapshot did not move the "real prices" timestamp.
    assert empty.prices_updated_at == good.prices_updated_at
    neste = next(s for s in empty.stations if s.brand == "Neste")
    assert neste.prices[FUEL_95] == 1.794


def test_price_cache_expires_old_prices():
    """Carried over prices expire after the cache lifetime."""
    now = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    cache = PriceCache(max_age=timedelta(days=1))

    cache.apply(_snapshot_from_rows(ROWS), now)
    expired = cache.apply(
        _snapshot_from_rows(_empty_rows(), "2026-11-12 10:00:00"),
        now + timedelta(days=2),
    )
    assert all(not station.prices for station in expired.stations)


def test_price_cache_fresh_prices_win():
    """New prices replace the cached ones."""
    now = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    cache = PriceCache()
    cache.apply(_snapshot_from_rows(ROWS), now)

    changed = [
        {**row, "price": "1.699"} if row["fuel_type"] == FUEL_95 else row
        for row in ROWS
    ]
    merged = cache.apply(
        _snapshot_from_rows(changed), now + timedelta(minutes=30)
    )
    neste = next(s for s in merged.stations if s.brand == "Neste")
    assert neste.prices[FUEL_95] == 1.699


def test_price_cache_roundtrip():
    """The cache survives a storage round trip."""
    now = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    cache = PriceCache()
    good = cache.apply(_snapshot_from_rows(ROWS), now)

    restored = PriceCache.from_dict(cache.as_dict())
    empty = restored.apply(
        _snapshot_from_rows(_empty_rows(), "2026-11-11 10:00:00"),
        now + timedelta(days=1),
    )
    assert empty.prices_updated_at == good.prices_updated_at
    neste = next(s for s in empty.stations if s.brand == "Neste")
    assert neste.prices[FUEL_95] == 1.794
