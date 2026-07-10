"""Constants for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)

DOMAIN: Final = "smartme_han"

CONF_AUTH_TYPE: Final = "auth_type"
CONF_DEVICE_ID: Final = "device_id"

AUTH_TYPE_API_KEY: Final = "apikey"
AUTH_TYPE_BASIC: Final = "basic"

API_BASE_URL: Final = "https://api.smart-me.com/api"
API_TIMEOUT: Final = 10

MODBUS_PORT: Final = 502

# The meter answers in well under 200 ms when it answers at all, so a short
# timeout costs nothing and makes a dropped request cheap to detect.
MODBUS_TIMEOUT: Final = 3

# pymodbus retries immediately, which the meter would ignore. We retry
# ourselves so that every attempt observes MODBUS_REQUEST_DELAY. The meter
# drops the occasional request even when nothing else is talking to it.
MODBUS_RETRIES: Final = 0
MODBUS_BLOCK_ATTEMPTS: Final = 3

# The HAN module silently drops any request that arrives less than ~2.0 s after
# the previous one. Measured against the hardware: 0.3 s is dropped, 2.5 s is
# answered. The vendor recommends 2.5 s.
MODBUS_REQUEST_DELAY: Final = 2.5

# The module also needs time to release its single TCP slot. Measured: after
# closing a socket, a new one's first request is dropped at 2.5 s, 5 s and 8 s,
# but answered at 12 s. Polling leaves ~54 s of idle, so this costs nothing in
# steady state -- only when setup validates and then immediately polls.
MODBUS_RECONNECT_DELAY: Final = 12

# Upper bound for one full poll, so a wedged meter cannot stall the coordinator.
# A healthy poll takes ~5.5 s; this leaves room for every block to retry.
MODBUS_READ_TIMEOUT: Final = 60

# The cloud API rate-limits continuous polling below 30 s.
UPDATE_INTERVAL: Final = timedelta(seconds=60)


@dataclass(frozen=True, kw_only=True)
class SmartMeSensorEntityDescription(SensorEntityDescription):
    """Describes a Smart-me sensor and how the cloud API exposes it."""

    api_field: str
    # Cloud values arrive in the meter's native units; only power needs kW -> W.
    api_factor: float = 1.0


@dataclass(frozen=True)
class ModbusRegister:
    """A 32-bit value spread over two consecutive holding registers."""

    address: int
    fmt: str
    scale: float


@dataclass(frozen=True)
class ModbusBlock:
    """A contiguous run of holding registers read in a single request."""

    start: int
    count: int


SENSOR_DESCRIPTIONS: Final[tuple[SmartMeSensorEntityDescription, ...]] = (
    SmartMeSensorEntityDescription(
        key="active_power",
        translation_key="active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        api_field="ActivePower",
        api_factor=1000,
    ),
    SmartMeSensorEntityDescription(
        key="energy_import",
        translation_key="energy_import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        api_field="CounterReadingImport",
    ),
    SmartMeSensorEntityDescription(
        key="energy_export",
        translation_key="energy_export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        api_field="CounterReadingExport",
    ),
    *(
        SmartMeSensorEntityDescription(
            key=f"voltage_l{phase}",
            translation_key=f"voltage_l{phase}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=1,
            api_field=f"VoltageL{phase}",
        )
        for phase in (1, 2, 3)
    ),
    *(
        SmartMeSensorEntityDescription(
            key=f"current_l{phase}",
            translation_key=f"current_l{phase}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            api_field=f"CurrentL{phase}",
        )
        for phase in (1, 2, 3)
    ),
)

# Signed for active power so export shows up as a negative value; unsigned elsewhere.
MODBUS_REGISTERS: Final[dict[str, ModbusRegister]] = {
    "active_power": ModbusRegister(8195, ">i", 1.0),
    "energy_import": ModbusRegister(8267, ">I", 0.001),
    "energy_export": ModbusRegister(8269, ">I", 0.001),
    "voltage_l1": ModbusRegister(8211, ">I", 0.001),
    "voltage_l2": ModbusRegister(8213, ">I", 0.001),
    "voltage_l3": ModbusRegister(8215, ">I", 0.001),
    "current_l1": ModbusRegister(8217, ">I", 0.01),
    "current_l2": ModbusRegister(8219, ">I", 0.01),
    "current_l3": ModbusRegister(8221, ">I", 0.01),
}

# Each block is one Modbus request. Because the meter enforces a delay between
# requests rather than between registers, grouping the nine values into three
# contiguous blocks is what keeps a full poll near 5 s instead of 23 s.
MODBUS_BLOCKS: Final[tuple[ModbusBlock, ...]] = (
    ModbusBlock(8195, 2),  # active power
    ModbusBlock(8211, 12),  # voltage L1-L3, current L1-L3
    ModbusBlock(8267, 4),  # energy import, energy export
)
