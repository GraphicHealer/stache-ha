"""Polls the Stache out-sensor webhook."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import StacheApiClient
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SENSOR_PATH,
)

_LOGGER = logging.getLogger(__name__)

@dataclass
class StacheData:
    """Per-entry runtime data - sensor coordinator plus optional REST client."""

    coordinator: "StacheCoordinator"
    api: StacheApiClient | None


type StacheConfigEntry = ConfigEntry[StacheData]


def sensor_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}{SENSOR_PATH}?token={token}"


def _count(v: Any) -> bool:
    # bool is an int subclass - True/False must not pass as counts, and a
    # negative count is malformed either way.
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def valid_payload(data: Any) -> bool:
    """Is this a plausible out-sensor response (not an arbitrary 200 page)?"""
    if not isinstance(data, dict):
        return False
    if not all(
        _count(data.get(k))
        for k in ("out_count", "unaccounted_count", "total", "low_stock_count")
    ):
        return False
    lists = [data.get(k) for k in ("items", "low_stock", "warranty_expiring")]
    if not all(isinstance(lst, list) for lst in lists):
        return False
    # Entries surface in attributes as dicts; anything else breaks sensors.
    return all(isinstance(e, dict) for lst in lists for e in lst)


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
