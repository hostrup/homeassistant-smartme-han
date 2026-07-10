"""API clients for the Smart-me Kamstrup HAN integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
import struct
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import aiohttp
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    API_BASE_URL,
    API_TIMEOUT,
    AUTH_TYPE_BASIC,
    MODBUS_BLOCK_ATTEMPTS,
    MODBUS_BLOCKS,
    MODBUS_PORT,
    MODBUS_READ_TIMEOUT,
    MODBUS_RECONNECT_DELAY,
    MODBUS_REGISTERS,
    MODBUS_REQUEST_DELAY,
    MODBUS_RETRIES,
    MODBUS_TIMEOUT,
    SENSOR_DESCRIPTIONS,
    ModbusBlock,
)

_LOGGER = logging.getLogger(__name__)

# pymodbus renamed the unit-id argument from `slave` to `device_id` in 3.11.
# Resolve the name once instead of probing it with TypeError on every call.
_UNIT_ID_KWARG: Final = (
    "device_id"
    if "device_id"
    in inspect.signature(AsyncModbusTcpClient.read_holding_registers).parameters
    else "slave"
)
_MODBUS_UNIT_ID: Final = 1


class SmartMeError(Exception):
    """Base error for the Smart-me integration."""


class SmartMeConnectionError(SmartMeError):
    """The meter or the cloud API could not be reached."""


class SmartMeAuthError(SmartMeError):
    """The supplied credentials were rejected."""


@dataclass
class _MeterGate:
    """Serialises access to one meter and paces what we send it.

    The HAN module needs breathing room in two independent ways, and neither is
    a property of a single connection: it drops requests that follow each other
    too closely, and it needs even longer to free its one TCP slot after a
    socket closes. Both therefore have to be tracked per meter, outliving any
    client instance -- config flow validation and the first poll are different
    objects talking to the same hardware.
    """

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_request: float | None = None
    last_close: float | None = None

    async def pace_request(self) -> None:
        """Sleep until the meter will answer another request."""
        await self._sleep_until(self.last_request, MODBUS_REQUEST_DELAY)

    async def pace_connect(self) -> None:
        """Sleep until the meter will serve a newly opened socket."""
        await self._sleep_until(self.last_close, MODBUS_RECONNECT_DELAY)

    def mark_request(self) -> None:
        """Record that a request has just been made."""
        self.last_request = time.monotonic()

    def mark_closed(self) -> None:
        """Record that the connection has just been closed."""
        self.last_close = time.monotonic()

    @staticmethod
    async def _sleep_until(since: float | None, delay: float) -> None:
        if since is None:
            return
        remaining = delay - (time.monotonic() - since)
        if remaining > 0:
            await asyncio.sleep(remaining)


_GATES: Final[dict[str, _MeterGate]] = {}


def _gate(host: str) -> _MeterGate:
    """Return the shared gate for a meter, creating it on first use."""
    return _GATES.setdefault(host, _MeterGate())


def decode_registers(raw: dict[int, int]) -> dict[str, float]:
    """Turn raw 16-bit holding registers into scaled sensor values."""
    values: dict[str, float] = {}
    for key, register in MODBUS_REGISTERS.items():
        packed = struct.pack(">HH", raw[register.address], raw[register.address + 1])
        values[key] = round(struct.unpack(register.fmt, packed)[0] * register.scale, 3)
    return values


class SmartMeModbusApi:
    """Read the meter over local Modbus TCP."""

    def __init__(self, host: str) -> None:
        """Initialize the Modbus client."""
        self.host = host
        # Shared with any other client for the same meter: the module accepts
        # one TCP connection at a time and paces requests across connections.
        self._gate = _gate(host)

    @property
    def device_identifier(self) -> str:
        """Return a stable identifier for the device registry."""
        return self.host

    async def async_validate(self) -> None:
        """Raise SmartMeConnectionError unless the meter answers a single read."""
        await self._async_read(MODBUS_BLOCKS[:1])

    async def async_read_all(self) -> dict[str, float]:
        """Read every register block and return scaled values."""
        return decode_registers(await self._async_read(MODBUS_BLOCKS))

    async def _async_read(self, blocks: Sequence[ModbusBlock]) -> dict[int, int]:
        """Read the given blocks into an address -> raw value map."""
        async with self._gate.lock:
            try:
                async with asyncio.timeout(MODBUS_READ_TIMEOUT):
                    return await self._async_read_blocks(blocks)
            except TimeoutError as err:
                raise SmartMeConnectionError(
                    f"Timed out reading Modbus from {self.host}"
                ) from err
            except ModbusException as err:
                raise SmartMeConnectionError(f"Modbus error: {err}") from err

    async def _async_read_blocks(self, blocks: Sequence[ModbusBlock]) -> dict[int, int]:
        """Issue one Modbus request per block, honouring the inter-request delay.

        The connection is opened per poll and closed again: the meter accepts a
        single TCP client at a time, and holding it open through the idle time
        between polls would lock out every other tool the user owns. With a full
        update interval of idle in between, reconnecting costs nothing.
        """
        await self._gate.pace_connect()
        await self._gate.pace_request()

        client = AsyncModbusTcpClient(
            self.host,
            port=MODBUS_PORT,
            timeout=MODBUS_TIMEOUT,
            retries=MODBUS_RETRIES,
            # Never 0: that intermittently leaves pymodbus reporting a
            # connection that carries no requests at all.
            reconnect_delay=MODBUS_REQUEST_DELAY,
        )
        if not await client.connect():
            raise SmartMeConnectionError(
                f"Could not connect to Modbus at {self.host}:{MODBUS_PORT}"
            )

        raw: dict[int, int] = {}
        try:
            for block in blocks:
                registers = await self._async_read_block(client, block)
                for offset, value in enumerate(registers):
                    raw[block.start + offset] = value
        finally:
            client.close()
            self._gate.mark_closed()

        return raw

    async def _async_read_block(
        self, client: AsyncModbusTcpClient, block: ModbusBlock
    ) -> list[int]:
        """Read one block, retrying because the meter drops occasional requests.

        The module drops the occasional request even when nothing else is
        talking to it. Retrying a block costs one extra delay; failing the poll
        would cost a whole update cycle.
        """
        failure = "not attempted"

        for attempt in range(1, MODBUS_BLOCK_ATTEMPTS + 1):
            # A no-op on the first attempt of the first block, since the caller
            # already paced before opening the connection.
            await self._gate.pace_request()
            try:
                result = await client.read_holding_registers(
                    block.start,
                    count=block.count,
                    **{_UNIT_ID_KWARG: _MODBUS_UNIT_ID},
                )
            except ModbusException as err:
                failure = str(err)
            else:
                if result.isError():
                    failure = str(result)
                elif len(result.registers) != block.count:
                    failure = f"got {len(result.registers)} of {block.count} registers"
                else:
                    return result.registers
            finally:
                self._gate.mark_request()

            _LOGGER.debug(
                "Modbus read at %s failed (attempt %s/%s): %s",
                block.start,
                attempt,
                MODBUS_BLOCK_ATTEMPTS,
                failure,
            )

        raise SmartMeConnectionError(
            f"Modbus read failed at address {block.start} after "
            f"{MODBUS_BLOCK_ATTEMPTS} attempts: {failure}"
        )


class SmartMeCloudApi:
    """Read the meter through the Smart-me cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth_type: str,
        credentials: dict[str, Any],
        device_id: str | None = None,
    ) -> None:
        """Initialize the cloud client."""
        self.device_id = device_id
        self._session = session
        self._headers = {"Accept": "application/json"}
        self._auth: aiohttp.BasicAuth | None = None

        if auth_type == AUTH_TYPE_BASIC:
            self._auth = aiohttp.BasicAuth(
                credentials["username"], credentials["password"]
            )
        else:
            self._headers["Authorization"] = f"ApiKey {credentials['api_key']}"

    @property
    def device_identifier(self) -> str:
        """Return a stable identifier for the device registry."""
        if self.device_id is None:
            raise SmartMeError("Missing Smart-me device ID; reconfigure the entry")
        return self.device_id

    async def _async_request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform a request and normalise transport and auth failures."""
        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=self._headers,
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                **kwargs,
            ) as response:
                if response.status in (401, 403):
                    raise SmartMeAuthError("Smart-me rejected the credentials")
                response.raise_for_status()
                if method == "GET":
                    return await response.json()
                return None
        except aiohttp.ClientError as err:
            raise SmartMeConnectionError(f"Smart-me API error: {err}") from err
        except TimeoutError as err:
            raise SmartMeConnectionError("Smart-me API timed out") from err

    async def async_get_first_device_id(self) -> str:
        """Return the ID of the first device on the account."""
        devices = await self._async_request("GET", "/Devices")
        if not isinstance(devices, list) or not devices:
            raise SmartMeError("No devices found in the Smart-me account")

        device_id = devices[0].get("Id")
        if not device_id:
            raise SmartMeError("Smart-me returned a device without an ID")
        return device_id

    async def async_enable_modbus_tcp(self, device_id: str) -> None:
        """Ask Smart-me to enable the meter's Modbus TCP port."""
        await self._async_request(
            "POST",
            "/SmartMeDeviceConfiguration",
            json={"Id": device_id, "EnableModbusTcp": True},
        )

    async def async_read_all(self) -> dict[str, float]:
        """Read every sensor value from the cloud API."""
        raw = await self._async_request("GET", f"/Devices/{self.device_identifier}")
        # A meter may omit fields it cannot measure, e.g. L2/L3 on a single phase.
        values = {
            description.key: raw[description.api_field] * description.api_factor
            for description in SENSOR_DESCRIPTIONS
            if raw.get(description.api_field) is not None
        }
        if not values:
            raise SmartMeError("Smart-me returned no usable measurements")
        return values
