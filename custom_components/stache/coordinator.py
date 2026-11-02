"""Polls the Stache out-sensor webhook."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_PATH,
)

_LOGGER = logging.getLogger(__name__)

type StacheConfigEntry = ConfigEntry[StacheCoordinator]


def sensor_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}{SENSOR_PATH}?token={token}"


def valid_payload(data: Any) -> bool:
    """Is this a plausible out-sensor response (not an arbitrary 200 page)?"""
    return (
        isinstance(data, dict)
        and isinstance(data.get("out_count"), int)
        and isinstance(data.get("unaccounted_count"), int)
        and isinstance(data.get("total"), int)
        and isinstance(data.get("items"), list)
        and isinstance(data.get("low_stock_count"), int)
        and isinstance(data.get("low_stock"), list)
        and isinstance(data.get("warranty_expiring"), list)
    )


class StacheCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches out/low-stock/warranty data from Stache."""

    config_entry: StacheConfigEntry

    def __init__(self, hass: HomeAssistant, entry: StacheConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self._url = sensor_url(entry.data[CONF_URL], entry.data[CONF_TOKEN])
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Webhook token rejected")
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except ConfigEntryAuthFailed:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Cannot reach Stache: {err}") from err
        if not valid_payload(data):
            raise UpdateFailed("Stache returned an unexpected response")
        return data
