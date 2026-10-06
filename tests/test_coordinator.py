"""Tests for how the coordinator decides to build a cloud fallback.

Only a locally configured (Modbus TCP) meter gets a cloud fallback, and only
when usable credentials are present and the fallback has not been disabled. The
transport switching itself is covered in `test_failover.py`.
"""

from __future__ import annotations

import pytest

from custom_components.smartme_han import coordinator as coordinator_module
from custom_components.smartme_han.api import SmartMeCloudApi
from custom_components.smartme_han.const import (
    AUTH_TYPE_API_KEY,
    AUTH_TYPE_BASIC,
    CONF_CLOUD_FALLBACK_ENABLED,
)
from custom_components.smartme_han.coordinator import SmartMeDataUpdateCoordinator


@pytest.fixture
def build(monkeypatch):
    """Call the fallback builder with a stubbed aiohttp session."""
    monkeypatch.setattr(
        coordinator_module, "async_get_clientsession", lambda hass: object()
    )

    def _build(settings: dict[str, object]) -> SmartMeCloudApi | None:
        return SmartMeDataUpdateCoordinator._async_build_cloud_fallback(
            object(), settings
        )

    return _build


def test_api_key_credentials_build_a_cloud_fallback(build) -> None:
    """An API key is enough to fall back to the cloud."""
    fallback = build({"api_key": "your-api-key", "auth_type": AUTH_TYPE_API_KEY})
    assert isinstance(fallback, SmartMeCloudApi)


def test_basic_credentials_build_a_cloud_fallback(build) -> None:
    """A username and password build a basic-auth cloud fallback."""
    fallback = build(
        {
            "username": "user@example.com",
            "password": "hunter2",
            "auth_type": AUTH_TYPE_BASIC,
        }
    )
    assert isinstance(fallback, SmartMeCloudApi)


def test_basic_credentials_without_a_password_are_refused(build) -> None:
    """A partial basic-auth pair must not build a broken client."""
    assert build({"username": "user@example.com", "auth_type": AUTH_TYPE_BASIC}) is None


def test_no_credentials_means_no_fallback(build) -> None:
    """Without credentials the meter stays on Modbus TCP only."""
    assert build({"ip_address": "192.168.1.100"}) is None


def test_the_fallback_can_be_disabled(build) -> None:
    """The options flow can turn the fallback off even with credentials stored."""
    settings = {
        "api_key": "your-api-key",
        "auth_type": AUTH_TYPE_API_KEY,
        CONF_CLOUD_FALLBACK_ENABLED: False,
    }
    assert build(settings) is None
