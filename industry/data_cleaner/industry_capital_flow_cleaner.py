"""Compatibility exports for Eastmoney industry data cleaners."""

from __future__ import annotations

from .industry_trend_cleaner import clean_industry_trend_data

clean_industry_capital_flow = clean_industry_trend_data

__all__ = ["clean_industry_capital_flow", "clean_industry_trend_data"]
