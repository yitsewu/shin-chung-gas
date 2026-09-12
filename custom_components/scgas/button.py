"""欣中天然氣查詢按鈕。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ScgasEntity, safe_error_code


@dataclass(frozen=True, kw_only=True)
class ScgasButtonDescription(ButtonEntityDescription):
    """欣中按鈕描述。"""

    history: bool = False
    statistics: bool = False


BUTTONS: tuple[ScgasButtonDescription, ...] = (
    ScgasButtonDescription(key="query_latest", translation_key="query_latest", history=False),
    ScgasButtonDescription(key="backfill_history", translation_key="backfill_history", history=True),
    ScgasButtonDescription(key="rebuild_statistics", translation_key="rebuild_statistics", statistics=True),
)


class ScgasButton(ScgasEntity, ButtonEntity):
    """執行 coordinator 查詢。"""

    entity_description: ScgasButtonDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: Any,
        description: ScgasButtonDescription,
    ) -> None:
        super().__init__(entry, coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.statistics:
            return super().available and self.coordinator.data.get("statistics_status") not in {"pending", "running"}
        return super().available and self.coordinator.data.get("query_status") != "running"

    async def async_press(self) -> None:
        if self.entity_description.statistics:
            self.coordinator.async_rebuild_statistics(force=True)
            return
        try:
            await self.coordinator.async_query(history=self.entity_description.history)
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="query_busy" if safe_error_code(err) == "busy" else "query_failed",
                translation_placeholders={"code": safe_error_code(err)},
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """設定查詢按鈕。"""
    coordinator = entry.runtime_data
    async_add_entities(ScgasButton(entry, coordinator, item) for item in BUTTONS)
