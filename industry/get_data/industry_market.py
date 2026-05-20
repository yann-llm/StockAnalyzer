"""Fetch Eastmoney single-industry market quote data."""

from __future__ import annotations

from typing import Any

from .industry_common import DEFAULT_TIMEOUT, fetch_ulist, normalize_industry_code, with_raw


MARKET_FIELDS = (
    "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f20,f21,f62,"
    "f104,f105,f106,f128,f136,f140,f152"
)


def fetch_industry_market(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch the single-industry quote row used by the industry market review."""
    codes = normalize_industry_code(industry_code)
    row = fetch_ulist(codes["secid"], MARKET_FIELDS, timeout)
    parsed = {
        "industry_code": row.get("f12"),
        "market": row.get("f13"),
        "industry_name": row.get("f14"),
        "latest_point": row.get("f2"),
        "change_rate": row.get("f3"),
        "change_amount": row.get("f4"),
        "volume": row.get("f5"),
        "amount": row.get("f6"),
        "amplitude": row.get("f7"),
        "turnover_rate": row.get("f8"),
        "pe": row.get("f9"),
        "volume_ratio": row.get("f10"),
        "total_market_cap": row.get("f20"),
        "free_float_market_cap": row.get("f21"),
        "main_net_inflow": row.get("f62"),
        "up_count": row.get("f104"),
        "down_count": row.get("f105"),
        "flat_count": row.get("f106"),
        "top_stock_name": row.get("f128"),
        "top_stock_change_rate": row.get("f136"),
        "top_stock_code": row.get("f140"),
    }
    return {"module": "market", "codes": codes, **with_raw(parsed, row)}
