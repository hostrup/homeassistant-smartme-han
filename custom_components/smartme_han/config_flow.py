"""Config flow for Smart-me Kamstrup HAN."""
import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .api import SmartMeApiClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_API_KEY): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart-me."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            client = SmartMeApiClient(
                api_key=user_input[CONF_API_KEY],
                ip_address=user_input[CONF_IP_ADDRESS]
            )

            try:
                # Validering 1: Kald cloud-valideringen og udtræk device_id
                device_id = await self.hass.async_add_executor_job(client.get_device_id)
                
                # Provisionering: Kald enable_modbus_tcp med det udtrukne device_id
                await self.hass.async_add_executor_job(client.enable_modbus_tcp, device_id)
                
                # Delay: Indsæt await asyncio.sleep(2) for at lade hardwaren åbne port 502
                await asyncio.sleep(2)
                
                # Validering 2: Udfør den lokale Modbus-test via IP-adressen
                modbus_ok = await self.hass.async_add_executor_job(client.test_modbus_connection)
                if not modbus_ok:
                    errors["base"] = "cannot_connect_modbus"
                else:
                    # Entry Creation: Inkludér device_id i integrationens data dict
                    entry_data = {**user_input, "device_id": device_id}
                    return self.async_create_entry(
                        title=f"Smart-me ({user_input[CONF_IP_ADDRESS]})", 
                        data=entry_data
                    )
            except Exception as ex:
                _LOGGER.error("Cloud validation or provisioning failed: %s", ex)
                errors["base"] = "cannot_connect_cloud"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )
