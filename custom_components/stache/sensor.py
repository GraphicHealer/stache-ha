"""Sensors for Stache: items out, unaccounted, low stock, warranty expiring."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_URL, DOMAIN
from .coordinator import StacheConfigEntry, StacheCoordinator

MAX_ATTR_ITEMS = 50


@dataclass(frozen=True, kw_only=True)
class StacheSensorEntityDescription(SensorEntityDescription):
    """Describes a Stache count sensor."""

    value_fn: Callable[[dict[str, Any]], int]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None]


SENSORS: tuple[StacheSensorEntityDescription, ...] = (
    StacheSensorEntityDescription(
        key="items_out",
        translation_key="items_out",
        value_fn=lambda data: data.get("out_count", 0),
        attributes_fn=lambda data: {
            "items": (data.get("items") or [])[:MAX_ATTR_ITEMS]
        },
    ),
    StacheSensorEntityDescription(
        key="unaccounted",
        translation_key="unaccounted",
        value_fn=lambda data: data.get("unaccounted_count", 0),
        attributes_fn=lambda data: None,
    ),
    StacheSensorEntityDescription(
        key="low_stock",
        translation_key="low_stock",
        value_fn=lambda data: data.get("low_stock_count", 0),
        attributes_fn=lambda data: {
            "items": (data.get("low_stock") or [])[:MAX_ATTR_ITEMS]
        },
    ),
    StacheSensorEntityDescription(
        key="warranty_expiring",
        translation_key="warranty_expiring",
        value_fn=lambda data: len(data.get("warranty_expiring") or []),
        attributes_fn=lambda data: {
            "items": (data.get("warranty_expiring") or [])[:MAX_ATTR_ITEMS]
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StacheConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        StacheSensor(entry.runtime_data, entry, desc) for desc in SENSORS
    )


class StacheSensor(CoordinatorEntity[StacheCoordinator], SensorEntity):
    """A count sensor backed by the shared coordinator."""

    _attr_has_entity_name = True
    entity_description: StacheSensorEntityDescription

    def __init__(
        self,
        coordinator: StacheCoordinator,
        entry: StacheConfigEntry,
        description: StacheSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Stache",
            manufacturer="Stache",
            configuration_url=entry.data[CONF_URL],
        )

    @property
    def native_value(self) -> int:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attributes_fn(self.coordinator.data or {})
