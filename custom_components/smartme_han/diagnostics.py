"""Diagnostics support for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID
from .coordinator import SmartMeConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartMeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "data": coordinator.data,
    }
