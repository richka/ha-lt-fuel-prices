"""Entity id ownership tests.

The integration used to assign ``entity_id`` directly, bypassing the entity
registry. It now only suggests an object id; the registry owns it afterwards.
"""

from __future__ import annotations

import re
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lt_fuel_prices.const import DOMAIN
from tests.helpers import (
    MUNICIPALITY,
    entry_data,
    entry_options,
    prices_payload,
    prices_url,
)

COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "lt_fuel_prices"
STATIONS_ENTITY = "sensor.marijampole_degalines"


def test_no_direct_entity_id_assignment() -> None:
    """The registry, not the integration, owns the entity id."""
    pattern = re.compile(r"\bentity_id\s*=")
    for name in ("entity.py", "sensor.py", "binary_sensor.py"):
        source = (COMPONENT_DIR / name).read_text(encoding="utf-8")
        assert pattern.search(source) is None, f"{name} assigns entity_id directly"


async def test_user_renamed_entity_keeps_its_id(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """A user rename survives a reload; the registry owns the id."""
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

    registry = er.async_get(hass)
    registry.async_update_entity(
        STATIONS_ENTITY, new_entity_id="sensor.mano_degalines"
    )

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mano_degalines") is not None
    assert hass.states.get(STATIONS_ENTITY) is None
