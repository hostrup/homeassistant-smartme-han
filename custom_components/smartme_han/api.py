"""API Client for Smart-me Kamstrup HAN."""
import logging
import struct
import time
import requests
from requests.exceptions import RequestException
from requests.auth import HTTPBasicAuth
from pymodbus.client import ModbusTcpClient
from homeassistant.core import HomeAssistant

from .const import MODBUS_PORT, MODBUS_POLL_DELAY

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.smart-me.com/api"

def _sync_validate_api(auth_type: str, credentials: dict) -> str:
    """Synchronous cloud API validation."""
    headers = {"Accept": "application/json"}
    auth = None
    if auth_type == "apikey":
        headers["Authorization"] = f"ApiKey {credentials['api_key']}"
    elif auth_type == "basic":
        auth = HTTPBasicAuth(credentials['username'], credentials['password'])
        
    response = requests.get(f"{BASE_URL}/Devices", headers=headers, auth=auth, timeout=10)
    response.raise_for_status()
    devices = response.json()
    if not devices or not isinstance(devices, list):
        raise ValueError("No devices found in Smart-me account.")
    return devices[0].get("Id")

async def async_validate_api(hass: HomeAssistant, auth_type: str, credentials: dict) -> str:
    """Validate cloud API and return Device ID."""
    return await hass.async_add_executor_job(_sync_validate_api, auth_type, credentials)

def _sync_validate_modbus(host: str) -> bool:
    """Synchronous Modbus validation."""
    client = ModbusTcpClient(host, port=MODBUS_PORT)
    if not client.connect():
        return False
    try:
        try:
            result = client.read_holding_registers(address=8195, count=2, slave=1)
        except TypeError:
            try:
                result = client.read_holding_registers(address=8195, count=2, unit=1)
            except TypeError:
                result = client.read_holding_registers(address=8195, count=2)
                
        if result.isError() or len(result.registers) < 2:
            return False
        return True
    except Exception as ex:
        _LOGGER.error("Modbus validation exception: %s", ex)
        return False
    finally:
        client.close()

async def async_validate_modbus(hass: HomeAssistant, host: str) -> bool:
    """Validate Modbus connection and read register 8195."""
    return await hass.async_add_executor_job(_sync_validate_modbus, host)

def _sync_enable_modbus_via_api(api_key: str, device_id: str) -> None:
    """Synchronous enable modbus via API."""
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Accept": "application/json"
    }
    payload = {
        "Id": device_id,
        "EnableModbusTcp": True
    }
    response = requests.post(f"{BASE_URL}/SmartMeDeviceConfiguration", headers=headers, json=payload, timeout=10)
    response.raise_for_status()

async def async_enable_modbus_via_api(hass: HomeAssistant, api_key: str, device_id: str) -> None:
    """Enable Modbus TCP on the device via the Cloud API."""
    await hass.async_add_executor_job(_sync_enable_modbus_via_api, api_key, device_id)

class SmartMeApiClient:
    """API client for Smart-me."""

    def __init__(self, api_key: str, ip_address: str) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._ip_address = ip_address
        self._base_url = BASE_URL
        self._headers = {
            "Authorization": f"ApiKey {self._api_key}",
            "Accept": "application/json"
        }

    def read_modbus_registers(self, registers_config: dict) -> dict:
        """Read all defined registers from Modbus."""
        client = ModbusTcpClient(self._ip_address, port=MODBUS_PORT)
        
        if not client.connect():
            _LOGGER.error("Failed to connect to Modbus at %s:%s", self._ip_address, MODBUS_PORT)
            return {}

        data = {}
        try:
            for key, config in registers_config.items():
                address = config["address"]
                count = config["count"]
                fmt = config["fmt"]
                scale = config["scale"]
                
                # Sleep to satisfy the strictly required polling delay
                time.sleep(MODBUS_POLL_DELAY)
                
                try:
                    # Version-independent call to read_holding_registers
                    try:
                        result = client.read_holding_registers(address=address, count=count, slave=1)
                    except TypeError:
                        try:
                            result = client.read_holding_registers(address=address, count=count, unit=1)
                        except TypeError:
                            result = client.read_holding_registers(address=address, count=count)
                            
                    if result.isError():
                        _LOGGER.error("Error reading modbus register %s at address %s", key, address)
                        continue
                        
                    packed = struct.pack('>HH', result.registers[0], result.registers[1])
                    value_32bit = struct.unpack(fmt, packed)[0]
                    
                    data[key] = round(value_32bit * scale, 3)
                    
                except Exception as ex:
                    _LOGGER.error("Exception reading modbus register %s: %s", key, ex)
                    
        except Exception as ex:
            _LOGGER.error("Unexpected error reading modbus: %s", ex)
        finally:
            client.close()
            
        return data
