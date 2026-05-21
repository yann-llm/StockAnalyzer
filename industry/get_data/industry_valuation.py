"""Fetch Eastmoney industry valuation data."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request

from eastmoney_http import eastmoney_urlopen
from .industry_common import DEFAULT_TIMEOUT, EastmoneyIndustryCapitalFlowError, data_rows, date_only, datacenter_get, normalize_industry_code


VALUATION_DETAIL_PAGE_URL = "https://data.eastmoney.com/gzfx/detail/{stock_code}.html"


def _extract_js_object(html: str, var_name: str) -> dict[str, Any]:
    match = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*(\{{.*?\}})\s*;", html, re.S)
    if not match:
        return {}
    return json.loads(match.group(1))


def fetch_valuation_industry_mapping(stock_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch valuation industry mapping from a representative stock valuation page."""
    code = str(stock_code).strip()
    if not code:
        raise ValueError("stock_code is required for industry valuation mapping")

    request = Request(VALUATION_DETAIL_PAGE_URL.format(stock_code=code), headers={"User-Agent": "Mozilla/5.0"})
    try:
        with eastmoney_urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyIndustryCapitalFlowError(f"failed to fetch valuation mapping for {code}: {exc}") from exc

    stock_info = _extract_js_object(html, "stockInfo")
    hy_info = _extract_js_object(html, "hyInfo")
    valuation_board_code = hy_info.get("hyCode")
    if not valuation_board_code:
        raise EastmoneyIndustryCapitalFlowError(f"valuation industry code not found on detail page for {code}")

    return {
        "stock_code": code,
        "stock_info": stock_info,
        "hy_info": hy_info,
        "bk_code": stock_info.get("hycode"),
        "industry_name": stock_info.get("hyname") or hy_info.get("hyName"),
        "valuation_board_code": valuation_board_code,
    }


def fetch_industry_valuation(
    industry_code: str | int,
    stock_code: str | int | None = None,
    trade_date: str | None = None,
    rank_page_size: int = 200,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch industry valuation stats and in-industry valuation ranking."""
    codes = normalize_industry_code(industry_code)
    if stock_code is None:
        return {
            "module": "valuation",
            "codes": codes,
            "raw": {},
            "parsed": {"stats": [], "rank": []},
            "missing_reason": "stock_code is required to resolve valuation industry code",
        }

    mapping = fetch_valuation_industry_mapping(stock_code, timeout)
    board_code = mapping["valuation_board_code"]
    stats_payload = datacenter_get(
        {
            "reportName": "RPT_VALUEINDUSTRY_STA",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(BOARD_CODE="{board_code}")',
            "pageNumber": "1",
            "pageSize": "10",
        },
        timeout,
    )
    stats_rows = data_rows(stats_payload)
    rank_trade_date = trade_date or date_only(stats_rows[0].get("TRADE_DATE") if stats_rows else None)

    filters = [f'(BOARD_CODE="{board_code}")']
    if rank_trade_date:
        filters.append(f"(TRADE_DATE='{rank_trade_date}')")
    rank_payload = datacenter_get(
        {
            "reportName": "RPT_VALUEANALYSIS_DET",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
            "filter": "".join(filters),
            "sortColumns": "PE_TTM",
            "sortTypes": "1",
            "pageNumber": "1",
            "pageSize": str(rank_page_size),
        },
        timeout,
    )
    return {
        "module": "valuation",
        "codes": codes,
        "mapping": mapping,
        "raw": {"stats": stats_payload, "rank": rank_payload},
        "parsed": {"stats": stats_rows, "rank": data_rows(rank_payload)},
    }
