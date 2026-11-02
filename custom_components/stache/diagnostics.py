"""Diagnostics for the Stache integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import StacheConfigEntry

TO_REDACT = {CONF_TOKEN}


def _summarize(data: dict[str, Any]) -> dict[str, Any]:
    """Counts and shape only - never inventory names, paths, or quantities."""
    return {
        "out_count": data.get("out_count"),
        "unaccounted_count": data.get("unaccounted_count"),
        "total": data.get("total"),
        "low_stock_count": data.get("low_stock_count"),
        "items_len": len(data.get("items") or []),
        "low_stock_len": len(data.get("low_stock") or []),
        "warranty_expiring_len": len(data.get("warranty_expiring") or []),
        "payload_keys": sorted(data.keys()),
        "item_field_names": sorted(data["items"][0].keys())
        if isinstance(data.get("items"), list) and data["items"]
        else [],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StacheConfigEntry
) -> dict[str, Any]:
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_summary": _summarize(entry.runtime_data.data or {}),
    }
