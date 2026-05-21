"""Shared helpers for Eastmoney industry modules."""

from __future__ import annotations

import json
import time
from typing import Any

import requests
from playwright.sync_api import sync_playwright

from eastmoney_http import eastmoney_requests_get


PUSH2_ULIST_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
PUSH2_CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
PUSH2_STOCK_URL = "https://push2.eastmoney.com/api/qt/stock/get"
PUSH2_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_PAGE_URL = "https://data.eastmoney.com/report/industry.jshtml"

PUSH2_UT = "8dec03ba335b81bf4ebdf7b29ec27d15"
STOCK_UT = "b2884a393a59ad64002292a3e90d46a5"
DEFAULT_TIMEOUT = 15

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

class EastmoneyIndustryCapitalFlowError(RuntimeError):
    """Raised when Eastmoney industry data cannot be fetched."""


def normalize_industry_code(industry_code: str | int) -> dict[str, str]:
    """Normalize Eastmoney industry code forms used by different pages."""
    raw = str(industry_code).strip().upper()
    if not raw:
        raise ValueError("industry_code is required")

    digits = raw[2:] if raw.startswith("BK") else raw
    if not digits.isdigit():
        raise ValueError(f"invalid industry_code: {industry_code!r}")

    numeric_code = str(int(digits))
    bk_code = f"BK{int(digits):04d}"
    return {
        "input_code": raw,
        "numeric_code": numeric_code,
        "bk_code": bk_code,
        "secid": f"90.{bk_code}",
    }


def request_json(url: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    """Request JSON with small retry protection for Eastmoney's flaky endpoints."""
    if "push2" in url:
        raise EastmoneyIndustryCapitalFlowError("push quote data must be fetched from the page context")

    clean_params = {key: value for key, value in params.items() if value is not None}
    headers = {
        **DEFAULT_HEADERS,
        "Referer": "https://data.eastmoney.com/",
    }
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = eastmoney_requests_get(url, params=clean_params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - expose a compact domain error.
            last_exc = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise EastmoneyIndustryCapitalFlowError(f"failed to fetch {url}: {last_exc}") from last_exc


def first_diff(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") or {}
    diff = data.get("diff") or []
    if not diff:
        return {}
    row = diff[0]
    return row if isinstance(row, dict) else {}


def data_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result") or {}
    rows = result.get("data") or []
    return rows if isinstance(rows, list) else []


def date_only(value: Any) -> str:
    if not value:
        return ""
    return str(value).split(" ")[0]


def with_raw(parsed: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {"raw": row, "parsed": parsed}


def quote_page_url(secid: str) -> str:
    return f"https://quote.eastmoney.com/bk/{secid}.html?jump_to_web=true"


def request_push_json_from_page(secid: str, url: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    """Open the Eastmoney board page and fetch push data from that browser page context."""
    clean_params = {key: value for key, value in params.items() if value is not None}
    page_timeout = timeout * 1000
    page_url = quote_page_url(secid)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"])
            page.goto(page_url, wait_until="commit", timeout=page_timeout)
            page.wait_for_timeout(1000)
            payload = page.evaluate(
                """async ({ url, params }) => {
                    const target = new URL(url);
                    target.search = new URLSearchParams(params).toString();
                    let lastError = null;
                    for (let attempt = 0; attempt < 3; attempt += 1) {
                        try {
                            const response = await fetch(target.toString(), {
                                credentials: 'include',
                                cache: 'no-store',
                            });
                            if (!response.ok) {
                                throw new Error(`HTTP ${response.status}`);
                            }
                            return await response.json();
                        } catch (error) {
                            lastError = error;
                            await new Promise((resolve) => setTimeout(resolve, 800 * (attempt + 1)));
                        }
                    }
                    throw lastError;
                }""",
                {"url": url, "params": clean_params},
            )
            browser.close()
            return payload
    except Exception as exc:  # noqa: BLE001 - browser errors should surface as domain errors.
        raise EastmoneyIndustryCapitalFlowError(f"failed to fetch page-context push data from {page_url}: {exc}") from exc


def fetch_ulist(secid: str, fields: str, timeout: int) -> dict[str, Any]:
    params = {
        "fltt": "2",
        "invt": "2",
        "ut": PUSH2_UT,
        "secids": secid,
        "fields": fields,
    }
    payload = request_push_json_from_page(secid, PUSH2_ULIST_URL, params, timeout)
    return first_diff(payload)


def fetch_clist_row(secid: str, fields: str, timeout: int) -> dict[str, Any]:
    """Fallback for board quote rows when ulist closes the connection."""
    bk_code = secid.split(".", 1)[-1].upper()
    payload = request_push_json_from_page(
        secid,
        PUSH2_CLIST_URL,
        {
            "pn": "1",
            "pz": "500",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": PUSH2_UT,
            "fs": "m:90 t:2",
            "fid": "f3",
            "fields": fields,
        },
        timeout,
    )
    for row in (payload.get("data") or {}).get("diff") or []:
        if isinstance(row, dict) and str(row.get("f12") or "").upper() == bk_code:
            return row
    return {}


def datacenter_get(params: dict[str, Any], timeout: int) -> dict[str, Any]:
    return request_json(DATACENTER_URL, params, timeout)
