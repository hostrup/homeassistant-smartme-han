"""DataUpdateCoordinator for Smart-me Kamstrup HAN."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartMeApiClient
from .const import DOMAIN, UPDATE_INTERVAL, REGISTERS

_LOGGER = logging.getLogger(__name__)

class SmartMeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Smart-me data."""

    def __init__(self, hass: HomeAssistant, client: SmartMeApiClient) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Modbus."""
        try:
            # Run the synchronous modbus reads in an executor
            # This will take ~22.5 seconds due to the strict 2.5s polling delay per register
            data = await self.hass.async_add_executor_job(
                self.client.read_modbus_registers, REGISTERS
            )
            
            if not data:
                raise UpdateFailed("Failed to fetch data from Modbus")
                
            return data
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}")
