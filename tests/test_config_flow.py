"""Config-flow coverage: URL parsing, validation errors, reauth, options."""
from __future__ import annotations

from datetime import timedelta

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.stache.config_flow import parse_input
from custom_components.stache.const import DOMAIN

from .conftest import BASE_URL, PAYLOAD, SENSOR_URL, TOKEN, entry, setup  # noqa: F401


async def start_user_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_parse_input_accepts_sensor_url_and_base():
    assert parse_input(f"{SENSOR_URL}?token={TOKEN}", None) == (BASE_URL, TOKEN)
    assert parse_input(" http://ha:8080/ ", "t") == ("http://ha:8080", "t")
    assert parse_input("https://x.io/stache", "t") == ("https://x.io/stache", "t")


@pytest.mark.parametrize(
    "bad",
    [
        "notaurl",
        "ftp://x",
        "http://",
        "http://h:8080?x=1",
        "http://h:8080#f",
        "http://[unclosed",
        f"{SENSOR_URL}?token=a&token=b",
    ],
)
def test_parse_input_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_input(bad, None)


async def test_setup_pasted_sensor_url(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": f"{SENSOR_URL}?token={TOKEN}"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": BASE_URL, "token": TOKEN}


async def test_setup_separate_fields(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": BASE_URL, "token": TOKEN}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_setup_invalid_url(hass: HomeAssistant):
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": "notaurl", "token": TOKEN}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"url": "invalid_url"}


async def test_setup_missing_token(hass: HomeAssistant):
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": BASE_URL}
    )
    assert result["errors"] == {"base": "token_required"}


async def test_setup_invalid_auth(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", status=401)
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": BASE_URL, "token": TOKEN}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_setup_cannot_connect(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(
        f"{SENSOR_URL}?token={TOKEN}", exc=aiohttp.ClientConnectionError()
    )
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": BASE_URL, "token": TOKEN}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_setup_wrong_payload(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json={"hello": "world"})
    flow = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"url": BASE_URL, "token": TOKEN}
    )
    assert result["errors"] == {"base": "invalid_response"}


async def test_reauth_updates_token(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    new_tok = "fresh-token"
    aioclient_mock.get(f"{SENSOR_URL}?token={new_tok}", json=PAYLOAD)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"token": new_tok}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == new_tok


async def test_options_flow_changes_interval(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{SENSOR_URL}?token={TOKEN}", json=PAYLOAD)
    await setup(hass, entry)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"scan_interval": 60}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["scan_interval"] == 60
    assert entry.runtime_data.update_interval == timedelta(seconds=60)
