"""Fetch Eastmoney industry index snapshot and K-line data."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .industry_common import (
    DEFAULT_TIMEOUT,
    PUSH2_KLINE_URL,
    PUSH2_STOCK_URL,
    STOCK_UT,
    normalize_industry_code,
    request_push_json_from_page,
    with_raw,
)


INDEX_SNAPSHOT_FIELDS = (
    "f57,f58,f107,f43,f169,f170,f171,f47,f48,f60,f46,f44,f45,"
    "f168,f113,f114,f444,f445,f446,f447"
)
KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"


def fetch_industry_index_snapshot(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch the industry index quote snapshot."""
    codes = normalize_industry_code(industry_code)
    payload = request_push_json_from_page(
        codes["secid"],
        PUSH2_STOCK_URL,
        {
            "fltt": "2",
            "invt": "2",
            "secid": codes["secid"],
            "fields": INDEX_SNAPSHOT_FIELDS,
            "ut": STOCK_UT,
        },
        timeout,
    )
    row = payload.get("data") or {}
    parsed = {
        "industry_code": row.get("f57"),
        "industry_name": row.get("f58"),
        "market": row.get("f107"),
        "latest_point": row.get("f43"),
        "change_amount": row.get("f169"),
        "change_rate": row.get("f170"),
        "amplitude": row.get("f171"),
        "volume": row.get("f47"),
        "amount": row.get("f48"),
        "previous_close": row.get("f60"),
        "open": row.get("f46"),
        "high": row.get("f44"),
        "low": row.get("f45"),
        "turnover_rate": row.get("f168"),
        "up_count": row.get("f113"),
        "down_count": row.get("f114"),
        "top_stock_change_rate": row.get("f444"),
        "top_stock_name": row.get("f445"),
        "top_stock_code": row.get("f446"),
        "top_stock_market": row.get("f447"),
    }
    return {"module": "index_snapshot", "codes": codes, **with_raw(parsed, row)}


def _yyyymmdd(value: date | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")


def fetch_industry_index_kline(
    industry_code: str | int,
    beg: date | str | None = None,
    end: date | str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch daily K-line rows for the industry board index."""
    codes = normalize_industry_code(industry_code)
    today = date.today()
    payload = request_push_json_from_page(
        codes["secid"],
        PUSH2_KLINE_URL,
        {
            "secid": codes["secid"],
            "fields1": KLINE_FIELDS1,
            "fields2": KLINE_FIELDS2,
            "klt": "101",
            "fqt": "1",
            "beg": _yyyymmdd(beg or today - timedelta(days=90)),
            "end": _yyyymmdd(end or today),
        },
        timeout,
    )
    data = payload.get("data") or {}
    rows = []
    for line in data.get("klines") or []:
        parts = str(line).split(",")
        if len(parts) < 11:
            continue
        rows.append(
            {
                "date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
                "amount": parts[6],
                "amplitude": parts[7],
                "change_rate": parts[8],
                "change_amount": parts[9],
                "turnover_rate": parts[10],
            }
        )
    parsed = {
        "industry_code": data.get("code"),
        "industry_name": data.get("name"),
        "market": data.get("market"),
        "decimal": data.get("decimal"),
        "kline_total": data.get("dktotal"),
        "pre_k_price": data.get("preKPrice"),
        "rows": rows,
    }
    return {"module": "index_kline", "codes": codes, "raw": data, "parsed": parsed}
