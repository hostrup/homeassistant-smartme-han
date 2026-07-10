"""Tests for the register map and the block layout derived from it."""

from __future__ import annotations

import pytest

from custom_components.smartme_han.const import (
    MODBUS_BLOCKS,
    MODBUS_REGISTERS,
    SENSOR_DESCRIPTIONS,
)


def test_every_register_is_covered_by_exactly_one_block() -> None:
    """Batching must not silently drop or duplicate a register."""
    covered: list[int] = []
    for block in MODBUS_BLOCKS:
        covered.extend(range(block.start, block.start + block.count))

    assert len(covered) == len(set(covered)), "blocks overlap"

    for key, register in MODBUS_REGISTERS.items():
        assert register.address in covered, f"{key}: low word not covered"
        assert register.address + 1 in covered, f"{key}: high word not covered"


def test_blocks_contain_no_unused_registers() -> None:
    """Reading registers we never decode wastes bytes on a slow link."""
    used = {
        address
        for register in MODBUS_REGISTERS.values()
        for address in (register.address, register.address + 1)
    }
    covered = {
        address
        for block in MODBUS_BLOCKS
        for address in range(block.start, block.start + block.count)
    }
    assert covered == used


def test_one_block_per_contiguous_run() -> None:
    """The poll takes 2.5 s per extra request, so blocks must be maximal."""
    assert len(MODBUS_BLOCKS) == 3


def test_sensor_keys_match_register_keys() -> None:
    """Every sensor must be readable over both transports."""
    assert {d.key for d in SENSOR_DESCRIPTIONS} == set(MODBUS_REGISTERS)


@pytest.mark.parametrize("description", SENSOR_DESCRIPTIONS, ids=lambda d: d.key)
def test_sensor_descriptions_are_translatable(description) -> None:
    """has_entity_name requires a translation key rather than a literal name."""
    assert description.translation_key == description.key
    assert description.name is None or description.name is not description.key
