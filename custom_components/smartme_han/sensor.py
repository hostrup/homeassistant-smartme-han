"""Sensor platform for Smart-me Kamstrup HAN."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, REGISTERS
from .coordinator import SmartMeDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    for key, config in REGISTERS.items():
        entities.append(SmartMeSensor(coordinator, entry, key, config))
        
    async_add_entities(entities)


class SmartMeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Smart-me sensor."""

    def __init__(
        self,
        coordinator: SmartMeDataUpdateCoordinator,
        entry: ConfigEntry,
        key: str,
        config: dict
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._config = config
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = config["name"]
        
        if device_class := config.get("device_class"):
            self._attr_device_class = device_class
            
        if state_class := config.get("state_class"):
            self._attr_state_class = state_class
            
        self._attr_native_unit_of_measurement = config.get("unit")

    @property
    def device_info(self):
        """Return device information about this Smart-me device."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.client._ip_address)},
            "name": "Smart-me Kamstrup HAN",
            "manufacturer": "Smart-me",
            "model": "Kamstrup HAN Module",
        }

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)
