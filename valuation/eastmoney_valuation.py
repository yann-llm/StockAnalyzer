"""Fetch valuation data from Eastmoney."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request

from eastmoney_http import eastmoney_urlopen


API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DEFAULT_TIMEOUT = 15


class EastmoneyValuationError(RuntimeError):
    """Raised when valuation data cannot be fetched."""


def _request(report_name: str, filter_expr: str, sort_field: str, page_size: int, timeout: int) -> list[dict[str, Any]]:
    params = {
        "sortColumns": sort_field,
        "sortTypes": "-1",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "columns": "ALL",
        "filter": filter_expr,
        "reportName": report_name,
        "source": "WEB",
        "client": "WEB",
    }
    request = Request(f"{API_URL}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with eastmoney_urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyValuationError(f"failed to fetch {report_name}: {exc}") from exc
    return payload.get("result", {}).get("data", []) or []


def fetch_stock_valuation_detail(
    stock_code: str,
    page_size: int = 60,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch stock valuation detail time series."""
    return _request(
        "RPT_VALUEANALYSIS_DET",
        f'(SECURITY_CODE="{stock_code}")',
        "TRADE_DATE",
        page_size,
        timeout,
    )


def fetch_industry_valuation_rank(
    board_code: str,
    page_size: int = 200,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch valuation rows for all stocks in one industry."""
    return _request(
        "RPT_VALUEANALYSIS_DET",
        f'(BOARD_CODE="{board_code}")',
        "TRADE_DATE",
        page_size,
        timeout,
    )


def fetch_industry_valuation_stats(
    board_code: str,
    page_size: int = 10,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch industry average and median valuation stats."""
    return _request(
        "RPT_VALUEINDUSTRY_STA",
        f'(BOARD_CODE="{board_code}")',
        "TRADE_DATE",
        page_size,
        timeout,
    )


def fetch_valuation_data(
    stock_code: str,
    board_code: str | None = None,
    detail_size: int = 60,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch valuation detail and optional industry comparison data."""
    detail = fetch_stock_valuation_detail(stock_code, detail_size, timeout)
    if board_code is None and detail:
        board_code = detail[0].get("BOARD_CODE")
    return {
        "stock_code": stock_code,
        "board_code": board_code,
        "source": "eastmoney",
        "modules": {
            "stock_detail": detail,
            "industry_rank": fetch_industry_valuation_rank(board_code, 200, timeout) if board_code else [],
            "industry_stats": fetch_industry_valuation_stats(board_code, 10, timeout) if board_code else [],
        },
    }
