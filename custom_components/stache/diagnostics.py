"""Diagnostics for the Stache integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import StacheConfigEntry

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StacheConfigEntry
) -> dict[str, Any]:
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": entry.runtime_data.data,
    }
