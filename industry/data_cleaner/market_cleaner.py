"""Clean industry market quote module."""

from __future__ import annotations

from typing import Any

from .cleaning_common import number, ratio, round_number


def compact_market(module: dict[str, Any]) -> dict[str, Any]:
    parsed = module.get("parsed", {})
    up_count = number(parsed.get("up_count")) or 0
    down_count = number(parsed.get("down_count")) or 0
    flat_count = number(parsed.get("flat_count")) or 0
    breadth_total = up_count + down_count + flat_count
    return {
        "industry_code": parsed.get("industry_code"),
        "industry_name": parsed.get("industry_name"),
        "latest_point": round_number(parsed.get("latest_point")),
        "change_rate": round_number(parsed.get("change_rate")),
        "change_amount": round_number(parsed.get("change_amount")),
        "amount": round_number(parsed.get("amount"), 2),
        "volume": round_number(parsed.get("volume"), 2),
        "amplitude": round_number(parsed.get("amplitude")),
        "turnover_rate": round_number(parsed.get("turnover_rate")),
        "pe_quote": round_number(parsed.get("pe")),
        "volume_ratio": round_number(parsed.get("volume_ratio")),
        "total_market_cap": round_number(parsed.get("total_market_cap"), 2),
        "free_float_market_cap": round_number(parsed.get("free_float_market_cap"), 2),
        "main_net_inflow": round_number(parsed.get("main_net_inflow"), 2),
        "up_count": int(up_count),
        "down_count": int(down_count),
        "flat_count": int(flat_count),
        "breadth_up_ratio": ratio(up_count, breadth_total),
        "top_stock_name": parsed.get("top_stock_name"),
        "top_stock_code": parsed.get("top_stock_code"),
        "top_stock_change_rate": round_number(parsed.get("top_stock_change_rate")),
    }
