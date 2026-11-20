"""Tests for the ENA fuel prices sensor platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lt_fuel_prices.const import (
    DOMAIN,
    STATIONS_MODE_ALL,
    STATIONS_MODE_SELECTED,
)
from tests.helpers import (
    MUNICIPALITY,
    ROWS,
    entry_data,
    entry_options,
    prices_payload,
    prices_url,
)

STATIONS_ENTITY = "sensor.marijampole_degalines"
NESTE_SENSOR = "sensor.marijampole_neste_vilkaviskio_g_61d"


async def _setup_entry(
    hass: HomeAssistant,
    aioclient_mock,
    options: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> MockConfigEntry:
    aioclient_mock.get(prices_url(), json=prices_payload(rows=rows))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=options or entry_options(),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_summary_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    """The aggregate sensors expose averages and cheapest prices."""
    await _setup_entry(hass, aioclient_mock)

    assert hass.states.get("sensor.marijampole_vidutine_95").state == "1.794"
    assert hass.states.get("sensor.marijampole_vidutine_dyzelinas").state == "2.187"
    assert hass.states.get("sensor.marijampole_pigiausia_95").state == "1.789"
    assert hass.states.get("sensor.marijampole_pigiausia_dyzelinas").state == "2.179"
    assert (
        hass.states.get("sensor.marijampole_pigiausia_95_degaline").state
        == "Baltic Petroleum - Marijampolė, Vasaros g. 15, 68266"
    )
    assert (
        hass.states.get("sensor.marijampole_pigiausia_dyzelinas_degaline").state
        == "Baltic Petroleum - Marijampolė, Vasaros g. 15, 68266"
    )


async def test_stations_attribute(hass: HomeAssistant, aioclient_mock) -> None:
    """The stations sensor carries the data consumed by the card."""
    await _setup_entry(hass, aioclient_mock)

    state = hass.states.get(STATIONS_ENTITY)
    assert state is not None
    assert state.state == "4"

    stations = state.attributes["stations"]
    assert len(stations) == 4
    assert [station["brand"] for station in stations] == [
        "Alauša",
        "Baltic Petroleum",
        "Neste",
        "Saurida",
    ]
    baltic = stations[1]
    assert baltic["address"] == "Marijampolė, Vasaros g. 15, 68266"
    assert baltic["prices"] == [
        {"label": "95", "value": "1,789 €"},
        {"label": "Dyzelinas", "value": "2,179 €"},
        {"label": "Dujos", "value": "—"},
    ]

    assert state.attributes["fuel_names"] == {
        "95": "95 benzinas",
        "Dyzelinas": "Dyzelinas",
        "Dujos": "LPG dujos",
    }
    assert state.attributes["municipality"] == MUNICIPALITY
    assert state.attributes["data_updated"] is not None


async def test_no_station_sensors_by_default(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """No per-station sensors are created unless the user opts in."""
    await _setup_entry(hass, aioclient_mock)
    assert hass.states.get(NESTE_SENSOR) is None


async def test_diagnostic_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    """The timestamp sensor and the technical data carrier are diagnostic."""
    await _setup_entry(hass, aioclient_mock)

    updated = hass.states.get("sensor.marijampole_paskutini_karta_atnaujinta")
    assert updated is not None
    assert updated.state.startswith("2026-11-10")
    assert updated.attributes["device_class"] == "timestamp"

    registry = er.async_get(hass)
    for entity_id in (
        "sensor.marijampole_paskutini_karta_atnaujinta",
        "sensor.marijampole_duomenu_saltinis",
        STATIONS_ENTITY,
        "binary_sensor.marijampole_duomenys_pasene",
    ):
        assert registry.async_get(entity_id).entity_category is (
            EntityCategory.DIAGNOSTIC
        )


async def test_source_sensor_and_device_disclaimer(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """The device page states the source and the unofficial status."""
    entry = await _setup_entry(hass, aioclient_mock)

    source = hass.states.get("sensor.marijampole_duomenu_saltinis")
    assert source is not None
    assert source.state == "LEA"
    attribution = source.attributes["attribution"]
    assert "Lietuvos energetikos agentūra" in attribution
    assert attribution.endswith("degalines valdančios įmonės.")
    assert source.attributes["url"] == "https://degalukainos.ena.lt/"
    disclaimer = source.attributes["disclaimer"]
    assert disclaimer.startswith(
        "Tai nepriklausoma trečiosios šalies sukurta integracija."
    )
    assert disclaimer.endswith("LEA šios integracijos nekuria ir neadministruoja.")

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device is not None
    assert device.manufacturer == "richka"
    assert (
        device.model
        == "Degalų kainos Lietuvoje"
    )


async def test_friendly_names(hass: HomeAssistant, aioclient_mock) -> None:
    """Sensor names start with a capital letter."""
    await _setup_entry(hass, aioclient_mock)

    names = {
        entity_id: state.attributes["friendly_name"]
        for entity_id in (
            "sensor.marijampole_vidutine_95",
            "sensor.marijampole_vidutine_dyzelinas",
            "sensor.marijampole_pigiausia_95",
            "sensor.marijampole_pigiausia_dyzelinas",
            "sensor.marijampole_pigiausia_95_degaline",
            "sensor.marijampole_pigiausia_dyzelinas_degaline",
            STATIONS_ENTITY,
        )
        if (state := hass.states.get(entity_id)) is not None
    }
    assert names["sensor.marijampole_vidutine_95"] == (
        "Marijampolė Average 95 petrol price"
    )
    assert names["sensor.marijampole_pigiausia_95"] == "Marijampolė Cheapest 95"
    assert names[STATIONS_ENTITY] == "Marijampolė Station count"


async def test_selected_station_sensor(hass: HomeAssistant, aioclient_mock) -> None:
    """A selected station gets a sensor with all prices as attributes."""
    options = entry_options(
        mode=STATIONS_MODE_SELECTED,
        stations=["Neste - Marijampolė, Vilkaviškio g. 61D, 68153"],
    )
    await _setup_entry(hass, aioclient_mock, options)

    state = hass.states.get(NESTE_SENSOR)
    assert state is not None
    assert state.state == "1.794"
    assert state.attributes["benzinas_95"] == 1.794
    assert state.attributes["dyzelinas"] == 2.194
    assert state.attributes["snd"] is None
    assert state.attributes["address"] == "Marijampolė, Vilkaviškio g. 61D, 68153"

    # Only the selected station is created.
    assert hass.states.get("sensor.marijampole_alausa_stoties_g_49") is None


async def test_all_station_sensors(hass: HomeAssistant, aioclient_mock) -> None:
    """The 'all stations' mode creates one sensor per station."""
    await _setup_entry(hass, aioclient_mock, entry_options(mode=STATIONS_MODE_ALL))

    station_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if entity_id.startswith("sensor.marijampole_")
        and entity_id
        not in {
            "sensor.marijampole_degalines",
            "sensor.marijampole_vidutine_95",
            "sensor.marijampole_vidutine_dyzelinas",
            "sensor.marijampole_pigiausia_95",
            "sensor.marijampole_pigiausia_dyzelinas",
            "sensor.marijampole_pigiausia_95_degaline",
            "sensor.marijampole_pigiausia_dyzelinas_degaline",
            "sensor.marijampole_paskutini_karta_atnaujinta",
            "sensor.marijampole_duomenu_saltinis",
        }
    ]
    assert len(station_entities) == 4
    assert NESTE_SENSOR in station_entities


async def test_stale_binary_sensor(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    """The problem sensor reflects the age of the published data."""
    freezer.move_to("2026-11-10T12:00:00+00:00")
    await _setup_entry(hass, aioclient_mock)

    state = hass.states.get("binary_sensor.marijampole_duomenys_pasene")
    assert state is not None
    assert state.state == "off"


async def test_stale_binary_sensor_old_data(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    """Old data turns the problem sensor on."""
    freezer.move_to("2026-11-20T12:00:00+00:00")
    await _setup_entry(hass, aioclient_mock)

    state = hass.states.get("binary_sensor.marijampole_duomenys_pasene")
    assert state is not None
    assert state.state == "on"


async def test_empty_snapshot_reports_no_prices(
    hass: HomeAssistant, aioclient_mock, freezer
) -> None:
    """LEA can publish a snapshot with empty prices; it must not look fresh."""
    freezer.move_to("2026-11-14T12:00:00+00:00")
    empty_rows = [{**row, "price": None} for row in ROWS]
    await _setup_entry(hass, aioclient_mock, rows=empty_rows)

    stations = hass.states.get(STATIONS_ENTITY)
    assert stations.state == "4"
    assert all(
        price["value"] == "—"
        for station in stations.attributes["stations"]
        for price in station["prices"]
    )

    assert hass.states.get("sensor.marijampole_vidutine_95").state == "unknown"
    assert (
        hass.states.get("sensor.marijampole_paskutini_karta_atnaujinta").state
        == "unknown"
    )
    assert hass.states.get("binary_sensor.marijampole_duomenys_pasene").state == "on"
