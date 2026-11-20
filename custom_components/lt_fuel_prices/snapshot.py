"""Pure transformation of API rows into station snapshots.

This module intentionally contains no Home Assistant entity code so it can be
unit tested without a running Home Assistant instance.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import BRAND_PREFIXES, FUEL_LABELS, PRICE_CACHE_MAX_AGE

NO_PRICE_LABEL = "—"


def format_price(value: float | None) -> str:
    """Return a Lithuanian formatted price label for the card."""
    if value is None or value <= 0:
        return NO_PRICE_LABEL
    return f"{value:.3f}".replace(".", ",") + " €"


def normalize_text(value: Any) -> str:
    """Collapse whitespace, including the non-breaking spaces the API returns."""
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def parse_price(raw: Any) -> float | None:
    """Parse an API price value; empty/zero prices mean "no data"."""
    if raw is None or raw == "" or raw == "-":
        return None
    try:
        value = round(float(raw), 3)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def parse_updated_at(raw: Any) -> datetime | None:
    """Parse the API ``last_updated`` value into an aware datetime."""
    if not raw:
        return None
    parsed = dt_util.parse_datetime(str(raw))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return parsed


def normalize_brand(name: str) -> str:
    """Collapse branch station names to their network brand."""
    first = (name or "").split(" ")[0].lower()
    return BRAND_PREFIXES.get(first, name or "?")


@dataclass(frozen=True, slots=True)
class Station:
    """One fuel station with the prices that are currently known."""

    key: str
    name: str
    brand: str
    address: str
    prices: dict[str, float]

    def price(self, fuel: str) -> float | None:
        """Return the price for a fuel key, if available."""
        return self.prices.get(fuel)

    @property
    def label(self) -> str:
        """Return the ``brand - address`` label used by the card."""
        return f"{self.brand} - {self.address}"

    @property
    def short_address(self) -> str:
        """Return the street part of the address (without city/postcode)."""
        parts = [part.strip() for part in self.address.split(",")]
        if len(parts) > 1:
            return parts[1]
        return self.address

    @property
    def card_prices(self) -> list[dict[str, str]]:
        """Return prices in the shape expected by fuel-prices-card."""
        return [
            {"label": label, "value": format_price(self.prices.get(fuel))}
            for fuel, label in FUEL_LABELS.items()
        ]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """All stations of one municipality at one point in time."""

    municipality: str
    updated_at: datetime | None
    stations: tuple[Station, ...]
    prices_updated_at: datetime | None = None

    def prices(self, fuel: str) -> list[float]:
        """Return all known prices for a fuel."""
        return [
            price
            for station in self.stations
            if (price := station.prices.get(fuel)) is not None
        ]

    def average(self, fuel: str) -> float | None:
        """Return the average price for a fuel."""
        values = self.prices(fuel)
        return round(sum(values) / len(values), 3) if values else None

    def cheapest(self, fuel: str) -> float | None:
        """Return the cheapest price for a fuel."""
        values = self.prices(fuel)
        return round(min(values), 3) if values else None

    def cheapest_station(self, fuel: str) -> Station | None:
        """Return the station with the cheapest price for a fuel."""
        candidates = [
            station for station in self.stations if station.prices.get(fuel)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda station: station.prices[fuel])


def address_prefixes(rows: Iterable[dict[str, Any]]) -> Counter[str]:
    """Count the address prefixes (text before the first comma)."""
    counter: Counter[str] = Counter()
    for row in rows:
        address = normalize_text(row.get("address"))
        if not address:
            continue
        counter[address.split(",")[0].strip()] += 1
    return counter


def suggest_city_prefix(rows: Iterable[dict[str, Any]]) -> str:
    """Suggest the most common city prefix for a set of rows."""
    prefixes = address_prefixes(rows)
    if not prefixes:
        return ""
    return prefixes.most_common(1)[0][0]


def count_stations(
    rows: Iterable[dict[str, Any]], city_prefix: str | None
) -> tuple[int, int]:
    """Return ``(total, matching)`` station counts for a city prefix."""
    addresses = {
        normalize_text(row.get("address"))
        for row in rows
        if normalize_text(row.get("address"))
    }
    prefix = (city_prefix or "").strip().lower()
    matching = (
        sum(1 for address in addresses if address.lower().startswith(prefix))
        if prefix
        else len(addresses)
    )
    return len(addresses), matching


def build_snapshot(
    rows: Iterable[dict[str, Any]],
    *,
    municipality: str,
    city_prefix: str | None,
    updated_at: Any,
) -> Snapshot:
    """Group raw API rows into a snapshot of stations."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        address = normalize_text(row.get("address"))
        if not address:
            continue
        entry = grouped.setdefault(
            address,
            {"name": normalize_text(row.get("gas_station_name")), "prices": {}},
        )
        fuel = row.get("fuel_type")
        if fuel:
            entry["prices"][str(fuel)] = parse_price(row.get("price"))

    prefix = (city_prefix or "").strip().lower()
    stations: list[Station] = []
    for address, entry in grouped.items():
        if prefix and not address.lower().startswith(prefix):
            continue
        brand = normalize_brand(entry["name"])
        prices = {
            fuel: price
            for fuel, price in entry["prices"].items()
            if price is not None
        }
        stations.append(
            Station(
                key=f"{brand} - {address}",
                name=entry["name"],
                brand=brand,
                address=address,
                prices=prices,
            )
        )

    stations.sort(key=lambda station: (station.brand.lower(), station.address))
    updated = parse_updated_at(updated_at)
    has_prices = any(station.prices for station in stations)
    return Snapshot(
        municipality=municipality,
        updated_at=updated,
        stations=tuple(stations),
        prices_updated_at=updated if has_prices else None,
    )


class PriceCache:
    """Keep the last known price per station and fuel.

    LEA occasionally publishes a snapshot where almost every ``price`` field is
    empty (for example when their feed fails). Carrying the last known values
    over keeps the dashboard useful, while a separate timestamp records when
    real prices were last seen so staleness can still be reported.
    """

    def __init__(self, max_age: timedelta = PRICE_CACHE_MAX_AGE) -> None:
        """Initialize an empty cache."""
        self._max_age = max_age
        self._values: dict[tuple[str, str], tuple[float, datetime]] = {}
        self._prices_updated_at: datetime | None = None

    @property
    def prices_updated_at(self) -> datetime | None:
        """Return when prices were last actually present."""
        return self._prices_updated_at

    def apply(self, snapshot: Snapshot, now: datetime) -> Snapshot:
        """Merge a fresh snapshot with cached prices."""
        fresh: dict[tuple[str, str], tuple[float, datetime]] = {}
        for station in snapshot.stations:
            for fuel, price in station.prices.items():
                fresh[(station.key, fuel)] = (price, now)

        cutoff = now - self._max_age
        self._values = {
            key: value
            for key, value in self._values.items()
            if value[1] >= cutoff
        }
        self._values.update(fresh)

        # Only advance the price timestamp when a meaningful share of the
        # stations reported prices. A snapshot with a few stray values is
        # treated as a failed publication.
        if len(fresh) >= max(1, len(snapshot.stations) / 2):
            self._prices_updated_at = snapshot.updated_at or now

        stations: list[Station] = []
        for station in snapshot.stations:
            prices = dict(station.prices)
            for fuel in FUEL_LABELS:
                if fuel in prices:
                    continue
                cached = self._values.get((station.key, fuel))
                if cached is not None:
                    prices[fuel] = cached[0]
            stations.append(replace(station, prices=prices))

        return replace(
            snapshot,
            stations=tuple(stations),
            prices_updated_at=self._prices_updated_at,
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize the cache for Home Assistant storage."""
        return {
            "prices_updated_at": (
                self._prices_updated_at.isoformat()
                if self._prices_updated_at
                else None
            ),
            "values": [
                [station_key, fuel, price, seen.isoformat()]
                for (station_key, fuel), (price, seen) in self._values.items()
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        max_age: timedelta = PRICE_CACHE_MAX_AGE,
    ) -> PriceCache:
        """Restore a cache from Home Assistant storage."""
        cache = cls(max_age)
        cache._prices_updated_at = parse_updated_at(data.get("prices_updated_at"))
        for item in data.get("values") or []:
            try:
                station_key, fuel, price, seen_raw = item
                seen = parse_updated_at(seen_raw)
                if seen is None:
                    continue
                cache._values[(str(station_key), str(fuel))] = (
                    float(price),
                    seen,
                )
            except (TypeError, ValueError):
                continue
        return cache
