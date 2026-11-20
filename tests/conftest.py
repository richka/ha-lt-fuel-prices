"""Global fixtures for the ENA fuel prices test suite."""

from __future__ import annotations

import sys

import pytest
import pytest_socket

pytest_plugins = "pytest_homeassistant_custom_component"

if sys.platform == "win32":
    # Home Assistant's test harness disables sockets for every test. On Windows
    # the asyncio ProactorEventLoop needs a real socket pair for its self-pipe,
    # so socket blocking makes every test fail. The tests themselves mock all
    # HTTP traffic through ``aioclient_mock``.
    pytest_socket.disable_socket = lambda *args, **kwargs: None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable the custom integration in every test."""
    yield
