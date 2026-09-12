"""真正 HA 與 SQLite Recorder fixture；所有查詢身分皆為合成資料。"""

from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url):
    return None


@pytest.fixture(autouse=True)
async def ready_recorder(recorder_mock):
    yield recorder_mock


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def config_entry():
    from custom_components.scgas.const import DEFAULT_OPTIONS

    return MockConfigEntry(
        domain="scgas",
        title="測試瓦斯",
        unique_id=sha256(b"000000").hexdigest(),
        data={"customer_id": "000000", "customer_name": "測試帳戶", "name": "測試瓦斯"},
        options={**DEFAULT_OPTIONS, "enabled": False},
        version=1,
        minor_version=2,
    )


@pytest.fixture
def bill_result():
    return {
        "bills": [
            {
                "month": "2026-08",
                "fields": {
                    "使用度數": "17",
                    "合計": "503",
                    "從量費": "203",
                    "基本費": "300",
                    "計費起日": "2026-08-01",
                    "計費迄日": "2026-08-20",
                    "應收日期": "2026-08-23",
                    "抄表度": "20",
                    "抄表狀況": "親眼抄見",
                    "繳費狀態": "paid",
                },
                "fetched_at": "2026-09-01T01:00:00+00:00",
            }
        ],
        "available_months": ["2026-08"],
        "verification_status": "accepted",
        "error_code": None,
        "status": "success",
        "finished_at": "2026-09-01T01:00:00+00:00",
    }


@pytest.fixture
async def loaded(hass, config_entry, bill_result):
    config_entry.add_to_hass(hass)
    hass.data.setdefault("scgas", {}).setdefault("seeds", {})[config_entry.unique_id] = deepcopy(bill_result)
    with patch("custom_components.scgas.client.query", return_value=deepcopy(bill_result)):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry
        await hass.config_entries.async_unload(config_entry.entry_id)
