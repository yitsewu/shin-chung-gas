from copy import deepcopy
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.components.recorder.statistics import get_last_statistics
from custom_components.scgas import client


async def test_setup_entities_diagnostics_and_recorder(hass, loaded, recorder_mock):
    c = loaded.runtime_data
    if c._statistics_task:
        await c._statistics_task
    assert c.data["query_status"] == "success"
    assert c.data["statistics_status"] == "published"
    assert c.data["meter_reading"] == "20"
    assert c.data["payment_due"] is None
    assert c.data["billing_days"] == 20
    states = hass.states.async_all()
    assert any(s.attributes.get("device_class") == "gas" for s in states)
    assert all("ocr" not in s.entity_id for s in states)
    stat = f"scgas:{loaded.entry_id.lower()}_gas"
    actual = await recorder_mock.async_add_executor_job(get_last_statistics, hass, 1, stat, False, {"sum"})
    assert actual[stat][0]["sum"] == pytest.approx(17)
    from custom_components.scgas.diagnostics import async_get_config_entry_diagnostics

    diag = await async_get_config_entry_diagnostics(hass, loaded)
    assert "000000" not in str(diag) and "測試帳戶" not in str(diag) and "ocr" not in str(diag)


async def test_failure_preserves_bill_and_revision_replaces(hass, loaded, bill_result):
    c = loaded.runtime_data
    original = deepcopy(c.bills)
    with patch("custom_components.scgas.client.query", side_effect=client.QueryError("cannot_connect")):
        with pytest.raises(client.QueryError):
            await c.async_query()
    assert c.bills == original and c.data["query_status"] == "failed"
    corrected = deepcopy(bill_result)
    corrected["bills"][0]["fields"]["使用度數"] = "18"
    with patch("custom_components.scgas.client.query", return_value=corrected):
        await c.async_query(history=True)
    assert len(c.bills) == 1 and c.data["usage_m3"] == 18
    if c._statistics_task:
        await c._statistics_task
    assert c.data["statistics_status"] == "published"


async def test_history_actions_busy_and_options(hass, loaded):
    c = loaded.runtime_data
    result = await hass.services.async_call(
        "scgas", "get_history", {"config_entry_id": loaded.entry_id}, blocking=True, return_response=True
    )
    assert result["total_saved_bills"] == 1
    before = len(c.query_history)
    async with c._query_lock:
        with pytest.raises(client.QueryError, match="busy"):
            await c.async_query()
    assert len(c.query_history) == before
    flow = await hass.config_entries.options.async_init(loaded.entry_id)
    assert flow["type"] == FlowResultType.FORM and flow["step_id"] == "settings"
    assert "ocr" not in str(flow["data_schema"].schema)


async def test_config_flow_credentials_and_duplicates(hass, bill_result):
    with (
        patch("custom_components.scgas.client.query", return_value=bill_result),
        patch("custom_components.scgas.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        form = await hass.config_entries.flow.async_init("scgas", context={"source": "user"})
        invalid = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"customer_id": "123", "customer_name": "測試", "name": "瓦斯", "history_limit": 0}
        )
        assert invalid["errors"] == {"customer_id": "invalid_customer_id"}
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {"customer_id": "000000", "customer_name": "測試", "name": "瓦斯", "history_limit": 0}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        again = await hass.config_entries.flow.async_init(
            "scgas",
            context={"source": "user"},
            data={"customer_id": "000000", "customer_name": "測試", "name": "瓦斯", "history_limit": 0},
        )
        assert again["reason"] == "already_configured"
