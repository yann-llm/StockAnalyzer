"""Clean industry capital-flow module."""

from __future__ import annotations

from typing import Any

from .cleaning_common import round_number


def compact_flow_period(period: dict[str, Any]) -> dict[str, Any]:
    return {
        "change_rate": round_number(period.get("change_rate")),
        "main_net_inflow": round_number(period.get("main_net_inflow"), 2),
        "main_net_inflow_ratio": round_number(period.get("main_net_inflow_ratio")),
        "super_large_net_inflow": round_number(period.get("super_large_net_inflow"), 2),
        "super_large_net_inflow_ratio": round_number(period.get("super_large_net_inflow_ratio")),
        "large_net_inflow": round_number(period.get("large_net_inflow"), 2),
        "large_net_inflow_ratio": round_number(period.get("large_net_inflow_ratio")),
        "medium_net_inflow": round_number(period.get("medium_net_inflow"), 2),
        "medium_net_inflow_ratio": round_number(period.get("medium_net_inflow_ratio")),
        "small_net_inflow": round_number(period.get("small_net_inflow"), 2),
        "small_net_inflow_ratio": round_number(period.get("small_net_inflow_ratio")),
        "top_stock_name": period.get("top_stock_name"),
        "top_stock_code": period.get("top_stock_code"),
    }


def compact_capital_flow(module: dict[str, Any]) -> dict[str, Any]:
    parsed = module.get("parsed", {})
    periods = parsed.get("periods", {})
    return {
        "industry_code": parsed.get("industry_code"),
        "industry_name": parsed.get("industry_name"),
        "latest_point": round_number(parsed.get("latest_point")),
        "periods": {period: compact_flow_period(periods.get(period, {})) for period in ("today", "5d", "10d")},
    }
