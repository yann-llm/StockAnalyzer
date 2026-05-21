"""Fetch Eastmoney industry report list data."""

from __future__ import annotations

from datetime import date
from typing import Any

from eastmoney_http import eastmoney_requests_get
from .industry_common import DEFAULT_HEADERS, DEFAULT_TIMEOUT, EastmoneyIndustryCapitalFlowError, normalize_industry_code


REPORT_LIST_URL = "https://reportapi.eastmoney.com/report/list"


def _date_years_ago(years: int) -> str:
    today = date.today()
    try:
        return today.replace(year=today.year - years).isoformat()
    except ValueError:
        return today.replace(year=today.year - years, day=28).isoformat()


def fetch_industry_reports(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch the industry report list used by the Eastmoney industry report page."""
    codes = normalize_industry_code(industry_code)
    params = {
        "industryCode": codes["numeric_code"],
        "pageSize": "50",
        "industry": "*",
        "rating": "*",
        "ratingchange": "*",
        "beginTime": _date_years_ago(2),
        "endTime": date.today().isoformat(),
        "pageNo": "1",
        "fields": "",
        "qType": "1",
    }
    try:
        response = eastmoney_requests_get(
            REPORT_LIST_URL,
            params=params,
            headers={
                **DEFAULT_HEADERS,
                "Referer": f"https://data.eastmoney.com/report/industry.jshtml?hyid={codes['numeric_code']}",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyIndustryCapitalFlowError(f"failed to fetch industry reports: {exc}") from exc

    rows = [
        row
        for row in data.get("data", [])
        if isinstance(row, dict) and str(row.get("industryCode") or "") == codes["numeric_code"]
    ]
    return {
        "module": "reports",
        "codes": codes,
        "page": {
            "hits": data.get("hits"),
            "size": data.get("size"),
            "total_page": data.get("TotalPage"),
            "page_no": data.get("pageNo"),
            "current_year": data.get("currentYear"),
            "gettime": data.get("gettime"),
        },
        "raw": data,
        "parsed": {"rows": rows},
    }
