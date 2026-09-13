"""Probe one real bill; publish only fixed codes and execution metadata."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import sys
import types

SAFE_CODES = {"cannot_connect", "site_changed", "invalid_response", "invalid_auth",
              "upstream_rejected", "duplicate_month", "invalid_month", "month_unavailable"}


def check(query, customer_id, customer_name, normalize):
    try:
        # Suppress response/exception output; only allowlisted metadata leaves this process.
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result = query(customer_id, customer_name, history_limit=None)
            valid = (isinstance(result, dict) and result.get("status") == "success"
                     and result.get("verification_status") == "accepted"
                     and len(result.get("bills", [])) == 1)
            if valid:
                bill = normalize(result["bills"][0])
                valid = (bill.usage_m3 is not None and bill.usage_m3.is_finite()
                         and bill.total_twd is not None and bill.total_twd.is_finite())
        code = "ok" if valid else "invalid_response"
    except Exception as error:
        raw_code = getattr(error, "code", None)
        code = raw_code if isinstance(raw_code, str) and raw_code in SAFE_CODES else "check_error"
    return {"status": "available" if code == "ok" else "failed", "code": code, "attempts": 1}


def main():
    version = os.environ.get("SCGAS_RELEASE", "")
    customer_id = os.environ.pop("SCGAS_MONITOR_CUSTOMER_ID", "")
    customer_name = os.environ.pop("SCGAS_MONITOR_CUSTOMER_NAME", "")
    report = {"status": "unknown", "code": "check_error", "attempts": 0}
    try:
        if not customer_id or not customer_name:
            report["code"] = "missing_configuration"
        elif not re.fullmatch(r"v\d+\.\d+\.\d+", version):
            report["code"] = "invalid_release"
        else:
            root = Path(os.environ["SCGAS_RELEASE_ROOT"]).resolve()
            namespace = types.ModuleType("scgas_live_probe")
            namespace.__path__ = [str(root / "custom_components" / "scgas")]
            sys.modules[namespace.__name__] = namespace
            with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
                client = importlib.import_module("scgas_live_probe.client")
            normalize = importlib.import_module("scgas_live_probe.normalize")
            report = check(client.query, customer_id, customer_name, normalize.normalize_bill)
    except Exception:
        pass  # No exception text, traceback, response, or account information.
    report["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report["version"] = version if re.fullmatch(r"v\d+\.\d+\.\d+", version) else "unknown"
    print(json.dumps(report))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## 欣中實際查詢檢查\n\n")
            for key, value in report.items():
                stream.write(f"- {key}: `{value}`\n")
            stream.write("\nGitHub 雲端、單一測試帳戶、最新一期帳單；不驗證 HA Recorder 或所有帳戶。\n")
    return 0 if report["status"] == "available" else 1


if __name__ == "__main__":
    sys.exit(main())
