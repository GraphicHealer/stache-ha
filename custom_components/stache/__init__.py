"""Stache inventory integration."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import StacheApiClient
from .const import CONF_API_TOKEN, CONF_URL
from .coordinator import StacheConfigEntry, StacheCoordinator, StacheData
from .services import async_setup_services

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: StacheConfigEntry) -> bool:
    coordinator = StacheCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    api = (
        StacheApiClient(hass, entry.data[CONF_URL], entry.data[CONF_API_TOKEN])
        if entry.data.get(CONF_API_TOKEN)
        else None
    )
    entry.runtime_data = StacheData(coordinator=coordinator, api=api)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: StacheConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StacheConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
