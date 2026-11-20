"""Async client for the public LEA (ENA) fuel price API.

The API is the same one used by the official map at https://degalukainos.ena.lt/.
Authentication uses a bearer token that the LEA frontend embeds in its public
JavaScript bundle, so it can be discovered (and refreshed) automatically.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_BASE_URL, REQUEST_TIMEOUT, WEB_URL

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = ClientTimeout(total=REQUEST_TIMEOUT)
_TOKEN_RE = re.compile(r'token:\s*"([^"]+)"')
_INDEX_RE = re.compile(r"(?:\./)?assets/(index-[A-Za-z0-9_\-]+\.js)")
_CHUNK_RE = re.compile(r"(?:\./)?(FuelPriceSiteApp-[A-Za-z0-9_\-]+\.js)")


class EnaApiError(Exception):
    """Base error for the ENA API."""


class EnaApiAuthError(EnaApiError):
    """The API rejected the bearer token."""


class EnaApiConnectionError(EnaApiError):
    """The API could not be reached or returned an unexpected payload."""


@dataclass(frozen=True, slots=True)
class PricesResponse:
    """Parsed response of the prices endpoint."""

    rows: list[dict[str, Any]]
    updated_at: str | None


def normalize_token(token: str) -> str:
    """Return a bare token, accepting an optional ``Bearer`` prefix."""
    token = (token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


async def async_discover_token(session: ClientSession) -> str:
    """Extract the current bearer token from the public LEA web app."""
    try:
        index_html = await _async_get_text(session, f"{WEB_URL}/")
        index_match = _INDEX_RE.search(index_html)
        if index_match is None:
            raise EnaApiError("Index bundle not found on the web app page")

        index_js = await _async_get_text(
            session, f"{WEB_URL}/assets/{index_match.group(1)}"
        )
        chunk_match = _CHUNK_RE.search(index_js)
        if chunk_match is None:
            raise EnaApiError("Application chunk not found in the index bundle")

        app_js = await _async_get_text(
            session, f"{WEB_URL}/assets/{chunk_match.group(1)}"
        )
    except (ClientError, TimeoutError) as err:
        raise EnaApiConnectionError(str(err)) from err

    token_match = _TOKEN_RE.search(app_js)
    if token_match is None:
        raise EnaApiError("Bearer token not found in the application chunk")

    return normalize_token(token_match.group(1))


async def async_validate_token(session: ClientSession, token: str) -> None:
    """Check that the token is accepted, using a very small request."""
    await _async_get_json(
        session, f"{API_BASE_URL}/read/prices", token, params={"per_page": 1}
    )


async def async_get_municipalities(
    session: ClientSession, token: str
) -> list[str]:
    """Return all municipalities known to the API."""
    payload = await _async_get_json(
        session, f"{API_BASE_URL}/read/prices/latest", token
    )
    rows = payload.get("data") or []
    return sorted(
        {
            str(row["municipality"])
            for row in rows
            if isinstance(row, dict) and row.get("municipality")
        }
    )


async def async_get_prices(
    session: ClientSession, token: str, municipality: str
) -> PricesResponse:
    """Return the latest price rows for one municipality."""
    payload = await _async_get_json(
        session,
        f"{API_BASE_URL}/read/prices",
        token,
        params={"municipality": municipality},
    )
    data = payload.get("data")
    if not isinstance(data, list):
        raise EnaApiConnectionError("Unexpected payload: 'data' is not a list")
    updated_at = payload.get("last_updated")
    return PricesResponse(
        rows=[row for row in data if isinstance(row, dict)],
        updated_at=str(updated_at) if updated_at else None,
    )


async def _async_get_text(session: ClientSession, url: str) -> str:
    async with session.get(url, timeout=_TIMEOUT) as response:
        response.raise_for_status()
        return await response.text()


async def _async_get_json(
    session: ClientSession,
    url: str,
    token: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {normalize_token(token)}",
        "Accept": "application/json",
    }
    try:
        async with session.get(
            url, headers=headers, params=params, timeout=_TIMEOUT
        ) as response:
            if response.status in (401, 403):
                raise EnaApiAuthError(f"HTTP {response.status}")
            response.raise_for_status()
            payload = await response.json(content_type=None)
    except EnaApiError:
        raise
    except (ClientError, TimeoutError) as err:
        raise EnaApiConnectionError(str(err)) from err
    except ValueError as err:
        raise EnaApiConnectionError(f"Invalid JSON response: {err}") from err

    if not isinstance(payload, dict):
        raise EnaApiConnectionError("Unexpected payload: not a JSON object")
    return payload
