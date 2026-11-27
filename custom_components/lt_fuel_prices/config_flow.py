"""Config and options flow for the ENA fuel prices integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    EnaApiAuthError,
    EnaApiConnectionError,
    EnaApiError,
    async_discover_token,
    async_get_municipalities,
    async_get_prices,
    async_validate_token,
    normalize_token,
)
from .const import (
    ALL_STATIONS_WARNING_THRESHOLD,
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
from .snapshot import build_snapshot, count_stations, suggest_city_prefix

_LOGGER = logging.getLogger(__name__)

TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class EnaFuelPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration of ENA fuel prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._session = None
        self._token = ""
        self._token_auto = True
        self._municipality = ""
        self._municipalities: list[str] = []
        self._rows: list[dict[str, Any]] = []
        self._updated_at: str | None = None

    @property
    def session(self):
        """Return a shared aiohttp session."""
        if self._session is None:
            self._session = async_get_clientsession(self.hass)
        return self._session

    def _suggested_prefix(self) -> str:
        return suggest_city_prefix(self._rows)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask whether the token should be fetched automatically."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._token_auto = bool(user_input[CONF_TOKEN_AUTO])
            if not self._token_auto:
                return await self.async_step_token()
            try:
                self._token = await async_discover_token(self.session)
                self._municipalities = await async_get_municipalities(
                    self.session, self._token
                )
            except EnaApiAuthError:
                errors["base"] = "invalid_auth"
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "token_not_found"
            else:
                return await self.async_step_municipality()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_TOKEN_AUTO, default=True): bool}
            ),
            description_placeholders={
                "source_url": "https://degalukainos.ena.lt/"
            },
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a manually obtained bearer token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = normalize_token(user_input[CONF_TOKEN])
            try:
                await async_validate_token(self.session, token)
                municipalities = await async_get_municipalities(self.session, token)
            except EnaApiAuthError:
                errors["base"] = "invalid_auth"
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "unknown"
            else:
                self._token = token
                self._municipalities = municipalities
                return await self.async_step_municipality()

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            errors=errors,
        )

    async def async_step_municipality(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a municipality."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._municipality = user_input[CONF_MUNICIPALITY]
            await self.async_set_unique_id(self._municipality.lower())
            self._abort_if_unique_id_configured()

            try:
                response = await async_get_prices(
                    self.session, self._token, self._municipality
                )
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "unknown"
            else:
                if not response.rows:
                    return self.async_abort(reason="no_data")
                self._rows = response.rows
                self._updated_at = response.updated_at
                return await self.async_step_city()

        options = [
            SelectOptionDict(value=municipality, label=municipality)
            for municipality in self._municipalities
        ]
        return self.async_show_form(
            step_id="municipality",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MUNICIPALITY): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer an optional city filter based on the address prefix."""
        suggested = self._suggested_prefix()
        total, matching = count_stations(self._rows, suggested)
        errors: dict[str, str] = {}

        if user_input is not None:
            prefix = (user_input.get(CONF_CITY_PREFIX) or "").strip()
            total, matching = count_stations(self._rows, prefix)
            if matching == 0:
                errors["base"] = "no_stations"
            else:
                return self.async_create_entry(
                    title=prefix or self._municipality,
                    data={
                        CONF_TOKEN: self._token,
                        CONF_TOKEN_AUTO: self._token_auto,
                        CONF_MUNICIPALITY: self._municipality,
                    },
                    options={
                        CONF_CITY_PREFIX: prefix,
                        CONF_STATIONS_MODE: STATIONS_MODE_NONE,
                        CONF_STATIONS: [],
                    },
                )

        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(
                {vol.Optional(CONF_CITY_PREFIX, default=suggested): str}
            ),
            description_placeholders={
                "stations": str(total),
                "prefix": suggested or "—",
                "matching": str(matching),
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Try a silent token refresh before asking the user."""
        entry = self._get_reauth_entry()

        if entry.data.get(CONF_TOKEN_AUTO):
            try:
                token = await async_discover_token(self.session)
                await async_validate_token(self.session, token)
            except EnaApiError:
                _LOGGER.debug("Silent LEA token refresh failed, asking the user")
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: token}
                )

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new bearer token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = normalize_token(user_input[CONF_TOKEN])
            try:
                await async_validate_token(self.session, token)
            except EnaApiAuthError:
                errors["base"] = "invalid_auth"
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_TOKEN: token, CONF_TOKEN_AUTO: False},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): TOKEN_SELECTOR}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the municipality and reset the filters that depended on it."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if not self._municipalities:
            try:
                self._municipalities = await async_get_municipalities(
                    self.session, entry.data[CONF_TOKEN]
                )
            except EnaApiAuthError:
                errors["base"] = "invalid_auth"
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "unknown"

        if user_input is not None:
            municipality = user_input[CONF_MUNICIPALITY]
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, municipality.lower()
            )
            if existing is not None and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")

            try:
                response = await async_get_prices(
                    self.session, entry.data[CONF_TOKEN], municipality
                )
            except EnaApiAuthError:
                errors["base"] = "invalid_auth"
            except EnaApiConnectionError:
                errors["base"] = "cannot_connect"
            except EnaApiError:
                errors["base"] = "unknown"
            else:
                if not response.rows:
                    return self.async_abort(reason="no_data")
                options = {
                    CONF_CITY_PREFIX: "",
                    CONF_STATIONS_MODE: STATIONS_MODE_NONE,
                    CONF_STATIONS: [],
                }
                # The flow owns the reload: keep the update listener quiet so
                # async_update_reload_and_abort performs the single reload.
                coordinator = getattr(entry, "runtime_data", None)
                if coordinator is not None:
                    coordinator.config_snapshot = (dict(options), municipality)
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=municipality.lower(),
                    title=municipality,
                    data_updates={CONF_MUNICIPALITY: municipality},
                    options=options,
                )

        current = entry.data[CONF_MUNICIPALITY]
        options = [
            SelectOptionDict(value=municipality, label=municipality)
            for municipality in (self._municipalities or [current])
        ]
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MUNICIPALITY, default=current): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            description_placeholders={"current": current},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return EnaFuelPricesOptionsFlow()


class EnaFuelPricesOptionsFlow(OptionsFlow):
    """Options flow: city filter and monitored stations."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._mode = STATIONS_MODE_NONE
        self._prefix = ""
        self._selected: list[str] = []

    @property
    def _coordinator(self):
        return self.config_entry.runtime_data

    @property
    def _snapshot(self):
        return self._coordinator.data

    async def _async_snapshot_for_prefix(self):
        """Return a snapshot for the pending prefix, refreshing it if needed."""
        snapshot = self._snapshot
        if snapshot is None:
            return None
        if self._prefix == self.config_entry.options.get(CONF_CITY_PREFIX, ""):
            return snapshot
        try:
            response = await async_get_prices(
                async_get_clientsession(self.hass),
                self.config_entry.data[CONF_TOKEN],
                self.config_entry.data[CONF_MUNICIPALITY],
            )
        except EnaApiError as err:
            _LOGGER.debug("Could not refresh prices for the new filter: %s", err)
            return snapshot
        return build_snapshot(
            response.rows,
            municipality=self.config_entry.data[CONF_MUNICIPALITY],
            city_prefix=self._prefix,
            updated_at=response.updated_at,
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the city filter and the station entity mode."""
        snapshot = self._snapshot
        stations = list(snapshot.stations) if snapshot else []
        errors: dict[str, str] = {}

        if user_input is not None:
            self._mode = user_input[CONF_STATIONS_MODE]
            self._prefix = (user_input.get(CONF_CITY_PREFIX) or "").strip()
            self._selected = list(self.config_entry.options.get(CONF_STATIONS, []))

            if self._prefix and stations:
                _, matching = count_stations(
                    [{"address": station.address} for station in stations],
                    self._prefix,
                )
                if matching == 0:
                    errors["base"] = "no_stations"

            if not errors:
                if self._mode == STATIONS_MODE_SELECTED:
                    return await self.async_step_stations()
                if (
                    self._mode == STATIONS_MODE_ALL
                    and len(stations) > ALL_STATIONS_WARNING_THRESHOLD
                ):
                    return await self.async_step_confirm_all()
                return self._async_save([])

        current_mode = self.config_entry.options.get(
            CONF_STATIONS_MODE, STATIONS_MODE_NONE
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CITY_PREFIX,
                        default=self.config_entry.options.get(CONF_CITY_PREFIX, ""),
                    ): str,
                    vol.Required(CONF_STATIONS_MODE, default=current_mode): (
                        SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    STATIONS_MODE_NONE,
                                    STATIONS_MODE_SELECTED,
                                    STATIONS_MODE_ALL,
                                ],
                                translation_key="stations_mode",
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        )
                    ),
                }
            ),
            description_placeholders={
                "stations": str(len(stations)),
                "selected": str(
                    len(self.config_entry.options.get(CONF_STATIONS, []))
                ),
            },
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the stations that should get their own sensors."""
        if user_input is not None:
            self._selected = list(user_input.get(CONF_STATIONS, []))
            return self._async_save(self._selected)

        snapshot = await self._async_snapshot_for_prefix()
        stations = list(snapshot.stations) if snapshot else []
        options = [
            SelectOptionDict(value=station.key, label=station.label)
            for station in stations
        ]
        return self.async_show_form(
            step_id="stations",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_STATIONS, default=self._selected
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(options))},
        )

    async def async_step_confirm_all(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for confirmation before creating a sensor for every station."""
        errors: dict[str, str] = {}
        snapshot = await self._async_snapshot_for_prefix()
        count = len(snapshot.stations) if snapshot else 0

        if user_input is not None:
            if user_input.get(CONF_CONFIRM):
                return self._async_save([])
            errors["base"] = "confirm_required"

        return self.async_show_form(
            step_id="confirm_all",
            data_schema=vol.Schema({vol.Required(CONF_CONFIRM, default=False): bool}),
            description_placeholders={"count": str(count)},
            errors=errors,
        )

    def _async_save(self, selected: list[str]) -> ConfigFlowResult:
        """Store the new options."""
        return self.async_create_entry(
            title="",
            data={
                CONF_CITY_PREFIX: self._prefix,
                CONF_STATIONS_MODE: self._mode,
                CONF_STATIONS: selected if self._mode == STATIONS_MODE_SELECTED else [],
            },
        )
