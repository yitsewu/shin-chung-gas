"""以合成帳单驗證真正 portal → client → normalizer 管線。"""

from datetime import date
from decimal import Decimal
import importlib
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch
import pytest

pkg = ModuleType("scgas_isolated")
pkg.__path__ = [str(Path(__file__).parents[1] / "custom_components/scgas")]
sys.modules[pkg.__name__] = pkg
client = importlib.import_module("scgas_isolated.client")
portal = importlib.import_module("scgas_isolated.portal")
normalize = importlib.import_module("scgas_isolated.normalize")
models = importlib.import_module("scgas_isolated.models")


def row(month="08", paid=True):
    return [
        f"115{month}23",
        "000000",
        "20",
        "17",
        "親眼抄見",
        "203",
        "0",
        "0",
        "0",
        "300",
        f"115{month}01~115{month}20",
        "0",
        "503",
        "已銷帳" if paid else "",
        *([] if paid else [f"115{month}28"]),
    ]


def html(rows=None):
    rows = [portal.HEADERS["usage"], *(rows or [row()])]
    return (
        "<p>戶名：不可輸出</p><table>"
        + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        + "</table>"
    )


def result(rows=None, **kwargs):
    with patch.object(portal.ScgasClient, "probe"), patch.object(portal.ScgasClient, "_get", return_value=html(rows)):
        return client.query("000000", "測試帳戶", **kwargs)


def test_pipeline_dates_totals_privacy_and_allocation():
    response = result(history_limit=0)
    bill = normalize.normalize_bill(response["bills"][0])
    assert bill.usage_m3 == 17 and bill.total_twd == 503
    assert bill.period_start == date(2026, 7, 31)
    assert bill.period_end == date(2026, 8, 20)
    assert bill.extra_fields["抄表度"] == "20"
    assert "不可輸出" not in str(bill.to_dict()) and "000000" not in str(bill.to_dict())
    daily = models.allocate_days([bill], mode="days")
    assert len(daily) == 20
    assert sum(Decimal(str(d["gas"])) for d in daily.values()) == Decimal(17)
    assert sum(Decimal(str(d["cost"])) for d in daily.values()) == Decimal(503)


def test_paid_missing_deadline_and_unpaid_deadline():
    assert "繳費期限" not in result()["bills"][0]["fields"]
    fields = result([row(paid=False)])["bills"][0]["fields"]
    assert fields["繳費期限"] == "2026-08-28" and fields["繳費狀態"] == "unpaid"


def test_history_latest_limit_and_specific():
    rows = [row("08"), row("06")]
    assert len(result(rows)["bills"]) == 1
    assert len(result(rows, history_limit=0)["bills"]) == 2
    assert len(result(rows, history_limit=1)["bills"]) == 1
    assert result(rows, requested_month="2026-06")["bills"][0]["month"] == "2026-06"
    with pytest.raises(client.QueryError, match="month_unavailable"):
        result(rows, requested_month="2026-07")


def test_existing_bill_is_refreshed_for_payment_corrections():
    assert len(result(history_limit=0, known_months=("2026-08",), refresh_history=False)["bills"]) == 1


def test_duplicate_month_fails_closed():
    with pytest.raises(client.QueryError, match="duplicate_month"):
        result([row(), row()])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda h: h.replace("000000", "999999"),
        lambda h: h.replace("使用度數", "變更"),
        lambda h: h.replace("<td>17</td>", "<td>NaN</td>"),
        lambda h: "<p>查詢失敗</p>",
    ],
)
def test_invalid_response_never_leaks_input(mutation):
    with (
        patch.object(portal.ScgasClient, "probe"),
        patch.object(portal.ScgasClient, "_get", return_value=mutation(html())),
    ):
        with pytest.raises(client.QueryError) as error:
            client.query("000000", "不得洩漏")
        assert "000000" not in str(error.value) and "不得洩漏" not in str(error.value)


def test_redirect_and_external_url_rejected():
    with pytest.raises(portal.QueryError):
        portal.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com")
    with pytest.raises(portal.QueryError):
        portal.ScgasClient()._get("http://www.scgas.com.tw/doc/gas.asp")


def test_big5_query_and_probe():
    form = (
        '<form method="get" action="gbm02.asp">'
        + "".join(
            f'<input name="{n}" value="{v}">'
            for n, v in [("wkapno", ""), ("wkname", ""), ("p1", "1"), ("R1", "0"), ("R1", "1")]
        )
        + "</form>"
    )
    with patch.object(portal.ScgasClient, "_get", side_effect=[form, html()]) as get:
        p = portal.ScgasClient()
        p.probe()
        p.query("000000", "測試")
        assert "%B4%FA%B8%D5" in get.call_args.args[0]
