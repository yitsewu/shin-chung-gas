"""欣中氣費唯讀爬蟲，Python 標準函式庫；不保存查詢身分或原始網頁。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

BASE = "https://www.scgas.com.tw/doc/"
MODES = {"usage": "0", "fees": "1"}
COMMON = [
    "應收日期",
    "用戶號碼",
    "從量費",
    "表/開關租金",
    "追收",
    "退還",
    "基本費",
    "計費時間",
    "違約金",
    "合計",
    "銷帳碼",
    "繳費期限",
]
HEADERS = {"fees": COMMON, "usage": COMMON[:2] + ["抄表度", "使用度數", "抄表狀況"] + COMMON[2:]}
KEYS = dict(
    zip(
        COMMON,
        [
            "receivable_date",
            "customer_id",
            "usage_fee",
            "rental_fee",
            "additional_charge",
            "refund",
            "basic_fee",
            "billing_period",
            "penalty",
            "total",
            "payment_code",
            "due_date",
        ],
    )
)
KEYS.update({"抄表度": "meter_reading", "使用度數": "usage_m3", "抄表狀況": "reading_status"})
NUMERIC = {
    "usage_fee",
    "rental_fee",
    "additional_charge",
    "refund",
    "basic_fee",
    "penalty",
    "total",
    "meter_reading",
    "usage_m3",
}


class QueryError(Exception):
    """安全的錯誤訊息，不包含回應或查詢 URL。"""


def compact(value):
    return re.sub(r"\s+", "", value)


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tables, self.forms, self.inputs = [], [], []
        self.table = self.row = self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append(attrs)
        if tag == "input":
            self.inputs.append(attrs)
        if tag == "table":
            if self.table is not None:
                raise QueryError("網站出現巢狀表格，請更新 parser。")
            self.table = []
        if tag == "tr" and self.table is not None:
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            if attrs.get("colspan", "1") != "1" or attrs.get("rowspan", "1") != "1":
                raise QueryError("網站表格合併欄位已變更。")
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        if tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def roc_date(value):
    value = compact(value)
    if not value:
        return None
    if not re.fullmatch(r"\d{7}", value):
        raise QueryError("日期格式已變更。")
    try:
        return date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:])).isoformat()
    except ValueError:
        raise QueryError("網站回傳無效日期。") from None


def parse_result(html, mode, customer_id):
    tables = Page(html).tables
    candidates = [t for t in tables if t and [compact(c) for c in t[0]] == HEADERS[mode]]
    if len(candidates) != 1 or len(candidates[0]) < 2:
        raise QueryError("查詢未取得帳單：可能身分不符、沒有帳單或網站格式已變更。")
    records = []
    for cells in candidates[0][1:]:
        # 官方已繳費列省略最後一個「繳費期限」td；保留缺值，不推算期限。
        if len(cells) == len(HEADERS[mode]) - 1:
            cells = cells + [""]
        if len(cells) != len(HEADERS[mode]):
            raise QueryError("帳單欄數已變更。")
        raw = dict(zip(HEADERS[mode], cells))
        if raw["用戶號碼"].strip() != customer_id:
            raise QueryError("回應用戶不符，已停止輸出。")
        record = {}
        for label, value in raw.items():
            key = KEYS[label]
            if key == "customer_id":
                continue
            value = value.strip()
            if key in NUMERIC:
                try:
                    number = Decimal(value.replace(",", ""))
                    if not number.is_finite():
                        raise InvalidOperation
                    record[key] = int(number) if number == number.to_integral_value() else float(number)
                except InvalidOperation:
                    raise QueryError("帳單數字格式已變更。") from None
            elif key in ("receivable_date", "due_date"):
                record[key] = roc_date(value)
            elif key == "billing_period":
                parts = compact(value).split("~")
                if len(parts) != 2:
                    raise QueryError("計費期間格式已變更。")
                record["period_start"], record["period_end"] = map(roc_date, parts)
                if (
                    not record["period_start"]
                    or not record["period_end"]
                    or record["period_start"] > record["period_end"]
                ):
                    raise QueryError("計費期間無效。")
            else:
                record[key] = value or None
        if not record["receivable_date"]:
            raise QueryError("帳單缺少應收日期。")
        record["payment_status"] = "paid" if record["payment_code"] else "unpaid"
        records.append(record)
    return records


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise QueryError("網站要求重新導向，已停止以避免轉送查詢身分。")


class ScgasClient:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.opener = build_opener(NoRedirect(), HTTPCookieProcessor(CookieJar()))

    def _get(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.scgas.com.tw"
            or parsed.path not in ("/doc/gas.asp", "/doc/gbm02.asp")
        ):
            raise QueryError("查詢目的地不符允許範圍。")
        try:
            req = Request(url, headers={"User-Agent": "ScgasReadOnlyCrawler/1.0", "Accept": "text/html"})
            with self.opener.open(req, timeout=self.timeout) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise QueryError("回應超過大小限制。")
                return body.decode("cp950")
        except QueryError:
            raise
        except Exception:
            raise QueryError("HTTPS 連線或頁面解碼失敗；未自動重試。") from None

    def probe(self):
        page = Page(self._get(BASE + "gas.asp"))
        if (
            len(page.forms) != 1
            or page.forms[0].get("action") != "gbm02.asp"
            or page.forms[0].get("method", "").lower() != "get"
        ):
            raise QueryError("官方查詢表單已變更。")
        if not {"wkapno", "wkname", "p1", "R1"} <= {i.get("name") for i in page.inputs}:
            raise QueryError("官方查詢欄位已變更。")
        if {i.get("value") for i in page.inputs if i.get("name") == "R1"} != {"0", "1"}:
            raise QueryError("查詢模式已變更。")
        return {"status": "ok", "encoding": "cp950", "modes": list(MODES)}

    def query(self, customer_id, customer_name, mode="usage"):
        if not re.fullmatch(r"\d{6}", customer_id) or not customer_name.strip() or len(customer_name) > 40:
            raise QueryError("請提供六碼用戶號碼及有效戶名。")
        if mode not in MODES:
            raise QueryError("查詢模式無效。")
        try:
            query = urlencode(
                {"p1": "1", "wkapno": customer_id, "wkname": customer_name, "R1": MODES[mode]},
                encoding="cp950",
                errors="strict",
            )
        except UnicodeEncodeError:
            raise QueryError("戶名無法以官方 Big5 編碼傳送。") from None
        return parse_result(self._get(BASE + "gbm02.asp?" + query), mode, customer_id)
