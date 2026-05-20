"""Clean industry index modules."""

from __future__ import annotations

from typing import Any

from .cleaning_common import number, ratio, round_number


def compact_index_snapshot(module: dict[str, Any]) -> dict[str, Any]:
    parsed = module.get("parsed", {})
    up_count = number(parsed.get("up_count")) or 0
    down_count = number(parsed.get("down_count")) or 0
    return {
        "industry_code": parsed.get("industry_code"),
        "industry_name": parsed.get("industry_name"),
        "latest_point": round_number(parsed.get("latest_point")),
        "change_rate": round_number(parsed.get("change_rate")),
        "change_amount": round_number(parsed.get("change_amount")),
        "open": round_number(parsed.get("open")),
        "high": round_number(parsed.get("high")),
        "low": round_number(parsed.get("low")),
        "previous_close": round_number(parsed.get("previous_close")),
        "amount": round_number(parsed.get("amount"), 2),
        "volume": round_number(parsed.get("volume"), 2),
        "amplitude": round_number(parsed.get("amplitude")),
        "turnover_rate": round_number(parsed.get("turnover_rate")),
        "up_count": int(up_count),
        "down_count": int(down_count),
        "breadth_up_ratio": ratio(up_count, up_count + down_count),
        "top_stock_name": parsed.get("top_stock_name"),
        "top_stock_code": parsed.get("top_stock_code"),
        "top_stock_change_rate": round_number(parsed.get("top_stock_change_rate")),
    }


def _pct_change(rows: list[dict[str, Any]], periods: int) -> float | None:
    if len(rows) <= periods:
        return None
    latest = number(rows[-1].get("close"))
    base = number(rows[-1 - periods].get("close"))
    if latest is None or base in (None, 0):
        return None
    return round((latest / base - 1) * 100, 4)


def _avg_amount(rows: list[dict[str, Any]], periods: int) -> float | None:
    values = [number(row.get("amount")) for row in rows[-periods:]]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def compact_index_kline(module: dict[str, Any], tail_limit: int) -> dict[str, Any]:
    parsed = module.get("parsed", {})
    rows = parsed.get("rows", [])
    latest = rows[-1] if rows else {}
    avg_5 = _avg_amount(rows, 5)
    latest_amount = number(latest.get("amount"))
    return {
        "industry_code": parsed.get("industry_code"),
        "industry_name": parsed.get("industry_name"),
        "kline_total": parsed.get("kline_total"),
        "latest": {
            "date": latest.get("date"),
            "open": round_number(latest.get("open")),
            "close": round_number(latest.get("close")),
            "high": round_number(latest.get("high")),
            "low": round_number(latest.get("low")),
            "amount": round_number(latest.get("amount"), 2),
            "change_rate": round_number(latest.get("change_rate")),
            "turnover_rate": round_number(latest.get("turnover_rate")),
        },
        "returns": {
            "5d": _pct_change(rows, 5),
            "10d": _pct_change(rows, 10),
            "20d": _pct_change(rows, 20),
        },
        "amount": {
            "latest": round_number(latest_amount, 2),
            "avg_5d": avg_5,
            "latest_to_5d_avg": ratio(latest_amount, avg_5),
        },
        "recent_rows": [
            {
                "date": row.get("date"),
                "open": round_number(row.get("open")),
                "close": round_number(row.get("close")),
                "high": round_number(row.get("high")),
                "low": round_number(row.get("low")),
                "volume": round_number(row.get("volume"), 2),
                "change_rate": round_number(row.get("change_rate")),
                "change_amount": round_number(row.get("change_amount")),
                "amount": round_number(row.get("amount"), 2),
                "amplitude": round_number(row.get("amplitude")),
                "turnover_rate": round_number(row.get("turnover_rate")),
            }
            for row in rows[-tail_limit:]
        ],
    }
