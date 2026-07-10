"""Tests for the pacing that keeps the meter answering.

The HAN module drops requests that arrive too close together, and drops the
first request on a socket opened too soon after the previous one closed. Both
delays were measured against the hardware; these tests pin the behaviour so a
refactor cannot quietly remove either one.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from custom_components.smartme_han import api
from custom_components.smartme_han.const import (
    MODBUS_RECONNECT_DELAY,
    MODBUS_REQUEST_DELAY,
)

# Timestamps are compared against the real clock, so allow for execution time.
TOLERANCE = 0.5


@pytest.fixture
def slept(monkeypatch):
    """Record what the gate would sleep, without actually sleeping."""
    calls: list[float] = []

    async def fake_sleep(delay):
        calls.append(delay)

    monkeypatch.setattr(api.asyncio, "sleep", fake_sleep)
    return calls


def test_first_request_does_not_wait(slept):
    """Nothing has touched the meter yet, so there is nothing to wait for."""
    asyncio.run(api._MeterGate().pace_request())
    assert slept == []


def test_first_connect_does_not_wait(slept):
    """No socket has been closed yet."""
    asyncio.run(api._MeterGate().pace_connect())
    assert slept == []


def test_request_right_after_another_waits_the_full_delay(slept):
    """A back-to-back request must wait out the inter-request delay."""
    gate = api._MeterGate()
    gate.mark_request()
    asyncio.run(gate.pace_request())
    assert slept == [pytest.approx(MODBUS_REQUEST_DELAY, abs=TOLERANCE)]


def test_connect_right_after_close_waits_the_reconnect_delay(slept):
    """A socket opened straight after a close is accepted but serves nothing."""
    gate = api._MeterGate()
    gate.mark_closed()
    asyncio.run(gate.pace_connect())
    assert slept == [pytest.approx(MODBUS_RECONNECT_DELAY, abs=TOLERANCE)]


def test_reconnect_delay_exceeds_request_delay():
    """Freeing the TCP slot takes longer than answering another request."""
    assert MODBUS_RECONNECT_DELAY > MODBUS_REQUEST_DELAY


def test_stale_timestamps_cost_nothing(slept):
    """After a full update interval of idle, neither gate should wait."""
    long_ago = time.monotonic() - 1000
    gate = api._MeterGate(last_request=long_ago, last_close=long_ago)

    asyncio.run(gate.pace_connect())
    asyncio.run(gate.pace_request())

    assert slept == []


def test_one_gate_per_meter_shared_across_clients():
    """Config-flow validation and the coordinator must pace against each other."""
    api._GATES.clear()
    try:
        first = api.SmartMeModbusApi("192.0.2.10")
        second = api.SmartMeModbusApi("192.0.2.10")
        other = api.SmartMeModbusApi("192.0.2.11")
        assert first._gate is second._gate
        assert first._gate is not other._gate
    finally:
        api._GATES.clear()
