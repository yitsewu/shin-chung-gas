"""Public probe must accept zero bills and never disclose account/error content."""
from decimal import Decimal
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location("live_probe", Path(__file__).parents[1] / "scripts/live_check.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def normalized(raw):
    return SimpleNamespace(usage_m3=Decimal(raw["gas"]), total_twd=Decimal(raw["cost"]))


def response(gas="0", cost="0"):
    return {"status": "success", "verification_status": "accepted", "bills": [{"gas": gas, "cost": cost}]}


def test_zero_values_and_one_attempt(capsys):
    calls = []
    def query(*args, **kwargs):
        calls.append(kwargs)
        print("PRIVATE_ACCOUNT")
        return response()
    assert probe.check(query, "000000", "SYNTHETIC", normalized) == {
        "status": "available", "code": "ok", "attempts": 1}
    assert calls == [{"history_limit": None}]
    assert "PRIVATE" not in capsys.readouterr().out


@pytest.mark.parametrize("result", [{}, response("NaN"), response(cost="Infinity"),
                                    {**response(), "bills": []},
                                    {**response(), "verification_status": "unknown"}])
def test_invalid_results(result):
    assert probe.check(lambda *a, **k: result, "000000", "SYNTHETIC", normalized)["status"] == "failed"


def test_exception_allowlist_and_no_retry(capsys):
    calls = []
    def query(*a, **k):
        calls.append(1)
        error = RuntimeError("PRIVATE_RESPONSE")
        error.code = "cannot_connect"
        raise error
    assert probe.check(query, "000000", "SYNTHETIC", normalized)["code"] == "cannot_connect"
    assert len(calls) == 1
    assert not capsys.readouterr().out


def test_unknown_error_code_is_not_published():
    def query(*a, **k):
        error = RuntimeError("PRIVATE")
        error.code = "PRIVATE"
        raise error
    assert probe.check(query, "000000", "SYNTHETIC", normalized)["code"] == "check_error"


def test_missing_configuration_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("SCGAS_MONITOR_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("SCGAS_MONITOR_CUSTOMER_NAME", raising=False)
    monkeypatch.setenv("SCGAS_RELEASE", "PRIVATE_INVALID_VERSION")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert probe.main() == 1
    assert "missing_configuration" in summary.read_text(encoding="utf-8")
    assert "PRIVATE" not in summary.read_text(encoding="utf-8") + capsys.readouterr().out

