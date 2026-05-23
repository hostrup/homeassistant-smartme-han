"""API Client for Smart-me Kamstrup HAN."""
import logging
import struct
import time
import requests
from requests.exceptions import RequestException
from pymodbus.client import ModbusTcpClient

from .const import MODBUS_PORT, MODBUS_POLL_DELAY

_LOGGER = logging.getLogger(__name__)

class SmartMeApiClient:
    """API client for Smart-me."""

    def __init__(self, api_key: str, ip_address: str) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._ip_address = ip_address
        self._base_url = "https://api.smart-me.com/api"
        self._headers = {
            "Authorization": f"ApiKey {self._api_key}",
            "Accept": "application/json"
        }

    def get_device_id(self) -> str:
        """Get the device ID from the Smart-me Cloud API."""
        response = requests.get(f"{self._base_url}/Devices", headers=self._headers, timeout=10)
        response.raise_for_status()
        devices = response.json()
        if not devices or not isinstance(devices, list):
            raise ValueError("No devices found in Smart-me account.")
        return devices[0].get("Id")

    def enable_modbus_tcp(self, device_id: str) -> None:
        """Enable Modbus TCP on the device via the Cloud API."""
        payload = {
            "Id": device_id,
            "EnableModbusTcp": True
        }
        response = requests.post(
            f"{self._base_url}/SmartMeDeviceConfiguration",
            headers=self._headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

    def test_modbus_connection(self) -> bool:
        """Test Modbus connection to the local device."""
        client = ModbusTcpClient(self._ip_address, port=MODBUS_PORT)
        connected = client.connect()
        if connected:
            client.close()
        return connected

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
                
                # Sleep to satisfy the strictly required polling delay (e.g. 2.5s)
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
                        
                    # Pack two 16-bit registers as Big Endian bytes, then unpack as 32-bit int
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
