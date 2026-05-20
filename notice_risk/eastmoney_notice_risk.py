"""Fetch notice-risk data from Eastmoney."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ANN_LIST_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
ANN_CONTENT_URL = "https://np-cnotice-stock.eastmoney.com/api/content/ann"
DEFAULT_TIMEOUT = 15


NOTICE_CATEGORIES = {
    "all": "0",
    "major_event": "5",
    "financial_report": "1",
    "financing": "2",
    "risk_warning": "3",
    "restructure": "6",
    "info_change": "4",
    "holding_change": "7",
}


class EastmoneyNoticeRiskError(RuntimeError):
    """Raised when notice-risk data cannot be fetched."""


def _request_json(url: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyNoticeRiskError(f"failed to fetch notice data: {exc}") from exc


def _parse_notice(item: dict[str, Any]) -> dict[str, Any]:
    columns = item.get("columns") or []
    codes = item.get("codes") or []
    return {
        "art_code": item.get("art_code"),
        "title": item.get("title") or item.get("title_ch"),
        "notice_date": _short_date(item.get("notice_date")),
        "display_time": item.get("display_time"),
        "publish_time": item.get("eiTime"),
        "sort_date": item.get("sort_date"),
        "columns": [{"code": col.get("column_code"), "name": col.get("column_name")} for col in columns],
        "stock": codes[0] if codes else {},
        "raw": item,
    }


def _short_date(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return value


def fetch_notice_list(
    stock_code: str,
    category: str = "all",
    page_size: int = 50,
    page_number: int = 1,
    s_node: str | int = 0,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch one notice category list."""
    f_node = NOTICE_CATEGORIES.get(category, category)
    params = {
        "ann_type": "A",
        "client_source": "web",
        "stock_list": stock_code,
        "page_index": str(page_number),
        "page_size": str(page_size),
        "f_node": f_node,
        "s_node": str(s_node),
    }

    payload = _request_json(ANN_LIST_URL, params, timeout)
    data = payload.get("data") or {}
    rows = data.get("list") or []
    return {
        "category": category,
        "f_node": f_node,
        "s_node": str(s_node),
        "page_number": data.get("page_index", page_number),
        "page_size": data.get("page_size", page_size),
        "total": data.get("total_hits", 0),
        "rows": [_parse_notice(item) for item in rows],
    }


def fetch_notice_content(
    art_code: str,
    page_number: int = 1,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch notice detail content by art_code."""
    params = {
        "art_code": art_code,
        "client_source": "web",
        "page_index": str(page_number),
    }
    payload = _request_json(ANN_CONTENT_URL, params, timeout)
    data = payload.get("data") or {}
    return {
        "art_code": data.get("art_code"),
        "notice_title": data.get("notice_title"),
        "notice_date": _short_date(data.get("notice_date")),
        "notice_content": data.get("notice_content"),
        "attach_url_web": data.get("attach_url_web"),
        "attach_type": data.get("attach_type"),
        "attach_size": data.get("attach_size"),
        "attach_list": data.get("attach_list") or [],
        "page_size": data.get("page_size"),
        "security": data.get("security") or [],
        "raw": data,
    }


def fetch_notice_risk_data(
    stock_code: str,
    page_size: int = 20,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch notice categories used by risk scoring."""
    categories = [
        "all",
        "major_event",
        "financial_report",
        "financing",
        "risk_warning",
        "restructure",
        "info_change",
        "holding_change",
    ]
    return {
        "stock_code": stock_code,
        "source": "eastmoney",
        "modules": {
            category: fetch_notice_list(stock_code, category, page_size, 1, 0, timeout)
            for category in categories
        },
    }
