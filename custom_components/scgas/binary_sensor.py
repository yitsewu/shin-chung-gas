"""欣中天然氣診斷 binary sensors。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ScgasEntity


@dataclass(frozen=True, kw_only=True)
class ScgasBinarySensorDescription(BinarySensorEntityDescription):
    """欣中診斷 binary sensor 描述。"""

    invert: bool = False


BINARY_SENSORS: tuple[ScgasBinarySensorDescription, ...] = (
    ScgasBinarySensorDescription(
        key="query_success",
        translation_key="last_query_failed",
        entity_category=EntityCategory.DIAGNOSTIC,
        invert=True,
    ),
    ScgasBinarySensorDescription(
        key="verification_success",
        translation_key="verification_accepted",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ScgasBinarySensorDescription(
        key="history_complete",
        translation_key="history_complete",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


class ScgasBinarySensor(ScgasEntity, BinarySensorEntity):
    """由 coordinator 的三態布林值提供診斷結果。"""

    entity_description: ScgasBinarySensorDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: Any,
        description: ScgasBinarySensorDescription,
    ) -> None:
        super().__init__(entry, coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator_value()
        if value is None:
            return None
        state = bool(value)
        return not state if self.entity_description.invert else state


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """設定欣中診斷 binary sensors。"""
    coordinator = entry.runtime_data
    async_add_entities(ScgasBinarySensor(entry, coordinator, item) for item in BINARY_SENSORS)
