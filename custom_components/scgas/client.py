"""欣中官方氣費查詢；一次 HTTP 回應取得所有可查帳單。"""

from datetime import datetime, timezone
import re

from .portal import ScgasClient, QueryError as PortalError


def now():
    return datetime.now(timezone.utc).isoformat()


class QueryError(Exception):
    def __init__(self, code, *, verification_status="not_run"):
        super().__init__(code)
        self.code = code
        self.verification_status = verification_status


def validate_month(month):
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise QueryError("invalid_month")
    return month


def query(
    customer_id, customer_name, *, history_limit=None, known_months=(), refresh_history=False, requested_month=None
):
    if requested_month is not None:
        validate_month(requested_month)
    if not isinstance(customer_id, str) or not re.fullmatch(r"[0-9]{6}", customer_id):
        raise QueryError("invalid_auth")
    started = now()
    try:
        portal = ScgasClient()
        portal.probe()
        records = portal.query(customer_id, customer_name, "usage")
    except PortalError as error:
        # No raw response, URL, name, cookie, or upstream exception escapes this boundary.
        code = (
            "cannot_connect"
            if "HTTPS" in str(error)
            else "upstream_rejected"
            if "未取得帳單" in str(error)
            else "site_changed"
        )
        raise QueryError(code, verification_status="unknown") from None
    from .normalize import from_record

    bills = sorted((from_record(record, now()) for record in records), key=lambda b: b["month"], reverse=True)
    available = [bill["month"] for bill in bills]
    # Do not silently overwrite multiple charges in the same month.
    if len(set(available)) != len(available):
        raise QueryError("duplicate_month", verification_status="accepted")
    if requested_month:
        bills = [bill for bill in bills if bill["month"] == requested_month]
        if not bills:
            raise QueryError("month_unavailable", verification_status="accepted")
    elif history_limit is None:
        bills = bills[:1]
    elif history_limit:
        bills = bills[:history_limit]
    # Refresh every returned bill: payment state/corrections can change on older bills.
    return {
        "bills": bills,
        "available_months": available,
        "verification_status": "accepted",
        "status": "success",
        "error_code": None,
        "started_at": started,
        "finished_at": now(),
    }


def validate_credentials(customer_id, customer_name):
    return query(customer_id, customer_name, history_limit=0)
