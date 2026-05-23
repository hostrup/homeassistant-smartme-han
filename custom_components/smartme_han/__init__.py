"""The Smart-me Kamstrup HAN integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_API_KEY
from homeassistant.core import HomeAssistant

from .api import SmartMeApiClient
from .const import DOMAIN
from .coordinator import SmartMeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart-me Kamstrup HAN from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = SmartMeApiClient(
        api_key=entry.data[CONF_API_KEY],
        ip_address=entry.data[CONF_IP_ADDRESS]
    )

    coordinator = SmartMeDataUpdateCoordinator(hass, client)

    # Fetch initial data so we have state when entities are added
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok