"""Industry trend-data helpers."""

from .get_data.industry_capital_flow_fetcher import (
    fetch_10d_industry_capital_flow,
    fetch_5d_industry_capital_flow,
    fetch_industry_capital_flow,
    fetch_today_industry_capital_flow,
)
from .get_data.industry_common import EastmoneyIndustryCapitalFlowError, normalize_industry_code
from .get_data.industry_index import (
    fetch_industry_index_kline,
    fetch_industry_index_snapshot,
)
from .get_data.industry_margin_trading import fetch_industry_margin_trading
from .get_data.industry_market import fetch_industry_market
from .get_data.industry_report import fetch_industry_reports
from .get_data.industry_trend_fetcher import fetch_industry_trend_data
from .get_data.industry_valuation import fetch_industry_valuation, fetch_valuation_industry_mapping
from .data_cleaner.industry_trend_cleaner import clean_industry_trend_data
from .data_cleaner.industry_trend_file_cleaner import build_industry_data_from_raw_files, clean_industry_raw_files

clean_industry_capital_flow = clean_industry_trend_data

__all__ = [
    "EastmoneyIndustryCapitalFlowError",
    "clean_industry_capital_flow",
    "clean_industry_raw_files",
    "clean_industry_trend_data",
    "build_industry_data_from_raw_files",
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
