"""Tests for the config and options flows."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lt_fuel_prices.const import (
    CONF_CITY_PREFIX,
    CONF_CONFIRM,
    CONF_MUNICIPALITY,
    CONF_STATIONS,
    CONF_STATIONS_MODE,
    CONF_TOKEN,
    CONF_TOKEN_AUTO,
    DOMAIN,
    STATIONS_MODE_ALL,
    STATIONS_MODE_NONE,
    STATIONS_MODE_SELECTED,
)
from tests.helpers import (
    MUNICIPALITY,
    ROWS,
    TOKEN,
    WEBSITE,
    entry_data,
    entry_options,
    latest_url,
    mock_token_discovery,
    prices_payload,
    prices_url,
    row,
    validate_url,
)


async def _start_user_flow(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_auto_token_flow(hass, aioclient_mock):
    """The token is discovered and the entry is created with a city filter."""
    mock_token_discovery(aioclient_mock)
    aioclient_mock.get(latest_url(), json=prices_payload())
    aioclient_mock.get(prices_url(), json=prices_payload())

    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "municipality"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: MUNICIPALITY}
    )
    assert result["step_id"] == "city"
    placeholders = result["description_placeholders"]
    assert placeholders["stations"] == "5"
    assert placeholders["prefix"] == "Marijampolė"
    assert placeholders["matching"] == "4"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CITY_PREFIX: "Marijampolė"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Marijampolė"
    assert result["data"] == {
        CONF_TOKEN: TOKEN,
        CONF_TOKEN_AUTO: True,
        CONF_MUNICIPALITY: MUNICIPALITY,
    }
    assert result["options"] == {
        CONF_CITY_PREFIX: "Marijampolė",
        CONF_STATIONS_MODE: STATIONS_MODE_NONE,
        CONF_STATIONS: [],
    }


async def test_manual_token_flow(hass, aioclient_mock):
    """A manually pasted token is validated before continuing."""
    aioclient_mock.get(validate_url(), json={"data": []})
    aioclient_mock.get(latest_url(), json=prices_payload())
    aioclient_mock.get(prices_url(), json=prices_payload())

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: False}
    )
    assert result["step_id"] == "token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: f"Bearer {TOKEN}"}
    )
    assert result["step_id"] == "municipality"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: MUNICIPALITY}
    )
    assert result["step_id"] == "city"


async def test_manual_token_rejected(hass, aioclient_mock):
    """An invalid manual token shows an error and stays on the token step."""
    aioclient_mock.get(validate_url(), status=401)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "1|nope"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_auto_token_discovery_failure(hass, aioclient_mock):
    """A changed bundle structure shows a helpful error."""
    aioclient_mock.get(f"{WEBSITE}/", text="<html><body>maintenance</body></html>")

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: True}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "token_not_found"}


async def test_municipality_already_configured(hass, aioclient_mock):
    """The same municipality cannot be added twice."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=entry_options(),
    ).add_to_hass(hass)

    mock_token_discovery(aioclient_mock)
    aioclient_mock.get(latest_url(), json=prices_payload())

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: MUNICIPALITY}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_city_filter_without_matches(hass, aioclient_mock):
    """A filter that matches nothing is rejected."""
    mock_token_discovery(aioclient_mock)
    aioclient_mock.get(latest_url(), json=prices_payload())
    aioclient_mock.get(prices_url(), json=prices_payload())

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN_AUTO: True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: MUNICIPALITY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CITY_PREFIX: "Niekur"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stations"}


async def test_reauth_silent_refresh(hass, aioclient_mock):
    """An auto-token entry refreshes itself without user interaction."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(**{CONF_TOKEN: "1|EXPIRED"}),
        options=entry_options(),
    )
    entry.add_to_hass(hass)

    mock_token_discovery(aioclient_mock)
    aioclient_mock.get(validate_url(), json={"data": []})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == TOKEN


async def test_reauth_manual_token(hass, aioclient_mock):
    """A manual-token entry asks for a new token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(**{CONF_TOKEN: "1|EXPIRED", CONF_TOKEN_AUTO: False}),
        options=entry_options(),
    )
    entry.add_to_hass(hass)

    aioclient_mock.get(validate_url(), json={"data": []})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == TOKEN
    assert entry.data[CONF_TOKEN_AUTO] is False


async def _setup_entry(hass, aioclient_mock, options: dict[str, Any]):
    aioclient_mock.get(prices_url(), json=prices_payload())
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_options_all_stations_below_threshold(hass, aioclient_mock):
    """Selecting all stations saves without a confirmation step."""
    entry = await _setup_entry(hass, aioclient_mock, entry_options())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CITY_PREFIX: "Marijampolė", CONF_STATIONS_MODE: STATIONS_MODE_ALL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_STATIONS_MODE] == STATIONS_MODE_ALL

    await hass.async_block_till_done()
    assert hass.states.get("sensor.marijampole_degalines") is not None


async def test_options_all_stations_requires_confirmation(hass, aioclient_mock):
    """More than 40 stations require an explicit confirmation."""
    rows = [
        row(
            "Tinklas",
            f"Marijampolė, Gatvė {index} g. 1, 68100",
            "benzinas_95",
            "1.799",
        )
        for index in range(45)
    ]
    aioclient_mock.get(prices_url(), json=prices_payload(rows=rows))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=entry_options(prefix="Marijampolė"),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.marijampole_degalines").state == "45"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CITY_PREFIX: "Marijampolė", CONF_STATIONS_MODE: STATIONS_MODE_ALL},
    )
    assert result["step_id"] == "confirm_all"
    assert result["description_placeholders"]["count"] == "45"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONFIRM: False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "confirm_required"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONFIRM: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_STATIONS_MODE] == STATIONS_MODE_ALL


async def test_options_selected_stations(hass, aioclient_mock):
    """Only the selected stations get their own sensors."""
    entry = await _setup_entry(hass, aioclient_mock, entry_options())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CITY_PREFIX: "Marijampolė",
            CONF_STATIONS_MODE: STATIONS_MODE_SELECTED,
        },
    )
    assert result["step_id"] == "stations"
    assert result["description_placeholders"]["count"] == "4"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_STATIONS: ["Neste - Marijampolė, Vilkaviškio g. 61D, 68153"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_STATIONS] == [
        "Neste - Marijampolė, Vilkaviškio g. 61D, 68153"
    ]

    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.marijampole_neste_vilkaviskio_g_61d") is not None
    )


async def test_reconfigure_resets_city_and_stations(hass, aioclient_mock):
    """Reconfigure changes the municipality and clears the dependent options."""
    new_municipality = "Vilniaus m. sav."
    new_rows = [
        row(
            "Neste",
            "Vilnius, Gedimino g. 1, 01103",
            "benzinas_95",
            "1.850",
            municipality=new_municipality,
        )
    ]
    aioclient_mock.get(latest_url(), json=prices_payload(rows=ROWS + new_rows))
    aioclient_mock.get(prices_url(), json=prices_payload())
    aioclient_mock.get(
        prices_url(new_municipality), json=prices_payload(rows=new_rows)
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Marijampolė",
        unique_id=MUNICIPALITY.lower(),
        data=entry_data(),
        options=entry_options(
            mode=STATIONS_MODE_SELECTED,
            stations=["Neste - Marijampolė, Vilkaviškio g. 61D, 68153"],
        ),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"]["current"] == MUNICIPALITY
    selector = next(iter(result["data_schema"].schema.values()))
    assert {option["value"] for option in selector.config["options"]} == {
        MUNICIPALITY,
        new_municipality,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: new_municipality}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_MUNICIPALITY] == new_municipality
    assert entry.title == new_municipality
    assert entry.unique_id == new_municipality.lower()
    assert entry.options == {
        CONF_CITY_PREFIX: "",
        CONF_STATIONS_MODE: STATIONS_MODE_NONE,
        CONF_STATIONS: [],
    }
    # The reload fetched the new municipality; the existing entity ids are kept.
    assert hass.states.get("sensor.marijampole_degalines").state == "1"
    assert hass.states.get("sensor.marijampole_neste_vilkaviskio_g_61d") is None


async def test_reconfigure_rejects_configured_municipality(hass, aioclient_mock):
    """A municipality that already has an entry cannot be picked again."""
    new_municipality = "Vilniaus m. sav."
    aioclient_mock.get(
        latest_url(),
        json=prices_payload(
            rows=[
                *ROWS,
                row(
                    "Neste",
                    "Vilnius, Gedimino g. 1, 01103",
                    "benzinas_95",
                    "1.850",
                    municipality=new_municipality,
                ),
            ]
        ),
    )
    entry = await _setup_entry(hass, aioclient_mock, entry_options())
    MockConfigEntry(
        domain=DOMAIN,
        title="Vilnius",
        unique_id=new_municipality.lower(),
        data=entry_data(**{CONF_MUNICIPALITY: new_municipality}),
        options=entry_options(prefix=""),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: new_municipality}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_MUNICIPALITY] == MUNICIPALITY


async def test_reconfigure_aborts_without_data(hass, aioclient_mock):
    """A municipality without published prices is rejected."""
    new_municipality = "Vilniaus m. sav."
    aioclient_mock.get(
        latest_url(),
        json=prices_payload(
            rows=[
                *ROWS,
                row(
                    "Neste",
                    "Vilnius, Gedimino g. 1, 01103",
                    "benzinas_95",
                    "1.850",
                    municipality=new_municipality,
                ),
            ]
        ),
    )
    aioclient_mock.get(prices_url(new_municipality), json=prices_payload(rows=[]))
    entry = await _setup_entry(hass, aioclient_mock, entry_options())

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MUNICIPALITY: new_municipality}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_data"
    assert entry.data[CONF_MUNICIPALITY] == MUNICIPALITY
