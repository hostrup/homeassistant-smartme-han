"""DataUpdateCoordinator for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SmartMeAuthError,
    SmartMeCloudApi,
    SmartMeError,
    SmartMeFailoverApi,
    SmartMeModbusApi,
)
from .const import (
    AUTH_TYPE_API_KEY,
    AUTH_TYPE_BASIC,
    CONF_AUTH_TYPE,
    CONF_CLOUD_FALLBACK_ENABLED,
    CONF_DEVICE_ID,
    CONF_FALLBACK_PROBE_INTERVAL,
    DEFAULT_FALLBACK_PROBE_INTERVAL,
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
        # Options override data, so the options flow can add or change the cloud
        # fallback credentials of a locally configured meter after setup.
        settings = {**entry.data, **entry.options}
        host = settings.get(CONF_IP_ADDRESS)

        if host:
            primary: SmartMeModbusApi | SmartMeCloudApi = SmartMeModbusApi(host)
        else:
            primary = SmartMeCloudApi(
                async_get_clientsession(hass),
                settings.get(CONF_AUTH_TYPE, AUTH_TYPE_API_KEY),
                dict(settings),
                settings.get(CONF_DEVICE_ID),
            )

        self.api = SmartMeFailoverApi(
            primary,
            self._async_build_cloud_fallback(hass, settings) if host else None,
            probe_interval=float(
                settings.get(
                    CONF_FALLBACK_PROBE_INTERVAL, DEFAULT_FALLBACK_PROBE_INTERVAL
                )
            ),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @staticmethod
    def _async_build_cloud_fallback(
        hass: HomeAssistant, settings: dict[str, object]
    ) -> SmartMeCloudApi | None:
        """Build the cloud fallback for a Modbus meter, if it is configured."""
        if not settings.get(CONF_CLOUD_FALLBACK_ENABLED, True):
            return None
        auth_type = settings.get(CONF_AUTH_TYPE, AUTH_TYPE_API_KEY)
        if auth_type == AUTH_TYPE_BASIC:
            configured = bool(
                settings.get(CONF_USERNAME) and settings.get(CONF_PASSWORD)
            )
        else:
            configured = bool(settings.get(CONF_API_KEY))
        if not configured:
            return None
        return SmartMeCloudApi(
            async_get_clientsession(hass),
            auth_type,
            dict(settings),
            settings.get(CONF_DEVICE_ID),
        )

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch the current meter readings."""
        try:
            return await self.api.async_read_all()
        except SmartMeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SmartMeError as err:
            raise UpdateFailed(str(err)) from err
