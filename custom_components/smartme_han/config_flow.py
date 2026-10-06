"""Config flow for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    SmartMeAuthError,
    SmartMeCloudApi,
    SmartMeConnectionError,
    SmartMeError,
    SmartMeModbusApi,
)
from .const import (
    API_KEY_URL,
    AUTH_TYPE_API_KEY,
    AUTH_TYPE_BASIC,
    CONF_AUTH_TYPE,
    CONF_CLOUD_FALLBACK_ENABLED,
    CONF_DEVICE_ID,
    CONF_FALLBACK_PROBE_INTERVAL,
    DEFAULT_FALLBACK_PROBE_INTERVAL,
    DOMAIN,
    MAX_FALLBACK_PROBE_INTERVAL,
    MIN_FALLBACK_PROBE_INTERVAL,
)
from .coordinator import SmartMeConfigEntry

_LOGGER = logging.getLogger(__name__)

_PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

API_KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): _PASSWORD_SELECTOR})
BASIC_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(),
        vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR,
    }
)
MODBUS_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): TextSelector()})
PROBE_INTERVAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FALLBACK_PROBE_INTERVAL): NumberSelector(
            NumberSelectorConfig(
                min=MIN_FALLBACK_PROBE_INTERVAL,
                max=MAX_FALLBACK_PROBE_INTERVAL,
                step=30,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="s",
            )
        )
    }
)

# The meter needs a moment to bring port 502 up after the cloud enables it.
MODBUS_ENABLE_SETTLE_DELAY = 5


class SmartMeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart-me Kamstrup HAN."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SmartMeConfigEntry,
    ) -> SmartMeOptionsFlow:
        """Return the options flow for an existing entry."""
        return SmartMeOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick between the local and the cloud transport."""
        return self.async_show_menu(step_id="user", menu_options=["modbus", "api"])

    async def async_step_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick a cloud authentication method."""
        return self.async_show_menu(
            step_id="api", menu_options=["api_key", "api_basic"]
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the cloud API with an API key."""
        return await self._async_cloud_step(
            "api_key", API_KEY_SCHEMA, AUTH_TYPE_API_KEY, user_input
        )

    async def async_step_api_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the cloud API with basic authentication."""
        return await self._async_cloud_step(
            "api_basic", BASIC_AUTH_SCHEMA, AUTH_TYPE_BASIC, user_input
        )

    async def _async_cloud_step(
        self,
        step_id: str,
        schema: vol.Schema,
        auth_type: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate cloud credentials and create the entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = await self._async_validate_cloud(auth_type, user_input)
            except SmartMeAuthError:
                errors["base"] = "invalid_auth"
            except SmartMeConnectionError:
                errors["base"] = "cannot_connect"
            except SmartMeError:
                errors["base"] = "no_devices"
            except Exception:
                _LOGGER.exception("Unexpected error validating the Smart-me cloud API")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Smart-me Cloud API",
                    data={
                        **user_input,
                        CONF_AUTH_TYPE: auth_type,
                        CONF_DEVICE_ID: device_id,
                    },
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_modbus(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a local Modbus TCP connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_IP_ADDRESS]
            await self.async_set_unique_id(self._host)
            self._abort_if_unique_id_configured()

            try:
                await SmartMeModbusApi(self._host).async_validate()
            except SmartMeConnectionError:
                # Port 502 is disabled on the meter by default, so offer to
                # switch it on through the cloud rather than failing outright.
                return await self.async_step_modbus_fallback()
            except Exception:
                _LOGGER.exception("Unexpected error validating Modbus")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Smart-me Modbus ({self._host})",
                    data={CONF_IP_ADDRESS: self._host},
                )

        return self.async_show_form(
            step_id="modbus", data_schema=MODBUS_SCHEMA, errors=errors
        )

    async def async_step_modbus_fallback(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable Modbus TCP through the cloud, then retry the local connection."""
        assert self._host is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                cloud = SmartMeCloudApi(session, AUTH_TYPE_API_KEY, user_input)
                device_id = await cloud.async_get_first_device_id()
                await cloud.async_enable_modbus_tcp(device_id)
                await asyncio.sleep(MODBUS_ENABLE_SETTLE_DELAY)
                await SmartMeModbusApi(self._host).async_validate()
            except SmartMeAuthError:
                errors["base"] = "invalid_auth"
            except SmartMeConnectionError:
                errors["base"] = "cannot_connect"
            except SmartMeError:
                errors["base"] = "no_devices"
            except Exception:
                _LOGGER.exception("Unexpected error enabling Modbus via the cloud")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Smart-me Modbus ({self._host})",
                    data={
                        CONF_IP_ADDRESS: self._host,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_DEVICE_ID: device_id,
                    },
                )

        return self.async_show_form(
            step_id="modbus_fallback", data_schema=API_KEY_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle credentials that stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for fresh credentials."""
        entry = self._get_reauth_entry()
        auth_type = entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_API_KEY)
        schema = BASIC_AUTH_SCHEMA if auth_type == AUTH_TYPE_BASIC else API_KEY_SCHEMA
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = await self._async_validate_cloud(auth_type, user_input)
            except SmartMeAuthError:
                errors["base"] = "invalid_auth"
            except SmartMeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                # New credentials must still lead to the meter this entry tracks.
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or credentials of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if CONF_IP_ADDRESS in entry.data:
            schema = MODBUS_SCHEMA
        elif entry.data.get(CONF_AUTH_TYPE) == AUTH_TYPE_BASIC:
            schema = BASIC_AUTH_SCHEMA
        else:
            schema = API_KEY_SCHEMA

        if user_input is not None:
            try:
                if host := user_input.get(CONF_IP_ADDRESS):
                    await SmartMeModbusApi(host).async_validate()
                    unique_id = host
                else:
                    unique_id = await self._async_validate_cloud(
                        entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_API_KEY), user_input
                    )
            except SmartMeAuthError:
                errors["base"] = "invalid_auth"
            except SmartMeConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfiguration")
                errors["base"] = "unknown"
            else:
                if not host:
                    # Changing an address is expected; swapping accounts is not.
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data_updates=user_input
                )

        # Prefill the address, but never echo stored credentials back to the form.
        suggested = (
            {CONF_IP_ADDRESS: entry.data[CONF_IP_ADDRESS]}
            if CONF_IP_ADDRESS in entry.data
            else {}
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    async def _async_validate_cloud(
        self, auth_type: str, credentials: dict[str, Any]
    ) -> str:
        """Return the device ID the credentials give access to."""
        api = SmartMeCloudApi(
            async_get_clientsession(self.hass), auth_type, credentials
        )
        return await api.async_get_first_device_id()


class SmartMeOptionsFlow(OptionsFlow):
    """Configure the cloud fallback of a locally configured (Modbus) meter."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the cloud-fallback menu."""
        if CONF_IP_ADDRESS not in self.config_entry.data:
            # The cloud API is already the primary transport; there is nothing
            # to fall back from.
            return self.async_abort(reason="options_not_supported")
        return self.async_show_menu(
            step_id="init",
            menu_options=["api_key", "api_basic", "probe_interval", "disable"],
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store a Smart-me API key to use as the cloud fallback."""
        return await self._async_save_credentials(
            "api_key", API_KEY_SCHEMA, AUTH_TYPE_API_KEY, user_input
        )

    async def async_step_api_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store Smart-me account credentials to use as the cloud fallback."""
        return await self._async_save_credentials(
            "api_basic", BASIC_AUTH_SCHEMA, AUTH_TYPE_BASIC, user_input
        )

    async def _async_save_credentials(
        self,
        step_id: str,
        schema: vol.Schema,
        auth_type: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate fallback credentials and store them in the entry options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = await self._async_validate_cloud(auth_type, user_input)
            except SmartMeAuthError:
                errors["base"] = "invalid_auth"
            except SmartMeConnectionError:
                errors["base"] = "cannot_connect"
            except SmartMeError:
                errors["base"] = "no_devices"
            except Exception:
                _LOGGER.exception("Unexpected error validating the cloud fallback")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        **user_input,
                        CONF_AUTH_TYPE: auth_type,
                        CONF_DEVICE_ID: device_id,
                        CONF_CLOUD_FALLBACK_ENABLED: True,
                    }
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"api_key_url": API_KEY_URL},
        )

    async def async_step_probe_interval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set how often the local link is probed for recovery."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )

        current = self.config_entry.options.get(
            CONF_FALLBACK_PROBE_INTERVAL, DEFAULT_FALLBACK_PROBE_INTERVAL
        )
        return self.async_show_form(
            step_id="probe_interval",
            data_schema=self.add_suggested_values_to_schema(
                PROBE_INTERVAL_SCHEMA, {CONF_FALLBACK_PROBE_INTERVAL: current}
            ),
        )

    async def async_step_disable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Turn the cloud fallback off."""
        if user_input is not None:
            options = dict(self.config_entry.options)
            options[CONF_CLOUD_FALLBACK_ENABLED] = False
            for key in (CONF_API_KEY, CONF_USERNAME, CONF_PASSWORD):
                options.pop(key, None)
            return self.async_create_entry(data=options)

        return self.async_show_form(step_id="disable", data_schema=vol.Schema({}))

    async def _async_validate_cloud(
        self, auth_type: str, credentials: dict[str, Any]
    ) -> str:
        """Return the device ID the given fallback credentials give access to."""
        api = SmartMeCloudApi(
            async_get_clientsession(self.hass), auth_type, credentials
        )
        return await api.async_get_first_device_id()
