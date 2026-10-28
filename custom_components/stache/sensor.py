"""Sensors for Stache: items out, unaccounted, low stock, warranty expiring."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN
from .coordinator import StacheCoordinator

DESCRIPTIONS = [
    {
        "key": "items_out",
        "translation_key": "items_out",
        "icon": "mdi:package-variant",
        "state_key": "out_count",
        "attr_key": "items",
        "attr_name": "items",
    },
    {
        "key": "unaccounted",
        "translation_key": "unaccounted",
        "icon": "mdi:help-rhombus-outline",
        "state_key": "unaccounted_count",
        "attr_key": None,
        "attr_name": None,
    },
    {
        "key": "low_stock",
        "translation_key": "low_stock",
        "icon": "mdi:package-variant-minus",
        "state_key": "low_stock_count",
        "attr_key": "low_stock",
        "attr_name": "items",
    },
    {
        "key": "warranty_expiring",
        "translation_key": "warranty_expiring",
        "icon": "mdi:shield-clock-outline",
        "state_key": None,  # counted from the list
        "attr_key": "warranty_expiring",
        "attr_name": "items",
    },
]

MAX_ATTR_ITEMS = 50


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: StacheCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        StacheSensor(coordinator, entry, desc) for desc in DESCRIPTIONS
    )


class StacheSensor(CoordinatorEntity[StacheCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StacheCoordinator,
        entry: ConfigEntry,
        desc: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc['key']}"
        self._attr_translation_key = desc["translation_key"]
        self._attr_icon = desc["icon"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Stache",
            manufacturer="Stache",
            configuration_url=entry.data[CONF_URL],
        )

    @property
    def native_value(self) -> int:
        data = self.coordinator.data or {}
        if self._desc["state_key"]:
            return data.get(self._desc["state_key"], 0)
        return len(data.get(self._desc["attr_key"], []) or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self._desc["attr_key"]:
            return None
        items = (self.coordinator.data or {}).get(self._desc["attr_key"]) or []
        return {self._desc["attr_name"]: items[:MAX_ATTR_ITEMS]}
