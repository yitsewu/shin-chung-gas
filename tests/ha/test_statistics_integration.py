"""以真正的 Recorder SQLite 驗證分攤統計與歷史更正。"""

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.recorder.statistics import get_last_statistics

from custom_components.scgas.statistics import async_publish_statistics


async def test_recorder_persists_replaces_and_keeps_twd(hass, recorder_mock):
    recorder = recorder_mock
    if not hass.is_running:
        await hass.async_start()
    await recorder.async_block_till_done()
    hass.config.currency = "USD"
    entry_id = "01K4VYABC123XYZ"
    statistic_id = "scgas:01k4vyabc123xyz_gas"
    result = await async_publish_statistics(
        hass,
        entry_id,
        "測試帳戶",
        {
            "2026-03-01": {"gas": 24, "cost": 240, "carbon": 3.6},
            "2026-03-02": {"gas": 12, "cost": 120, "carbon": 1.8},
        },
    )
    assert result == "published"
    first = await recorder.async_add_executor_job(get_last_statistics, hass, 1, statistic_id, False, {"sum"})
    assert first[statistic_id][0]["sum"] == pytest.approx(36)
    result = await async_publish_statistics(
        hass,
        entry_id,
        "測試帳戶",
        {
            "2026-03-01": {"gas": 10, "cost": 100, "carbon": None},
        },
    )
    assert result == "published"
    corrected = await recorder.async_add_executor_job(get_last_statistics, hass, 1, statistic_id, False, {"sum"})
    assert corrected[statistic_id][0]["sum"] == pytest.approx(10)
    assert corrected[statistic_id][0]["start"] < first[statistic_id][0]["start"]
