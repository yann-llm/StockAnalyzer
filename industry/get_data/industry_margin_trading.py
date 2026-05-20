"""Fetch Eastmoney industry margin-trading data."""

from __future__ import annotations

from typing import Any

from .industry_common import DEFAULT_TIMEOUT, data_rows, datacenter_get, normalize_industry_code


def fetch_industry_margin_trading(industry_code: str | int, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch today, 3-day, 5-day, and 10-day margin-trading rows for one industry."""
    codes = normalize_industry_code(industry_code)
    today_payload = datacenter_get(
        {
            "reportName": "RPTA_WEB_BKJYMXN",
            "columns": "ALL",
            "pageNumber": "1",
            "pageNo": "1",
            "pageSize": "5",
            "sortColumns": "FIN_BALANCE",
            "sortTypes": "-1",
            "stat": "1",
            "filter": f'(BOARD_TYPE_CODE="005")(BOARD_CODE="{codes["numeric_code"]}")',
            "source": "WEB",
            "client": "WEB",
        },
        timeout,
    )
    periods = {"today": data_rows(today_payload)}
    for days in (3, 5, 10):
        payload = datacenter_get(
            {
                "reportName": "RPTA_WEB_BKQJYMXN",
                "columns": "ALL",
                "pageNumber": "1",
                "pageNo": "1",
                "pageSize": "5",
                "sortColumns": "FIN_NETBUY_AMT",
                "sortTypes": "-1",
                "stat": str(days),
                "filter": f'(BOARD_TYPE_CODE="005")(BOARD_CODE="{codes["numeric_code"]}")(INTERVAL_TYPE="{days}日")',
                "source": "WEB",
                "client": "WEB",
            },
            timeout,
        )
        periods[f"{days}d"] = data_rows(payload)

    return {"module": "margin_trading", "codes": codes, "raw": periods, "parsed": {"periods": periods}}
