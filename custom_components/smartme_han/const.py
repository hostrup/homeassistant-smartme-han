"""Constants for the Smart-me Kamstrup HAN integration."""
from datetime import timedelta

DOMAIN = "smartme_han"

# Configuration constants
CONF_IP_ADDRESS = "ip_address"
CONF_API_KEY = "api_key"

# Update intervals
UPDATE_INTERVAL = timedelta(seconds=60) # Coordinator update interval. The modbus read takes 9 * 2.5s = 22.5s. 60s total interval is safe.

# Modbus settings
MODBUS_PORT = 502
MODBUS_POLL_DELAY = 2.5  # Minimum 2 seconds, recommended 2.5s

# Register Map
# Format based on domain knowledge and POC
REGISTERS = {
    "active_power": {
        "address": 8195,
        "count": 2,
        "fmt": ">i",
        "scale": 1.0,
        "unit": "W",
        "name": "Aktuel Effekt",
        "device_class": "power",
        "state_class": "measurement"
    },
    "energy_import": {
        "address": 8267,
        "count": 2,
        "fmt": ">I",
        "scale": 0.001,
        "unit": "kWh",
        "name": "Energi Import (Total)",
        "device_class": "energy",
        "state_class": "total_increasing"
    },
    "energy_export": {
        "address": 8269,
        "count": 2,
        "fmt": ">I",
        "scale": 0.001,
        "unit": "kWh",
        "name": "Energi Eksport (Total)",
        "device_class": "energy",
        "state_class": "total_increasing"
    },
    "voltage_l1": {
        "address": 8211,
        "count": 2,
        "fmt": ">I",
        "scale": 0.001,
        "unit": "V",
        "name": "Spænding L1",
        "device_class": "voltage",
        "state_class": "measurement"
    },
    "voltage_l2": {
        "address": 8213,
        "count": 2,
        "fmt": ">I",
        "scale": 0.001,
        "unit": "V",
        "name": "Spænding L2",
        "device_class": "voltage",
        "state_class": "measurement"
    },
    "voltage_l3": {
        "address": 8215,
        "count": 2,
        "fmt": ">I",
        "scale": 0.001,
        "unit": "V",
        "name": "Spænding L3",
        "device_class": "voltage",
        "state_class": "measurement"
    },
    "current_l1": {
        "address": 8217,
        "count": 2,
        "fmt": ">I",
        "scale": 0.01,
        "unit": "A",
        "name": "Strømstyrke L1",
        "device_class": "current",
        "state_class": "measurement"
    },
    "current_l2": {
        "address": 8219,
        "count": 2,
        "fmt": ">I",
        "scale": 0.01,
        "unit": "A",
        "name": "Strømstyrke L2",
        "device_class": "current",
        "state_class": "measurement"
    },
    "current_l3": {
        "address": 8221,
        "count": 2,
        "fmt": ">I",
        "scale": 0.01,
        "unit": "A",
        "name": "Strømstyrke L3",
        "device_class": "current",
        "state_class": "measurement"
    }
}
