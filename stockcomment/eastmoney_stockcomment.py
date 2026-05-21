"""按千股千评 review 文档抓取东方财富接口数据。"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request

from eastmoney_http import eastmoney_urlopen


DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
NEWS_URL = "https://np-listapi.eastmoney.com/comm/web/getListInfo"
ANN_LIST_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
REPORT_LIST_URL = "https://reportapi.eastmoney.com/report/list"
DEFAULT_TIMEOUT = 15


REPORT_CONFIGS: dict[str, dict[str, Any]] = {
    "custom_stock_pk": {
        "module": "综合评价",
        "report_name": "RPT_CUSTOM_STOCK_PK",
        "filter_field": "SECUCODE",
        "sort_field": "DIAGNOSE_TIME",
        "sort_type": "-1",
        "fields": [
            "SECUCODE",
            "DIAGNOSE_TIME",
            "TOTAL_SCORE",
            "TOTAL_SCORE_CHANGE",
            "STOCK_RANK_RATIO",
            "RISE_1_PROBABILITY",
            "WORDS_EXPLAIN",
        ],
    },
    "history_mark": {
        "module": "综合评价",
        "report_name": "RPT_STOCK_HISTORYMARK",
        "filter_field": "SECURITY_CODE",
        "sort_field": "DIAGNOSE_DATE",
        "sort_type": "-1",
        "fields": ["DIAGNOSE_DATE", "CLOSE", "TOTAL_SCORE"],
    },
    "pk_rank": {
        "module": "综合评价",
        "report_name": "RPT_STOCK_PK_RANK",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "SECURITY_CODE",
            "SECURITY_NAME_ABBR",
            "TRADE_DATE",
            "COMPRE_SCORE",
            "MARKET_RANK",
            "EVALUATE_MARKET_NUM",
            "MARKET_STOCK_NUM",
            "MARKET_SCORE_HIGH",
            "MARKET_SCORE_LOW",
            "MARKET_SCORE_AVG",
            "STOCK_RANK_RATIO",
            "BOARD_CODE",
            "BOARD_NAME",
            "INDUSTRY_RANK",
            "EVALUATE_INDUSTRY_NUM",
            "INDUSTRY_STOCK_NUM",
            "INDUSTRY_SCORE_HIGH",
            "INDUSTRY_SCORE_LOW",
            "INDUSTRY_SCORE_AVG",
            "CHANGE_RATE",
        ],
    },
    "stock_evaluate": {
        "module": "主力控盘",
        "report_name": "RPT_DMSK_TS_STOCKEVALUATE",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "TRADE_DATE",
            "SECURITY_CODE",
            "SECURITY_NAME_ABBR",
            "CLOSE_PRICE",
            "CHANGE_RATE",
            "TURNOVERRATE",
            "SUPERDEAL_INFLOW",
            "SUPERDEAL_OUTFLOW",
            "BIGDEAL_INFLOW",
            "BIGDEAL_OUTFLOW",
            "PRIME_INFLOW",
            "PRIME_COST",
            "PRIME_COST_20DAYS",
            "PRIME_COST_60DAYS",
            "ORG_PARTICIPATE",
            "PARTICIPATE_TYPE",
            "PARTICIPATE_TYPE_CN",
            "BUY_SUPERDEAL_RATIO",
            "BUY_BIGDEAL_RATIO",
            "RATIO",
            "RATIO_3DAYS",
            "RATIO_50DAYS",
            "PE_DYNAMIC",
        ],
    },
    "market_focus": {
        "module": "市场热度",
        "report_name": "RPT_STOCK_MARKETFOCUS",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "TRADE_DATE",
            "SECURITY_CODE",
            "SECURITY_NAME_ABBR",
            "MARKET_FOCUS",
            "MARKET_FOCUS_RANK",
            "TOTAL_MARKET",
            "MARKET_FOCUS_CHANGE",
            "CLOSE_PRICE",
        ],
    },
    "participation": {
        "module": "市场热度",
        "report_name": "RPT_STOCK_PARTICIPATION",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "TRADE_DATE",
            "PARTICIPATION_WISH",
            "PARTICIPATION_WISH_5DAYS",
            "PARTICIPATION_WISH_CHANGE",
            "PARTICIPATION_WISH_5DAYSCHANGE",
        ],
    },
    "trend_comment": {
        "module": "趋势研判",
        "report_name": "RPT_STOCK_TRENDVOLUME_COMMENT",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": ["TRADE_DATE", "COMMENT_TXT"],
    },
    "trend_volume": {
        "module": "趋势研判",
        "report_name": "RPT_STOCK_TRENDVOLUME_PK",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "PRICE_AVG_RELATION",
            "VOLUME_JUDGE",
            "PAR_FOCUS",
            "SUPPORT_LEVEL",
            "PRESSURE_LEVEL",
            "AVG_PRICE",
            "DEAL_AMOUNT",
            "AVG_AMOUNT_5DAYS",
            "WORDS_EXPLAIN",
        ],
    },
    "macd": {
        "module": "趋势研判",
        "report_name": "PRT_STOCK_MACD_PK",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADEDATE",
        "sort_type": "-1",
        "fields": [
            "TRADEDATE",
            "NEW",
            "OPEN",
            "HIGH",
            "LOW",
            "PCTCHANGE_STOCK",
            "SWING",
            "PCTCHANGE_INDEX",
            "AVGTURN",
            "DIF",
            "DEA",
            "MACD",
            "K",
            "D",
            "J",
            "RSI1",
            "RSI2",
            "RSI3",
            "MID",
            "UPPER",
            "LOWER",
            "MACDCOUT",
            "MACDCLOR",
            "KDJOUT",
            "KDJCLOR",
            "RSIOUT",
            "RSICLOR",
            "BOLLOUT",
            "BOLLCLOR",
            "BIASOUT",
            "BIASCLOR",
            "WROUT",
            "WRCLOR",
        ],
    },
    "capital_flows": {
        "module": "资金动向",
        "report_name": "PRT_STOCK_CAPITALFLOWS",
        "filter_field": "SECUCODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "SECUCODE",
            "TRADE_DATE",
            "CAPITAL_FLOWS",
            "CAPITAL_FLOWS_5DAYS",
            "CAPITAL_FLOWS_RATIO",
            "CAPITAL_FLOWS_5DAYSRATIO",
            "BOARD_CODE",
            "BOARD_NAME",
            "BOARD_CAPITAL_FLOWS",
            "BOARD_CAPITAL_5FLOWS",
        ],
    },
    "margin_trend": {
        "module": "资金动向",
        "report_name": "RPT_STOCK_MARGINTREND",
        "filter_field": "SECURITY_CODE",
        "sort_field": "TRADE_DATE",
        "sort_type": "-1",
        "fields": [
            "TRADE_DATE",
            "FIN_BALANCE_DIFF",
            "FREE_RATIO",
            "AVG_FREE_RATIO",
            "FINBALANCE_DIFF_CHANGE",
            "FIN_BALANCE",
            "LOAN_BALANCE",
            "EXPLAIN",
        ],
    },
    "financial_analysis": {
        "module": "财务评估",
        "report_name": "RPT_F10_FINANALYSIS",
        "filter_field": "SECUCODE",
        "sort_field": "REPORT_DATE",
        "sort_type": "-1",
        "fields": [
            "SECUCODE",
            "REPORT_DATE",
            "GROUP_DATE",
            "DATE_TYPE",
            "WEIGHT_ROE",
            "CORE_RPOFIT",
            "TOTAL_PROFIT",
            "CORE_RPOFIT_RATIO",
            "GROSS_RPOFIT_RATIO",
            "SALE_NPR",
            "DEBT_ASSET_RATIO",
            "CURRENT_RATIO",
            "INVENTORY_TR",
            "ACCOUNTS_RECE_TR",
            "TOTAL_ASSETS_TR",
            "CURRENT_TOTAL_ASSETS_TR",
            "WEIGHT_ROE_RANK",
            "NETPROFIT_YOY_RATIO_RANK",
            "TOTAL_ASSETS_TR_RANK",
            "SALE_CASH_RATIO_RANK",
            "DEBT_ASSET_RATIO_RANK",
            "SALE_CASH_RATIO",
            "SX_RATIO",
            "JX_RATIO",
            "NETCASH_OPERATE",
            "NETCASH_INVEST",
            "NETCASH_FINANCE",
            "NETPROFIT_YOY_RATIO",
            "TOTAL_OPERATE_INCOME_RATIO",
            "TOTAL_ASSETS_RATIO",
        ],
    },
    "company_type": {
        "module": "财务评估",
        "report_name": "RPT_F10_PUBLIC_COMPANYTPYE",
        "filter_field": "SECUCODE",
        "sort_field": None,
        "sort_type": "1",
        "fields": ["COMPANY_TYPE"],
    },
}

STOCKBOARD_RANK_FIELDS = [
    "BOARD_CODE",
    "BOARD_NAME",
    "SECUCODE",
    "SECURITY_NAME_ABBR",
    "CAPITAL_FLOWS",
    "CAPITAL_FLOWS_RANK",
]


class EastmoneyStockcommentError(RuntimeError):
    """千股千评数据抓取失败。"""


def _secucode(stock_code: str) -> str:
    market = "SH" if stock_code.startswith("6") else "SZ"
    return f"{stock_code}.{market}"


def _hq_code(stock_code: str) -> str:
    market_prefix = "1" if stock_code.startswith("6") else "0"
    return f"{market_prefix}.{stock_code}"


def _read_json(url: str, timeout: int) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"})
    with eastmoney_urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _pick_fields(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _datacenter_rows(
    report_name: str,
    filter_text: str,
    page_size: int,
    timeout: int,
    sort_field: str | None = None,
    sort_type: str = "-1",
) -> list[dict[str, Any]]:
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": filter_text,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "source": "WEB",
        "client": "WEB",
    }
    if sort_field:
        params["sortColumns"] = sort_field
        params["sortTypes"] = sort_type

    try:
        payload = _read_json(f"{DATACENTER_URL}?{urlencode(params)}", timeout)
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyStockcommentError(f"failed to fetch {report_name}: {exc}") from exc

    result = payload.get("result") or {}
    rows = result.get("data") or []
    if not isinstance(rows, list):
        raise EastmoneyStockcommentError(f"unexpected response shape for {report_name}")
    return rows


def fetch_stockcomment_report(
    stock_code: str,
    config_key: str,
    page_size: int = 1,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """按 review.md 中配置的 reportName 和字段抓取单个模块。"""
    config = REPORT_CONFIGS[config_key]
    filter_value = _secucode(stock_code) if config["filter_field"] == "SECUCODE" else stock_code
    rows = _datacenter_rows(
        config["report_name"],
        f'({config["filter_field"]}="{filter_value}")',
        page_size,
        timeout,
        config.get("sort_field"),
        config.get("sort_type", "-1"),
    )
    fields = config["fields"]
    return {
        "module": config["module"],
        "report_name": config["report_name"],
        "fields": fields,
        "rows": [_pick_fields(row, fields) for row in rows],
        "raw_rows": rows,
    }


def fetch_stockcomment_news(
    stock_code: str,
    page_size: int = 20,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """抓取舆情监控中的新闻列表，对应页面脚本 loadNews。"""
    params = {
        "client": "web",
        "biz": "web_voice",
        "mTypeAndCode": _hq_code(stock_code),
        "pageSize": str(page_size),
        "type": "1",
        "req_trace": stock_code,
    }
    try:
        payload = _read_json(f"{NEWS_URL}?{urlencode(params)}", timeout)
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyStockcommentError(f"failed to fetch stockcomment news: {exc}") from exc

    rows = (payload.get("data") or {}).get("list") or []
    fields = ["Art_Title", "Art_ShowTime", "Art_Code", "Art_Url"]
    return {
        "module": "舆情监控",
        "report_name": "np-listapi.eastmoney.com/comm/web/getListInfo",
        "fields": fields,
        "rows": [_pick_fields(row, fields) for row in rows],
        "raw_rows": rows,
    }


def fetch_stockcomment_announcements(
    stock_code: str,
    page_size: int = 20,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """抓取舆情监控中的公告列表，对应页面脚本 loadNotices。"""
    params = {
        "sr": "-1",
        "page_size": str(page_size),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": stock_code,
        "f_node": "0",
        "s_node": "0",
    }
    try:
        payload = _read_json(f"{ANN_LIST_URL}?{urlencode(params)}", timeout)
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyStockcommentError(f"failed to fetch stockcomment announcements: {exc}") from exc

    rows = (payload.get("data") or {}).get("list") or []
    fields = ["title", "notice_date", "art_code"]
    return {
        "module": "舆情监控",
        "report_name": "np-anotice-stock.eastmoney.com/api/security/ann",
        "fields": fields,
        "rows": [_pick_fields(row, fields) for row in rows],
        "raw_rows": rows,
    }


def fetch_stockcomment_reports(
    stock_code: str,
    page_size: int = 25,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """抓取舆情监控中的研报列表，对应页面脚本 loadReports。"""
    today = date.today()
    params = {
        "pageNo": "1",
        "pageSize": str(page_size),
        "code": stock_code,
        "industryCode": "*",
        "industry": "*",
        "rating": "*",
        "ratingchange": "*",
        "beginTime": f"{today.year}-01-01",
        "endTime": today.isoformat(),
        "fields": "",
        "qType": "0",
        "sort": "publishDate,desc",
    }
    try:
        payload = _read_json(f"{REPORT_LIST_URL}?{urlencode(params)}", timeout)
    except Exception as exc:  # noqa: BLE001
        raise EastmoneyStockcommentError(f"failed to fetch stockcomment reports: {exc}") from exc

    rows = payload.get("data") or []
    fields = ["title", "publishDate", "infoCode", "orgSName", "emRatingName"]
    return {
        "module": "舆情监控",
        "report_name": "reportapi.eastmoney.com/report/list",
        "fields": fields,
        "rows": [_pick_fields(row, fields) for row in rows],
        "raw_rows": rows,
    }


def fetch_stockboard_rank(
    stock_code: str,
    board_code: str,
    page_size: int = 3,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """抓取资金动向中的行业内个股主力流入排行，并补充当前股票排名。"""
    top_rows = _datacenter_rows(
        "RPT_STOCKBOARD_RANK",
        f'(BOARD_CODE="{board_code}")',
        page_size,
        timeout,
        "CAPITAL_FLOWS_RANK",
        "1",
    )
    current_rows = _datacenter_rows(
        "RPT_STOCKBOARD_RANK",
        f'(SECUCODE="{_secucode(stock_code)}")',
        1,
        timeout,
        None,
        "1",
    )
    seen = {row.get("SECUCODE") for row in top_rows}
    rows = list(top_rows)
    if current_rows and current_rows[0].get("SECUCODE") not in seen:
        rows.append(current_rows[0])
    return {
        "module": "资金动向",
        "report_name": "RPT_STOCKBOARD_RANK",
        "fields": STOCKBOARD_RANK_FIELDS,
        "rows": [_pick_fields(row, STOCKBOARD_RANK_FIELDS) for row in rows],
        "raw_rows": rows,
    }


def fetch_stockcomment_data(
    stock_code: str,
    page_size: int = 1,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """抓取千股千评 7 大板块所需的接口数据。"""
    modules = {key: fetch_stockcomment_report(stock_code, key, page_size, timeout) for key in REPORT_CONFIGS}

    capital_row = (modules.get("capital_flows", {}).get("rows") or [{}])[0]
    board_code = capital_row.get("BOARD_CODE")
    if board_code:
        modules["stockboard_rank"] = fetch_stockboard_rank(stock_code, str(board_code), 3, timeout)

    modules["news"] = fetch_stockcomment_news(stock_code, 20, timeout)
    modules["announcements"] = fetch_stockcomment_announcements(stock_code, 20, timeout)
    modules["reports"] = fetch_stockcomment_reports(stock_code, 25, timeout)

    return {
        "stock_code": stock_code,
        "source": "eastmoney",
        "modules": modules,
        "unsupported_by_review": {
            "prediction": "review.md 标注页面涨跌预测模块未暴露独立接口字段名，仅保留说明，不伪造字段。",
        },
    }
