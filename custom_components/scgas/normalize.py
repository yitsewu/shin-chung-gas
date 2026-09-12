"""欣中帳單映射；使用白名單並保留原始計費日期。"""

from datetime import date, timedelta
from decimal import Decimal
from .models import Bill

FEE_MAP = {
    "usage_fee": "從量費",
    "rental_fee": "表/開關租金",
    "additional_charge": "追收",
    "refund": "退還",
    "basic_fee": "基本費",
    "penalty": "違約金",
}
FEE_LABELS = tuple(FEE_MAP.values())
DATE_LABELS = ("應收日期", "繳費期限")
SAFE_LABELS = set(
    FEE_LABELS + DATE_LABELS + ("使用度數", "合計", "計費起日", "計費迄日", "抄表度", "抄表狀況", "繳費狀態")
)


def safe_fields(fields):
    return {key: str(value)[:256] for key, value in fields.items() if key in SAFE_LABELS and value is not None}


def roc_date(value):
    return date.fromisoformat(value) if value else None


def from_record(record, fetched_at):
    fields = {label: record[key] for key, label in FEE_MAP.items()}
    fields.update(
        {
            "使用度數": record["usage_m3"],
            "合計": record["total"],
            "計費起日": record["period_start"],
            "計費迄日": record["period_end"],
            "應收日期": record["receivable_date"],
            "繳費期限": record["due_date"],
            "抄表度": record["meter_reading"],
            "抄表狀況": record["reading_status"],
            "繳費狀態": record["payment_status"],
        }
    )
    return {"month": record["receivable_date"][:7], "fields": safe_fields(fields), "fetched_at": fetched_at}


def normalize_bill(raw):
    fields = safe_fields(raw["fields"])
    first, last = roc_date(fields["計費起日"]), roc_date(fields["計費迄日"])
    if first is None or last is None or first > last or (last - first).days > 400:
        raise ValueError("invalid_period")
    # Source periods are contiguous with the next period starting the following day.
    # Shared allocation model uses (start,end], so subtract one day once only.
    normalized = {
        **fields,
        "usage_m3": fields["使用度數"],
        "total_twd": fields["合計"],
        "period_start": first - timedelta(days=1),
        "period_end": last,
        "billing_start": first.isoformat(),
        "billing_end": last.isoformat(),
        "fee_breakdown": {label: Decimal(fields[label]) for label in FEE_LABELS if label in fields},
    }
    return Bill.from_fields(raw["month"], normalized, raw["fetched_at"])
