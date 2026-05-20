"""Fetch Eastmoney single-industry capital-flow data."""

from __future__ import annotations

from typing import Any

from .industry_common import DEFAULT_TIMEOUT, fetch_ulist, normalize_industry_code, with_raw


CAPITAL_FLOW_FIELDS = (
    "f12,f13,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,"
    "f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,"
    "f160,f174,f175,f176,f177,f178,f179,f180,f181,f182,f183,"
    "f204,f205,f257,f258,f260,f261"
)


def fetch_industry_capital_flow(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch today, 5-day, and 10-day capital-flow fields for one industry."""
    codes = normalize_industry_code(industry_code)
    row = fetch_ulist(codes["secid"], CAPITAL_FLOW_FIELDS, timeout)
    parsed = {
        "industry_code": row.get("f12"),
        "market": row.get("f13"),
        "industry_name": row.get("f14"),
        "latest_point": row.get("f2"),
        "periods": {
            "today": {
                "change_rate": row.get("f3"),
                "main_net_inflow": row.get("f62"),
                "main_net_inflow_ratio": row.get("f184"),
                "super_large_net_inflow": row.get("f66"),
                "super_large_net_inflow_ratio": row.get("f69"),
                "large_net_inflow": row.get("f72"),
                "large_net_inflow_ratio": row.get("f75"),
                "medium_net_inflow": row.get("f78"),
                "medium_net_inflow_ratio": row.get("f81"),
                "small_net_inflow": row.get("f84"),
                "small_net_inflow_ratio": row.get("f87"),
                "top_stock_name": row.get("f204"),
                "top_stock_code": row.get("f205"),
            },
            "5d": {
                "change_rate": row.get("f109"),
                "main_net_inflow": row.get("f164"),
                "main_net_inflow_ratio": row.get("f165"),
                "super_large_net_inflow": row.get("f166"),
                "super_large_net_inflow_ratio": row.get("f167"),
                "large_net_inflow": row.get("f168"),
                "large_net_inflow_ratio": row.get("f169"),
                "medium_net_inflow": row.get("f170"),
                "medium_net_inflow_ratio": row.get("f171"),
                "small_net_inflow": row.get("f172"),
                "small_net_inflow_ratio": row.get("f173"),
                "top_stock_name": row.get("f257"),
                "top_stock_code": row.get("f258"),
            },
            "10d": {
                "change_rate": row.get("f160"),
                "main_net_inflow": row.get("f174"),
                "main_net_inflow_ratio": row.get("f175"),
                "super_large_net_inflow": row.get("f176"),
                "super_large_net_inflow_ratio": row.get("f177"),
                "large_net_inflow": row.get("f178"),
                "large_net_inflow_ratio": row.get("f179"),
                "medium_net_inflow": row.get("f180"),
                "medium_net_inflow_ratio": row.get("f181"),
                "small_net_inflow": row.get("f182"),
                "small_net_inflow_ratio": row.get("f183"),
                "top_stock_name": row.get("f260"),
                "top_stock_code": row.get("f261"),
            },
        },
    }
    return {"module": "capital_flow", "codes": codes, **with_raw(parsed, row)}


def fetch_today_industry_capital_flow(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Compatibility wrapper returning the today capital-flow period for one industry."""
    data = fetch_industry_capital_flow(industry_code, timeout)
    return {"module": "capital_flow_today", "codes": data["codes"], "raw": data["raw"], "parsed": data["parsed"]["periods"]["today"]}


def fetch_5d_industry_capital_flow(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Compatibility wrapper returning the 5-day capital-flow period for one industry."""
    data = fetch_industry_capital_flow(industry_code, timeout)
    return {"module": "capital_flow_5d", "codes": data["codes"], "raw": data["raw"], "parsed": data["parsed"]["periods"]["5d"]}


def fetch_10d_industry_capital_flow(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Compatibility wrapper returning the 10-day capital-flow period for one industry."""
    data = fetch_industry_capital_flow(industry_code, timeout)
    return {"module": "capital_flow_10d", "codes": data["codes"], "raw": data["raw"], "parsed": data["parsed"]["periods"]["10d"]}
