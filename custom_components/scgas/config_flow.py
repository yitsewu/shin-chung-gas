"""欣中天然氣設定、重新驗證與排程選項。"""

from __future__ import annotations
from datetime import time as time_value
from functools import partial
import hashlib
import math
import re
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector
from . import client
from .const import DEFAULT_OPTIONS, DOMAIN, NAME

_SCHEDULES = ("daily", "weekly", "monthly")
_ALLOCATIONS = ("days", "equal")


def _account_id(customer_id):
    return hashlib.sha256(customer_id.encode("ascii")).hexdigest()


def _credential_schema(values):
    return vol.Schema(
        {
            vol.Required("customer_id", default=values.get("customer_id", "")): selector.TextSelector(),
            vol.Required("customer_name", default=values.get("customer_name", "")): selector.TextSelector(),
            vol.Required("name", default=values.get("name", NAME)): selector.TextSelector(),
            vol.Required("history_limit", default=values.get("history_limit", 0)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
        }
    )


class ScgasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return ScgasOptionsFlow()

    async def async_step_user(self, user_input=None):
        return await self._credentials("user", user_input, {})

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        return await self._credentials("reconfigure", user_input, {**entry.data, **entry.options})

    async def _credentials(self, step, user_input, defaults):
        values = dict(defaults)
        errors = {}
        if user_input is not None:
            values = dict(user_input)
            customer_id = str(values.get("customer_id", "")).strip()
            customer_name = str(values.get("customer_name", "")).strip()
            name = str(values.get("name", "")).strip()
            if not re.fullmatch(r"[0-9]{6}", customer_id):
                errors["customer_id"] = "invalid_customer_id"
            if not customer_name or len(customer_name) > 40:
                errors["customer_name"] = "invalid_customer_name"
            if not name or len(name) > 100:
                errors["name"] = "invalid_name"
            try:
                limit = int(values.get("history_limit", 0))
                if limit < 0 or limit != float(values.get("history_limit", 0)):
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                errors["history_limit"] = "invalid_history_limit"
            if not errors:
                uid = _account_id(customer_id)
                await self.async_set_unique_id(uid)
                if step == "reconfigure":
                    self._abort_if_unique_id_mismatch()
                else:
                    self._abort_if_unique_id_configured()
                try:
                    result = await self.hass.async_add_executor_job(
                        partial(client.query, customer_id, customer_name, history_limit=limit)
                    )
                except client.QueryError as error:
                    errors["base"] = error.code
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    self.hass.data.setdefault(DOMAIN, {}).setdefault("seeds", {})[uid] = result
                    data = {"customer_id": customer_id, "customer_name": customer_name, "name": name}
                    if step == "reconfigure":
                        entry = self._get_reconfigure_entry()
                        return self.async_update_and_abort(
                            entry,
                            title=name,
                            data=data,
                            options={**DEFAULT_OPTIONS, **entry.options, "history_limit": limit},
                        )
                    return self.async_create_entry(
                        title=name, data=data, options={**DEFAULT_OPTIONS, "history_limit": limit}
                    )
        return self.async_show_form(step_id=step, data_schema=_credential_schema(values), errors=errors)


class ScgasOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return await self.async_step_settings(user_input)

    async def async_step_settings(self, user_input=None):
        values = {**DEFAULT_OPTIONS, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            values, errors = _normalize_options(user_input, values)
            if not errors:
                return self.async_create_entry(title="", data=values)
        return self.async_show_form(step_id="settings", data_schema=_options_schema(values), errors=errors)


def _options_schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("enabled", default=values["enabled"]): selector.BooleanSelector(),
            vol.Required("schedule", default=values["schedule"]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(_SCHEDULES), translation_key="schedule")
            ),
            vol.Required("query_time", default=values["query_time"]): selector.TimeSelector(),
            vol.Required("weekday", default=values["weekday"]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=6,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("monthday", default=values["monthday"]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=31,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("history_limit", default=values["history_limit"]): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("allocation", default=values["allocation"]): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(_ALLOCATIONS), translation_key="allocation")
            ),
            vol.Optional(
                "carbon_factor",
                description={"suggested_value": values.get("carbon_factor")},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, step=0.001, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                "carbon_factor_source",
                default=values.get("carbon_factor_source", ""),
            ): selector.TextSelector(),
        }
    )


def _normalize_options(user_input: dict[str, Any], current: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    values = {**DEFAULT_OPTIONS, **current, **user_input}
    errors: dict[str, str] = {}

    query_time_input = values.get("query_time")
    if isinstance(query_time_input, time_value):
        parsed_time = query_time_input
    else:
        try:
            parsed_time = time_value.fromisoformat(str(query_time_input))
        except ValueError:
            parsed_time = None
    if parsed_time is None or parsed_time.second != 0 or parsed_time.microsecond != 0:
        query_time = str(query_time_input)
        errors["query_time"] = "invalid_query_time"
    else:
        query_time = parsed_time.strftime("%H:%M")

    try:
        weekday = int(values.get("weekday"))
    except (TypeError, ValueError):
        weekday = -1
    if not 0 <= weekday <= 6:
        errors["weekday"] = "invalid_weekday"

    try:
        monthday = int(values.get("monthday"))
    except (TypeError, ValueError):
        monthday = 0
    if not 1 <= monthday <= 31:
        errors["monthday"] = "invalid_monthday"

    try:
        history_limit = int(values.get("history_limit"))
    except (TypeError, ValueError):
        history_limit = -1
    if history_limit < 0:
        errors["history_limit"] = "invalid_history_limit"

    schedule = str(values.get("schedule"))
    if schedule not in _SCHEDULES:
        errors["schedule"] = "invalid_schedule"
    allocation = str(values.get("allocation"))
    if allocation not in _ALLOCATIONS:
        errors["allocation"] = "invalid_allocation"

    # 空白 optional 欄位會由前端省略；省略即清除舊係數，不保留舊估算。
    factor_input = user_input.get("carbon_factor")
    carbon_factor: float | None
    if factor_input in (None, ""):
        carbon_factor = None
    else:
        try:
            carbon_factor = float(factor_input)
        except (TypeError, ValueError):
            carbon_factor = None
            errors["carbon_factor"] = "invalid_carbon_factor"
        else:
            if not math.isfinite(carbon_factor) or carbon_factor < 0:
                errors["carbon_factor"] = "invalid_carbon_factor"

    source = str(values.get("carbon_factor_source", "")).strip()
    if carbon_factor is not None and not source:
        errors["carbon_factor_source"] = "carbon_factor_source_required"
    if len(source) > 200:
        errors["carbon_factor_source"] = "invalid_carbon_factor_source"
    if carbon_factor is None:
        source = ""

    return {
        "enabled": bool(values.get("enabled")),
        "schedule": schedule,
        "query_time": query_time,
        "weekday": weekday,
        "monthday": monthday,
        "history_limit": history_limit,
        "allocation": allocation,
        "carbon_factor": carbon_factor,
        "carbon_factor_source": source,
    }, errors
