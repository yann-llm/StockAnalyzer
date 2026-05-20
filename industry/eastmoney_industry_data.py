"""Compatibility exports for Eastmoney industry data fetchers."""

from __future__ import annotations

from .get_data.industry_capital_flow_fetcher import (
    fetch_10d_industry_capital_flow,
    fetch_5d_industry_capital_flow,
    fetch_industry_capital_flow,
    fetch_today_industry_capital_flow,
)
from .get_data.industry_common import DEFAULT_TIMEOUT, EastmoneyIndustryCapitalFlowError, normalize_industry_code
from .get_data.industry_index import fetch_industry_index_kline, fetch_industry_index_snapshot
from .get_data.industry_margin_trading import fetch_industry_margin_trading
from .get_data.industry_market import fetch_industry_market
from .get_data.industry_report import fetch_industry_reports
from .get_data.industry_trend_fetcher import fetch_industry_trend_data
from .get_data.industry_valuation import fetch_industry_valuation, fetch_valuation_industry_mapping

__all__ = [
    "DEFAULT_TIMEOUT",
    "EastmoneyIndustryCapitalFlowError",
    "fetch_10d_industry_capital_flow",
    "fetch_5d_industry_capital_flow",
    "fetch_industry_capital_flow",
    "fetch_industry_index_kline",
    "fetch_industry_index_snapshot",
    "fetch_industry_margin_trading",
    "fetch_industry_market",
    "fetch_industry_reports",
    "fetch_industry_trend_data",
    "fetch_industry_valuation",
    "fetch_valuation_industry_mapping",
    "fetch_today_industry_capital_flow",
    "normalize_industry_code",
]
