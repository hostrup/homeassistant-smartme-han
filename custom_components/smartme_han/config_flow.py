"""Config flow for Smart-me Kamstrup HAN."""
import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_API_KEY, CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN
from .api import async_validate_api, async_validate_modbus, async_enable_modbus_via_api

_LOGGER = logging.getLogger(__name__)

class SmartMeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart-me."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._setup_data = {}

    async def async_step_user(self, user_input=None):
        """Menu to choose connection method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["api", "modbus"]
        )

    async def async_step_api(self, user_input=None):
        """Redirect to API Auth Type."""
        return await self.async_step_api_auth()

    async def async_step_modbus(self, user_input=None):
        """Redirect to Modbus Setup."""
        return await self.async_step_modbus_setup()

    async def async_step_api_auth(self, user_input=None):
        """Menu for API Auth Type."""
        return self.async_show_menu(
            step_id="api_auth_type",
            menu_options=["basic", "apikey"]
        )

    async def async_step_basic(self, user_input=None):
        """Basic Auth selected."""
        self._setup_data["auth_type"] = "basic"
        return await self.async_step_api_setup()

    async def async_step_apikey(self, user_input=None):
        """API Key selected."""
        self._setup_data["auth_type"] = "apikey"
        return await self.async_step_api_setup()

    async def async_step_api_setup(self, user_input=None):
        """Handle Cloud API credentials."""
        errors = {}
        auth_type = self._setup_data.get("auth_type", "apikey")
        
        if user_input is not None:
            try:
                device_id = await async_validate_api(self.hass, auth_type, user_input)
                
                entry_data = {**user_input, "device_id": device_id, "auth_type": auth_type}
                return self.async_create_entry(title="Smart-me Cloud API", data=entry_data)
                
            except Exception as ex:
                _LOGGER.error("API validation failed: %s", ex)
                errors["base"] = "invalid_auth"
        
        schema = {}
        if auth_type == "basic":
            schema = {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        else:
            schema = {
                vol.Required(CONF_API_KEY): str,
            }
            
        return self.async_show_form(
            step_id="api_setup",
            data_schema=vol.Schema(schema),
            errors=errors
        )

    async def async_step_modbus_setup(self, user_input=None):
        """Handle Local Modbus IP."""
        errors = {}
        if user_input is not None:
            ip = user_input[CONF_IP_ADDRESS]
            self._setup_data[CONF_IP_ADDRESS] = ip
            
            is_valid = await async_validate_modbus(self.hass, ip)
            if is_valid:
                return self.async_create_entry(title=f"Smart-me Modbus ({ip})", data=self._setup_data)
            else:
                return await self.async_step_modbus_fallback()
                
        return self.async_show_form(
            step_id="modbus_setup",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
            }),
            errors=errors
        )

    async def async_step_modbus_fallback(self, user_input=None):
        """Fallback to enable Modbus via API."""
        errors = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            ip = self._setup_data[CONF_IP_ADDRESS]
            
            try:
                device_id = await async_validate_api(self.hass, "apikey", {CONF_API_KEY: api_key})
                await async_enable_modbus_via_api(self.hass, api_key, device_id)
                await asyncio.sleep(2)
                
                is_valid = await async_validate_modbus(self.hass, ip)
                if is_valid:
                    self._setup_data[CONF_API_KEY] = api_key
                    self._setup_data["device_id"] = device_id
                    return self.async_create_entry(title=f"Smart-me Modbus ({ip})", data=self._setup_data)
                else:
                    errors["base"] = "cannot_connect"
            except Exception as ex:
                _LOGGER.error("Fallback provisioning failed: %s", ex)
                errors["base"] = "cannot_connect"
                
        return self.async_show_form(
            step_id="modbus_fallback",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is not None:
            new_data = {**entry.data, **user_input}
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")
            
        schema = {}
        if CONF_IP_ADDRESS in entry.data:
            schema[vol.Optional(CONF_IP_ADDRESS, default=entry.data[CONF_IP_ADDRESS])] = str
        if CONF_API_KEY in entry.data:
            schema[vol.Optional(CONF_API_KEY, default=entry.data[CONF_API_KEY])] = str
        if CONF_USERNAME in entry.data:
            schema[vol.Optional(CONF_USERNAME, default=entry.data[CONF_USERNAME])] = str
        if CONF_PASSWORD in entry.data:
            schema[vol.Optional(CONF_PASSWORD, default=entry.data[CONF_PASSWORD])] = str
            
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema),
            errors=errors
        )
