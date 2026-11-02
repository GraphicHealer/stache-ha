"""Runtime coverage: polling, sensors, failures, diagnostics."""
from __future__ import annotations

import json

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.stache.coordinator import valid_payload
from custom_components.stache.diagnostics import (
    async_get_config_entry_diagnostics,
)

from conftest import BASE_URL, PAYLOAD, SENSOR_URL, TOKEN, setup


async def test_sensors_populate(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    items_out = hass.states.get("sensor.stache_items_out")
    assert items_out is not None
    assert items_out.state == "1"
    assert items_out.attributes["items"] == PAYLOAD["items"]
    assert hass.states.get("sensor.stache_unaccounted").state == "0"
    assert hass.states.get("sensor.stache_low_stock").state == "0"
    assert hass.states.get("sensor.stache_warranty_expiring").state == "0"


async def test_attribute_truncation(hass: HomeAssistant, aioclient_mock, entry):
    big = dict(PAYLOAD, items=[{"name": f"i{n}"} for n in range(60)])
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=big)
    await setup(hass, entry)
    state = hass.states.get("sensor.stache_items_out")
    assert len(state.attributes["items"]) == 50
    assert state.state == "1"  # count still comes from out_count


async def test_401_poll_raises_auth_failed(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", status=401)
    with pytest.raises(ConfigEntryAuthFailed):
        await entry.runtime_data._async_update_data()


async def test_server_error_marks_update_failed(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", status=500)
    with pytest.raises(UpdateFailed):
        await entry.runtime_data._async_update_data()


async def test_connection_error_marks_update_failed(
    hass: HomeAssistant, aioclient_mock, entry
):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SENSOR_URL}?token={TOKEN}", exc=aiohttp.ClientConnectionError()
    )
    with pytest.raises(UpdateFailed):
        await entry.runtime_data._async_update_data()


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"out_count": 1},  # missing fields
        {"out_count": "1", "unaccounted_count": 0, "total": 1, "items": [],
         "low_stock_count": 0, "low_stock": [], "warranty_expiring": []},
        [],  # not an object at all
    ],
)
def test_valid_payload_rejects_wrong_shapes(bad):
    assert valid_payload(bad) is False


def test_valid_payload_accepts_contract():
    assert valid_payload(PAYLOAD) is True
    assert valid_payload(dict(PAYLOAD, extra="ok")) is True


async def test_malformed_json_marks_update_failed(
    hass: HomeAssistant, aioclient_mock, entry
):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{SENSOR_URL}?token={TOKEN}", text="<html>not json</html>"
    )
    with pytest.raises(UpdateFailed):
        await entry.runtime_data._async_update_data()


async def test_diagnostics_redacts_token_and_contents(
    hass: HomeAssistant, aioclient_mock, entry
):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    blob = json.dumps(diag)
    assert TOKEN not in blob
    assert "drill" not in blob  # no inventory contents leak
    assert diag["coordinator_summary"]["out_count"] == 1
    assert diag["coordinator_summary"]["payload_keys"]
