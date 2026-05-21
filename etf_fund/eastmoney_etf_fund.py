"""Fetch ETF fund archive pages from Eastmoney Fund F10."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen


FUND_F10_BASE_URL = "https://fundf10.eastmoney.com"
DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://fundf10.eastmoney.com/",
}

FUND_ARCHIVE_PAGES = {
    "profile": ("基本概况", "jbgk_{code}.html"),
    "nav_history": ("历史净值", "jjjz_{code}.html"),
    "stage_return": ("阶段涨幅", "jdzf_{code}.html"),
    "holdings": ("基金持仓", "ccmx_{code}.html"),
    "industry_allocation": ("行业配置", "hytz_{code}.html"),
    "asset_allocation": ("资产配置", "zcpz_{code}.html"),
    "scale_change": ("规模变动", "gmbd_{code}.html"),
}

FUND_ARCHIVE_DATASETS = {
    "holdings": {
        "url": f"{FUND_F10_BASE_URL}/FundArchivesDatas.aspx",
        "params": {"type": "jjcc", "topline": "10", "year": "", "month": ""},
    },
    "stage_return": {
        "url": f"{FUND_F10_BASE_URL}/FundArchivesDatas.aspx",
        "params": {"type": "jdzf"},
    },
    "scale_change": {
        "url": f"{FUND_F10_BASE_URL}/FundArchivesDatas.aspx",
        "params": {"type": "gmbd", "mode": "0"},
    },
    "nav_history": {
        "url": "https://api.fund.eastmoney.com/f10/lsjz",
        "params": {"pageIndex": "1", "pageSize": "60", "startDate": "", "endDate": ""},
    },
    "industry_allocation": {
        "url": "https://api.fund.eastmoney.com/f10/HYPZ/",
        "params": {"year": ""},
    },
}

ETF_FUND_MODULE_PAGES = {
    "etf_product_index": ("profile",),
    "etf_return_performance": ("nav_history", "stage_return"),
    "etf_risk_volatility": ("nav_history", "stage_return"),
    "etf_holding_exposure": ("holdings", "industry_allocation", "asset_allocation"),
    "etf_scale_liquidity": ("profile", "scale_change"),
}


class EastmoneyEtfFundError(RuntimeError):
    """Raised when Eastmoney ETF fund archive data cannot be fetched."""


def _fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    request = Request(url, headers=DEFAULT_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")
    except URLError as exc:
        raise EastmoneyEtfFundError(f"failed to fetch {url}: {exc}") from exc


def _fetch_dataset(stock_code: str, page_key: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any] | None:
    config = FUND_ARCHIVE_DATASETS.get(page_key)
    if not config:
        return None
    params = dict(config["params"])
    if page_key in {"nav_history", "industry_allocation"}:
        params["fundCode"] = stock_code
    else:
        params["code"] = stock_code
        params["rt"] = "0.1"
    url = f"{config['url']}?{urlencode(params)}"
    return {
        "url": url,
        "text": _fetch_html(url, timeout),
    }


def fetch_fund_archive_page(stock_code: str | int, page_key: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch one Fund F10 archive HTML page."""
    code = str(stock_code).strip()
    if page_key not in FUND_ARCHIVE_PAGES:
        raise ValueError(f"unsupported fund archive page: {page_key}")
    page_name, path_template = FUND_ARCHIVE_PAGES[page_key]
    url = f"{FUND_F10_BASE_URL}/{path_template.format(code=code)}"
    return {
        "page_key": page_key,
        "page_name": page_name,
        "url": url,
        "html": _fetch_html(url, timeout),
        "dataset": _fetch_dataset(code, page_key, timeout),
    }


def fetch_etf_fund_data(stock_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch the seven Fund F10 pages used by the ETF five-block score."""
    code = str(stock_code).strip()
    return {
        "stock_code": code,
        "source": "eastmoney_fundf10",
        "modules": {
            page_key: fetch_fund_archive_page(code, page_key, timeout)
            for page_key in FUND_ARCHIVE_PAGES
        },
    }


def fetch_etf_fund_module_data(
    stock_code: str | int,
    module_name: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch only the Fund F10 pages needed by one ETF analysis module."""
    code = str(stock_code).strip()
    page_keys = ETF_FUND_MODULE_PAGES.get(module_name)
    if not page_keys:
        raise ValueError(f"unsupported ETF fund module: {module_name}")
    return {
        "stock_code": code,
        "module": module_name,
        "source": "eastmoney_fundf10",
        "modules": {
            page_key: fetch_fund_archive_page(code, page_key, timeout)
            for page_key in page_keys
        },
    }
