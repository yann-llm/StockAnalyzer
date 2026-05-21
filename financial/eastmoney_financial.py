"""Fetch financial report data from Eastmoney."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request

from eastmoney_http import eastmoney_urlopen


API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
DEFAULT_TIMEOUT = 15


REPORT_CONFIGS = {
    "performance_report": {
        "report_name": "RPT_LICO_FN_CPD",
        "sort_field": "REPORTDATE",
    },
    "balance_sheet": {
        "report_name": "RPT_DMSK_FN_BALANCE",
        "sort_field": "REPORT_DATE",
    },
    "income_statement": {
        "report_name": "RPT_DMSK_FN_INCOME",
        "sort_field": "REPORT_DATE",
    },
    "cash_flow_statement": {
        "report_name": "RPT_DMSK_FN_CASHFLOW",
        "sort_field": "REPORT_DATE",
    },
}


FIELD_MAPS = {
    "performance_report": {
        "REPORTDATE": "报告期",
        "SECURITY_CODE": "证券代码",
        "SECURITY_NAME_ABBR": "证券简称",
        "BASIC_EPS": "基本每股收益",
        "DEDUCT_BASIC_EPS": "扣非每股收益",
        "TOTAL_OPERATE_INCOME": "营业总收入",
        "YSTZ": "营业总收入同比增长(%)",
        "YSHZ": "营业总收入季度环比增长(%)",
        "PARENT_NETPROFIT": "归母净利润",
        "SJLTZ": "归母净利润同比增长(%)",
        "SJLHZ": "归母净利润季度环比增长(%)",
        "BPS": "每股净资产",
        "WEIGHTAVG_ROE": "净资产收益率(%)",
        "MGJYXJJE": "每股经营现金流量",
        "XSMLL": "销售毛利率(%)",
        "ASSIGNDSCRPT": "利润分配",
        "ZXGXL": "股息率",
        "NOTICE_DATE": "公告日期",
        "UPDATE_DATE": "更新日期",
    },
    "balance_sheet": {
        "REPORT_DATE": "报告期",
        "TOTAL_ASSETS": "总资产(元)",
        "TOTAL_ASSETS_RATIO": "总资产同比(%)",
        "FIXED_ASSET": "固定资产(元)",
        "MONETARYFUNDS": "货币资金(元)",
        "MONETARYFUNDS_RATIO": "货币资金同比(%)",
        "ACCOUNTS_RECE": "应收账款(元)",
        "ACCOUNTS_RECE_RATIO": "应收账款同比(%)",
        "INVENTORY": "存货(元)",
        "INVENTORY_RATIO": "存货同比(%)",
        "TOTAL_LIABILITIES": "总负债(元)",
        "TOTAL_LIAB_RATIO": "总负债同比(%)",
        "ACCOUNTS_PAYABLE": "应付账款(元)",
        "ACCOUNTS_PAYABLE_RATIO": "应付账款同比(%)",
        "ADVANCE_RECEIVABLES": "预收账款(元)",
        "ADVANCE_RECEIVABLES_RATIO": "预收账款同比(%)",
        "TOTAL_EQUITY": "股东权益合计(元)",
        "TOTAL_EQUITY_RATIO": "股东权益同比(%)",
        "DEBT_ASSET_RATIO": "资产负债率(%)",
        "NOTICE_DATE": "公告日期",
    },
    "income_statement": {
        "REPORT_DATE": "报告期",
        "PARENT_NETPROFIT": "净利润/归母净利润(元)",
        "PARENT_NETPROFIT_RATIO": "净利润同比(%)",
        "DEDUCT_PARENT_NETPROFIT": "扣非归母净利润(元)",
        "DPN_RATIO": "扣非归母净利润同比(%)",
        "TOTAL_OPERATE_INCOME": "营业总收入(元)",
        "TOI_RATIO": "营业总收入同比(%)",
        "OPERATE_EXPENSE": "营业支出(元)",
        "OPERATE_EXPENSE_RATIO": "营业支出同比(%)",
        "SALE_EXPENSE": "销售费用(元)",
        "MANAGE_EXPENSE": "管理费用(元)",
        "FINANCE_EXPENSE": "财务费用(元)",
        "TOTAL_OPERATE_COST": "营业总支出(元)",
        "TOE_RATIO": "营业总支出同比(%)",
        "OPERATE_PROFIT": "营业利润(元)",
        "OPERATE_PROFIT_RATIO": "营业利润同比(%)",
        "TOTAL_PROFIT": "利润总额(元)",
        "NOTICE_DATE": "公告日期",
    },
    "cash_flow_statement": {
        "REPORT_DATE": "报告期",
        "CCE_ADD": "净现金流(元)",
        "CCE_ADD_RATIO": "净现金流同比(%)",
        "NETCASH_OPERATE": "经营性现金流量净额(元)",
        "NETCASH_OPERATE_RATIO": "经营性现金流量净额占比(%)",
        "SALES_SERVICES": "销售商品、提供劳务收到的现金(元)",
        "SALES_SERVICES_RATIO": "销售商品、提供劳务收到的现金占比(%)",
        "NETCASH_INVEST": "投资性现金流量净额(元)",
        "NETCASH_INVEST_RATIO": "投资性现金流量净额占比(%)",
        "RECEIVE_INVEST_INCOME": "取得投资收益收到的现金(元)",
        "RII_RATIO": "取得投资收益收到的现金占比(%)",
        "CONSTRUCT_LONG_ASSET": "购建固定资产、无形资产和其他长期资产支付的现金(元)",
        "CLA_RATIO": "购建固定资产、无形资产和其他长期资产支付的现金占比(%)",
        "NETCASH_FINANCE": "融资性现金流量净额(元)",
        "NETCASH_FINANCE_RATIO": "融资性现金流量净额占比(%)",
        "NOTICE_DATE": "公告日期",
    },
}


class EastmoneyFinancialError(RuntimeError):
    """Raised when Eastmoney financial data cannot be fetched or parsed."""


def _normalize_date(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return value


def _parse_rows(module_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    field_map = FIELD_MAPS[module_name]
    date_field = "REPORTDATE" if module_name == "performance_report" else "REPORT_DATE"
    parsed_rows = []

    for row in rows:
        raw = {field: row.get(field) for field in field_map}
        parsed = {label: _normalize_date(row.get(field)) for field, label in field_map.items()}
        parsed_rows.append(
            {
                "report_date": _normalize_date(row.get(date_field)),
                "raw": raw,
                "parsed": parsed,
            }
        )
    return parsed_rows


def _request_report(
    stock_code: str,
    module_name: str,
    page_size: int,
    timeout: int,
) -> list[dict[str, Any]]:
    config = REPORT_CONFIGS[module_name]
    params = {
        "sortColumns": config["sort_field"],
        "sortTypes": "-1",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{stock_code}")',
        "reportName": config["report_name"],
        "source": "WEB",
        "client": "WEB",
    }
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with eastmoney_urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - keep caller-facing error simple.
        raise EastmoneyFinancialError(f"failed to fetch {module_name}: {exc}") from exc

    rows = payload.get("result", {}).get("data", [])
    if not isinstance(rows, list):
        raise EastmoneyFinancialError(f"unexpected response shape for {module_name}")
    return _parse_rows(module_name, rows)


def fetch_performance_report(
    stock_code: str,
    page_size: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch Eastmoney performance report rows."""
    return _request_report(stock_code, "performance_report", page_size, timeout)


def fetch_balance_sheet(
    stock_code: str,
    page_size: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch Eastmoney balance sheet rows."""
    return _request_report(stock_code, "balance_sheet", page_size, timeout)


def fetch_income_statement(
    stock_code: str,
    page_size: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch Eastmoney income statement rows."""
    return _request_report(stock_code, "income_statement", page_size, timeout)


def fetch_cash_flow_statement(
    stock_code: str,
    page_size: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch Eastmoney cash flow statement rows."""
    return _request_report(stock_code, "cash_flow_statement", page_size, timeout)


def fetch_financial_reports(
    stock_code: str,
    page_size: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Fetch all four Eastmoney financial report modules."""
    return {
        "stock_code": stock_code,
        "source": "eastmoney",
        "modules": {
            "performance_report": fetch_performance_report(stock_code, page_size, timeout),
            "balance_sheet": fetch_balance_sheet(stock_code, page_size, timeout),
            "income_statement": fetch_income_statement(stock_code, page_size, timeout),
            "cash_flow_statement": fetch_cash_flow_statement(stock_code, page_size, timeout),
        },
    }
