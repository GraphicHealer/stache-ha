"""Polls the Stache out-sensor webhook."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TOKEN, CONF_URL, DEFAULT_SCAN_INTERVAL, DOMAIN, SENSOR_PATH

_LOGGER = logging.getLogger(__name__)


def sensor_url(base: str, token: str) -> str:
    return f"{base.rstrip('/')}{SENSOR_PATH}?token={token}"


class StacheCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches out/low-stock/warranty data from Stache."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._url = sensor_url(entry.data[CONF_URL], entry.data[CONF_TOKEN])
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 401:
                    raise UpdateFailed("Invalid webhook token")
                resp.raise_for_status()
                return await resp.json()
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Cannot reach Stache: {err}") from err
