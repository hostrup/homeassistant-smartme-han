"""Tests for the Modbus to cloud failover and auto-heal behaviour.

The HAN module's Modbus TCP port occasionally stops answering while the Smart-me
cloud API keeps working. These tests pin the failover state machine: when the
local link trips, the cloud takes over, and the local link is probed at a fixed
interval so the meter is used again the moment it recovers.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.smartme_han.api import (
    SmartMeConnectionError,
    SmartMeFailoverApi,
)
from custom_components.smartme_han.const import (
    DEFAULT_FALLBACK_PROBE_INTERVAL,
    FALLBACK_FAILURE_THRESHOLD,
)


class FakeTransport:
    """A transport that answers or fails on demand and counts its calls."""

    def __init__(self, name: str, *, failing: bool = False) -> None:
        """Initialize the fake transport."""
        self.name = name
        self.failing = failing
        self.calls = 0

    @property
    def device_identifier(self) -> str:
        """Return the identifier used for the device registry."""
        return self.name

    async def async_read_all(self) -> dict[str, float]:
        """Return one value, or fail, and record that a read was attempted."""
        self.calls += 1
        if self.failing:
            raise SmartMeConnectionError(f"{self.name} is down")
        return {"active_power": float(self.calls)}


class FakeClock:
    """A monotonic clock advanced explicitly by the test."""

    def __init__(self) -> None:
        """Start the clock at zero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def _drive_into_fallback(api: SmartMeFailoverApi) -> None:
    """Issue exactly `threshold` reads, leaving the wrapper in fallback mode."""
    for _ in range(FALLBACK_FAILURE_THRESHOLD - 1):
        with pytest.raises(SmartMeConnectionError):
            asyncio.run(api.async_read_all())
    asyncio.run(api.async_read_all())


def test_without_a_fallback_the_primary_is_a_passthrough() -> None:
    """A cloud-only or credential-less meter keeps its old behaviour."""
    primary = FakeTransport("meter")
    api = SmartMeFailoverApi(primary, None)

    assert asyncio.run(api.async_read_all()) == {"active_power": 1.0}
    assert api.using_fallback is False
    assert api.device_identifier == "meter"


def test_a_failure_below_the_threshold_raises_and_never_uses_the_cloud() -> None:
    """A one-off dropped request must not drag the cloud in."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    api = SmartMeFailoverApi(primary, fallback, clock=FakeClock())

    for _ in range(FALLBACK_FAILURE_THRESHOLD - 1):
        with pytest.raises(SmartMeConnectionError):
            asyncio.run(api.async_read_all())

    assert fallback.calls == 0
    assert api.using_fallback is False
    assert api.consecutive_failures == FALLBACK_FAILURE_THRESHOLD - 1


def test_reaching_the_threshold_switches_to_the_cloud_immediately() -> None:
    """The poll that trips the threshold must still return data, not an error."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    api = SmartMeFailoverApi(primary, fallback, clock=FakeClock())

    for _ in range(FALLBACK_FAILURE_THRESHOLD - 1):
        with pytest.raises(SmartMeConnectionError):
            asyncio.run(api.async_read_all())

    assert asyncio.run(api.async_read_all()) == {"active_power": 1.0}
    assert api.using_fallback is True
    assert api.consecutive_failures == 0
    assert fallback.calls == 1
    assert primary.calls == FALLBACK_FAILURE_THRESHOLD


def test_the_cloud_serves_every_poll_until_the_probe_interval_passes() -> None:
    """The local link must not be hammered while it is down."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    clock = FakeClock()
    api = SmartMeFailoverApi(primary, fallback, clock=clock, probe_interval=100)

    _drive_into_fallback(api)
    primary_calls = primary.calls

    clock.advance(99)
    asyncio.run(api.async_read_all())

    assert primary.calls == primary_calls, "no probe before the interval"
    assert fallback.calls == 2
    assert api.using_fallback is True


def test_a_successful_probe_switches_back_to_the_local_link() -> None:
    """Recovery must return the meter's own data, not the cloud's."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    clock = FakeClock()
    api = SmartMeFailoverApi(primary, fallback, clock=clock, probe_interval=100)

    _drive_into_fallback(api)
    primary.failing = False
    clock.advance(100)

    data = asyncio.run(api.async_read_all())

    assert api.using_fallback is False
    assert api.consecutive_failures == 0
    assert data == {"active_power": float(FALLBACK_FAILURE_THRESHOLD + 1)}
    assert fallback.calls == 1, "the cloud was used only to bridge the outage"


def test_a_failed_probe_keeps_the_cloud_and_reschedules_the_next_one() -> None:
    """A still-down meter must wait a full interval before the next attempt."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    clock = FakeClock()
    api = SmartMeFailoverApi(primary, fallback, clock=clock, probe_interval=100)

    _drive_into_fallback(api)
    clock.advance(100)

    assert asyncio.run(api.async_read_all()) == {"active_power": 2.0}
    assert api.using_fallback is True
    assert primary.calls == FALLBACK_FAILURE_THRESHOLD + 1

    clock.advance(99)
    asyncio.run(api.async_read_all())

    assert primary.calls == FALLBACK_FAILURE_THRESHOLD + 1, "probe rescheduled"
    assert fallback.calls == 3


def test_a_success_resets_the_failure_counter() -> None:
    """Intermittent failures must be counted consecutively, not cumulatively."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    api = SmartMeFailoverApi(primary, fallback, clock=FakeClock())

    for _ in range(FALLBACK_FAILURE_THRESHOLD - 1):
        with pytest.raises(SmartMeConnectionError):
            asyncio.run(api.async_read_all())

    primary.failing = False
    asyncio.run(api.async_read_all())
    assert api.consecutive_failures == 0

    primary.failing = True
    with pytest.raises(SmartMeConnectionError):
        asyncio.run(api.async_read_all())
    assert api.using_fallback is False


def test_a_failing_cloud_fallback_propagates_its_error() -> None:
    """When both transports are down the coordinator must see an error."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud", failing=True)
    api = SmartMeFailoverApi(primary, fallback, clock=FakeClock())

    for _ in range(FALLBACK_FAILURE_THRESHOLD - 1):
        with pytest.raises(SmartMeConnectionError):
            asyncio.run(api.async_read_all())

    with pytest.raises(SmartMeConnectionError):
        asyncio.run(api.async_read_all())


def test_a_custom_threshold_is_honoured_and_defaults_are_sane() -> None:
    """The threshold is configurable; the defaults stay positive."""
    primary = FakeTransport("meter", failing=True)
    fallback = FakeTransport("cloud")
    api = SmartMeFailoverApi(primary, fallback, clock=FakeClock(), failure_threshold=1)

    assert asyncio.run(api.async_read_all()) == {"active_power": 1.0}
    assert api.using_fallback is True
    assert FALLBACK_FAILURE_THRESHOLD >= 1
    assert DEFAULT_FALLBACK_PROBE_INTERVAL > 0
