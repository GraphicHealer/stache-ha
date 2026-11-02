"""Shared fixtures for the Stache integration tests."""
from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stache.const import DOMAIN

BASE_URL = "http://stache.local:8080"
SENSOR_PATH = "/api/webhooks/out-sensor"
SENSOR_URL = f"{BASE_URL}{SENSOR_PATH}"
TOKEN = "deadbeef-token"

PAYLOAD = {
    "out_count": 1,
    "unaccounted_count": 0,
    "total": 1,
    "items": [{"name": "drill", "path": "garage", "days": 3}],
    "low_stock_count": 0,
    "low_stock": [],
    "warranty_expiring": [],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    e = MockConfigEntry(domain=DOMAIN, title="Stache (stache.local:8080)",
                        data={"url": BASE_URL, "token": TOKEN})
    e.add_to_hass(hass)
    return e


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
