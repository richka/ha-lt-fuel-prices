"""Platform-level quality-scale compliance tests."""

from __future__ import annotations

from custom_components.lt_fuel_prices import binary_sensor, sensor


def test_parallel_updates_disabled() -> None:
    """All state comes from the coordinator; entities never poll on their own."""
    assert sensor.PARALLEL_UPDATES == 0
    assert binary_sensor.PARALLEL_UPDATES == 0
