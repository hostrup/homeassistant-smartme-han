"""Sensor platform for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_DESCRIPTIONS, SmartMeSensorEntityDescription
from .coordinator import SmartMeConfigEntry, SmartMeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartMeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smart-me sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SmartMeSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class SmartMeSensor(CoordinatorEntity[SmartMeDataUpdateCoordinator], SensorEntity):
    """A single reading from the Smart-me Kamstrup HAN module."""

    _attr_has_entity_name = True
    entity_description: SmartMeSensorEntityDescription

    def __init__(
        self,
        coordinator: SmartMeDataUpdateCoordinator,
        description: SmartMeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.api.device_identifier)},
            manufacturer="Smart-me",
            model="Kamstrup HAN Module",
            name="Smart-me Kamstrup HAN",
            configuration_url="https://portalweb.smart-me.com",
        )

    @property
    def available(self) -> bool:
        """Return whether the last poll produced a value for this sensor."""
        return (
            super().available and self.entity_description.key in self.coordinator.data
        )

    @property
    def native_value(self) -> float | None:
        """Return the current reading."""
        return self.coordinator.data.get(self.entity_description.key)
