"""Tests for decoding raw Modbus registers into sensor values."""

from __future__ import annotations

import struct

from custom_components.smartme_han.api import decode_registers
from custom_components.smartme_han.const import MODBUS_REGISTERS, SENSOR_DESCRIPTIONS


def _raw(**values: tuple[str, int]) -> dict[int, int]:
    """Build an address -> 16-bit word map from (struct format, raw value) pairs."""
    raw: dict[int, int] = {}
    for key, (fmt, value) in values.items():
        address = MODBUS_REGISTERS[key].address
        raw[address], raw[address + 1] = struct.unpack(">HH", struct.pack(fmt, value))
    return raw


def _full_raw(**overrides: tuple[str, int]) -> dict[int, int]:
    """Fill every register with zero, then apply the overrides."""
    defaults = {key: (register.fmt, 0) for key, register in MODBUS_REGISTERS.items()}
    return _raw(**{**defaults, **overrides})


def test_scaling_matches_the_meter_units() -> None:
    """Raw Wh, mV and cA must become kWh, V and A."""
    decoded = decode_registers(
        _full_raw(
            energy_import=(">I", 12_345_678),
            voltage_l1=(">I", 230_500),
            current_l1=(">I", 1_234),
        )
    )

    assert decoded["energy_import"] == 12345.678
    assert decoded["voltage_l1"] == 230.5
    assert decoded["current_l1"] == 12.34


def test_active_power_is_signed_so_export_reads_negative() -> None:
    """Export must survive as a negative value rather than wrapping to 4.29e9."""
    assert (
        decode_registers(_full_raw(active_power=(">i", -1234)))["active_power"] == -1234
    )
    assert (
        decode_registers(_full_raw(active_power=(">i", 4321)))["active_power"] == 4321
    )


def test_counters_are_unsigned() -> None:
    """A counter past 2^31 Wh must not flip negative."""
    decoded = decode_registers(_full_raw(energy_import=(">I", 3_000_000_000)))
    assert decoded["energy_import"] == 3_000_000.0


def test_decode_returns_every_sensor() -> None:
    """A successful poll must populate all sensors."""
    assert set(decode_registers(_full_raw())) == {d.key for d in SENSOR_DESCRIPTIONS}


def test_only_active_power_is_rescaled_from_the_cloud() -> None:
    """The cloud reports kW for power and native units for everything else."""
    factors = {d.key: d.api_factor for d in SENSOR_DESCRIPTIONS}
    assert factors.pop("active_power") == 1000
    assert set(factors.values()) == {1.0}
