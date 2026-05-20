"""Aggregate Eastmoney industry data modules."""

from __future__ import annotations

from datetime import date
from typing import Any

from .industry_capital_flow_fetcher import fetch_industry_capital_flow
from .industry_common import DEFAULT_TIMEOUT, normalize_industry_code
from .industry_index import fetch_industry_index_kline, fetch_industry_index_snapshot
from .industry_margin_trading import fetch_industry_margin_trading
from .industry_market import fetch_industry_market
from .industry_report import fetch_industry_reports
from .industry_valuation import fetch_industry_valuation


def fetch_industry_trend_data(
    industry_code: str | int,
    stock_code: str | int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    kline_beg: date | str | None = None,
    kline_end: date | str | None = None,
    valuation_trade_date: str | None = None,
) -> dict[str, Any]:
    """Fetch all review-backed modules for one industry code."""
    codes = normalize_industry_code(industry_code)
    return {
        "source": "eastmoney",
        "codes": codes,
        "modules": {
            "market": fetch_industry_market(industry_code, timeout),
            "capital_flow": fetch_industry_capital_flow(industry_code, timeout),
            "index_snapshot": fetch_industry_index_snapshot(industry_code, timeout),
            "index_kline": fetch_industry_index_kline(industry_code, kline_beg, kline_end, timeout),
            "reports": fetch_industry_reports(industry_code, timeout),
            "margin_trading": fetch_industry_margin_trading(industry_code, timeout),
            "valuation": fetch_industry_valuation(industry_code, stock_code, valuation_trade_date, timeout=timeout),
        },
    }
