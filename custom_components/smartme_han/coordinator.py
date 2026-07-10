"""DataUpdateCoordinator for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SmartMeAuthError,
    SmartMeCloudApi,
    SmartMeError,
    SmartMeModbusApi,
)
from .const import (
    AUTH_TYPE_API_KEY,
    CONF_AUTH_TYPE,
    CONF_DEVICE_ID,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SmartMeConfigEntry = ConfigEntry["SmartMeDataUpdateCoordinator"]


class SmartMeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Fetch meter data over Modbus TCP or the Smart-me cloud API."""

    config_entry: SmartMeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SmartMeConfigEntry) -> None:
        """Initialize the coordinator with the transport the entry was set up for."""
        self.api: SmartMeModbusApi | SmartMeCloudApi
        if host := entry.data.get(CONF_IP_ADDRESS):
            self.api = SmartMeModbusApi(host)
        else:
            self.api = SmartMeCloudApi(
                async_get_clientsession(hass),
                entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_API_KEY),
                dict(entry.data),
                entry.data.get(CONF_DEVICE_ID),
            )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch the current meter readings."""
        try:
            return await self.api.async_read_all()
        except SmartMeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmartMeError as err:
            raise UpdateFailed(str(err)) from err
