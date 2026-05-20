"""Clean Eastmoney valuation data."""

from __future__ import annotations

from typing import Any


VALUATION_FIELDS = [
    "TRADE_DATE",
    "SECURITY_CODE",
    "SECURITY_NAME_ABBR",
    "BOARD_CODE",
    "BOARD_NAME",
    "CLOSE_PRICE",
    "CHANGE_RATE",
    "PE_TTM",
    "PE_LAR",
    "PB_MRQ",
    "PEG_CAR",
    "PCF_OCF_LAR",
    "PCF_OCF_TTM",
    "PS_TTM",
    "TOTAL_MARKET_CAP",
    "NOTLIMITED_MARKETCAP_A",
    "TOTAL_SHARES",
    "FREE_SHARES_A",
]


def _number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def _date(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return value


VALUATION_METRIC_EXPLANATIONS = {
    "pe_ttm": {
        "name_cn": "滚动市盈率",
        "formula_cn": "总市值 / 最近四个季度净利润",
        "meaning": "衡量投资者为公司当前每 1 元利润愿意支付多少价格。",
        "how_to_read": "越低通常越便宜，但周期低点或利润异常时会失真；亏损公司该指标可能为负，参考意义较弱。",
    },
    "pe_lar": {
        "name_cn": "静态市盈率",
        "formula_cn": "总市值 / 最近年度净利润",
        "meaning": "用上一完整年度利润衡量估值水平。",
        "how_to_read": "适合利润稳定公司；利润高速变化时，参考价值弱于滚动市盈率。",
    },
    "pb_mrq": {
        "name_cn": "市净率",
        "formula_cn": "总市值 / 最近一期归母净资产",
        "meaning": "衡量市场价格相当于账面净资产的多少倍。",
        "how_to_read": "重资产行业常用。越高说明市场给资产更高溢价，也可能意味着估值压力更高。",
    },
    "peg": {
        "name_cn": "市盈增长比率",
        "formula_cn": "市盈率 / 盈利增速",
        "meaning": "把估值和成长速度放在一起看，判断高估值是否被高增长支撑。",
        "how_to_read": "通常小于 1 偏便宜，接近 1 较均衡，大于 1 说明需要较强增长兑现来消化估值。",
    },
    "pcf_ocf_lar": {
        "name_cn": "年度经营现金流市现率",
        "formula_cn": "总市值 / 最近年度经营现金流",
        "meaning": "衡量公司经营现金流对当前市值的支撑力度。",
        "how_to_read": "越低通常现金流支撑越强；如果明显高于 PE，需要关注利润是否充分转化为现金。",
    },
    "pcf_ocf_ttm": {
        "name_cn": "滚动经营现金流市现率",
        "formula_cn": "总市值 / 最近四个季度经营现金流",
        "meaning": "用最近四个季度经营现金流衡量估值。",
        "how_to_read": "适合观察现金回款质量。数值偏高时，说明现金流相对市值偏弱。",
    },
    "ps_ttm": {
        "name_cn": "滚动市销率",
        "formula_cn": "总市值 / 最近四个季度营业收入",
        "meaning": "衡量每 1 元收入对应多少市场估值。",
        "how_to_read": "利润波动或暂时低利润公司可参考；但收入质量、毛利率和现金流仍要一起看。",
    },
}


def _valuation_reading(latest: dict[str, Any], percentiles: dict[str, Any]) -> dict[str, Any]:
    pe = _number(latest.get("pe_ttm"))
    pb = _number(latest.get("pb_mrq"))
    peg = _number(latest.get("peg"))
    pcf = _number(latest.get("pcf_ocf_ttm"))

    notes = []
    if pe is not None:
        notes.append(f"滚动市盈率为 {pe} 倍，表示市场按最近四个季度利润给出约 {pe} 倍定价。")
    if peg is not None:
        if peg > 1:
            notes.append(f"PEG 为 {peg}，高于 1，说明估值需要后续盈利增长继续兑现来支撑。")
        else:
            notes.append(f"PEG 为 {peg}，不高于 1，估值与成长性的匹配度相对更好。")
    if pcf is not None:
        notes.append(f"滚动经营现金流市现率为 {pcf} 倍，可用来观察利润是否真正转化为现金流。")
    if pb is not None:
        notes.append(f"市净率为 {pb} 倍，反映市场给予公司净资产的溢价水平。")

    percentile_notes = []
    for key, label in (
        ("pe_ttm", "滚动市盈率"),
        ("pb_mrq", "市净率"),
        ("peg", "PEG"),
        ("pcf_ocf_ttm", "滚动经营现金流市现率"),
        ("ps_ttm", "滚动市销率"),
    ):
        item = percentiles.get(key)
        if item:
            percentile_notes.append(
                f"{label}在同行中从低到高位于约 {item['percentile']}% 分位，分位越高代表相对同行越贵。"
            )

    return {
        "summary": "估值指标需要和盈利增速、现金流质量、行业位置一起看，不能只看单个倍数高低。",
        "latest_notes": notes,
        "industry_percentile_notes": percentile_notes,
    }


def _compact_detail(row: dict[str, Any]) -> dict[str, Any]:
    """保留估值分析需要的核心字段。"""
    return {
        "trade_date": _date(row.get("TRADE_DATE")),
        "stock_code": row.get("SECURITY_CODE"),
        "stock_name": row.get("SECURITY_NAME_ABBR"),
        "board_code": row.get("BOARD_CODE"),
        "board_name": row.get("BOARD_NAME"),
        "close_price": _round(row.get("CLOSE_PRICE")),
        "change_rate": _round(row.get("CHANGE_RATE")),
        "pe_ttm": _round(row.get("PE_TTM")),
        "pe_lar": _round(row.get("PE_LAR")),
        "pb_mrq": _round(row.get("PB_MRQ")),
        "peg": _round(row.get("PEG_CAR")),
        "pcf_ocf_lar": _round(row.get("PCF_OCF_LAR")),
        "pcf_ocf_ttm": _round(row.get("PCF_OCF_TTM")),
        "ps_ttm": _round(row.get("PS_TTM")),
        "total_market_cap": _round(row.get("TOTAL_MARKET_CAP"), 2),
        "float_market_cap": _round(row.get("NOTLIMITED_MARKETCAP_A"), 2),
        "total_shares": _round(row.get("TOTAL_SHARES"), 2),
        "float_shares": _round(row.get("FREE_SHARES_A"), 2),
    }


def _latest_date(rows: list[dict[str, Any]]) -> Any:
    """取数据中的最新交易日。"""
    dates = [_date(row.get("TRADE_DATE")) for row in rows if row.get("TRADE_DATE")]
    return max(dates) if dates else None


def _filter_by_trade_date(rows: list[dict[str, Any]], trade_date: Any) -> list[dict[str, Any]]:
    if not trade_date:
        return rows
    return [row for row in rows if _date(row.get("TRADE_DATE")) == trade_date]


def _rank_stock(industry_rows: list[dict[str, Any]], stock_code: str) -> dict[str, Any] | None:
    """按 PE_TTM 从低到高计算行业排名，和页面默认排名逻辑保持一致。"""
    valid_rows = [row for row in industry_rows if _number(row.get("PE_TTM")) not in (None, 0)]
    sorted_rows = sorted(valid_rows, key=lambda row: _number(row.get("PE_TTM")) or float("inf"))
    for index, row in enumerate(sorted_rows, start=1):
        if row.get("SECURITY_CODE") == stock_code:
            compact = _compact_detail(row)
            compact["rank_by_pe_ttm"] = index
            compact["industry_count"] = len(sorted_rows)
            compact["industry_trade_date"] = compact.get("trade_date")
            return compact
    return None


def _percentile_rank(rows: list[dict[str, Any]], stock_code: str, field: str) -> dict[str, Any] | None:
    """计算目标股票在同行中的分位，数值越低分位越低。"""
    target_row = next((row for row in rows if row.get("SECURITY_CODE") == stock_code), None)
    if target_row is None:
        return None

    target_value = _number(target_row.get(field))
    if target_value is None:
        return None

    values = [_number(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return None

    lower_or_equal = sum(1 for value in values if value <= target_value)
    percentile = lower_or_equal / len(values) * 100
    return {
        "value": _round(target_value),
        "percentile": round(percentile, 2),
        "rank_low_to_high": lower_or_equal,
        "industry_count": len(values),
    }


def _industry_percentiles(industry_rows: list[dict[str, Any]], stock_code: str) -> dict[str, Any]:
    """输出估值模型可直接使用的同行分位。"""
    field_map = {
        "pe_ttm": "PE_TTM",
        "pe_lar": "PE_LAR",
        "pb_mrq": "PB_MRQ",
        "peg": "PEG_CAR",
        "pcf_ocf_lar": "PCF_OCF_LAR",
        "pcf_ocf_ttm": "PCF_OCF_TTM",
        "ps_ttm": "PS_TTM",
    }
    return {
        clean_field: percentile
        for clean_field, raw_field in field_map.items()
        if (percentile := _percentile_rank(industry_rows, stock_code, raw_field)) is not None
    }


def _stats_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清洗行业平均/中值行。"""
    return [
        {
            "trade_date": _date(row.get("TRADE_DATE")),
            "industry_type": row.get("INDUSTRY_TYPE"),
            "board_code": row.get("BOARD_CODE"),
            "board_name": row.get("BOARD_NAME"),
            "pe_ttm": _round(row.get("PE_TTM")),
            "pe_lar": _round(row.get("PE_LAR")),
            "pb_mrq": _round(row.get("PB_MRQ")),
            "peg": _round(row.get("PEG_CAR")),
            "pcf_ocf_lar": _round(row.get("PCF_OCF_LAR")),
            "pcf_ocf_ttm": _round(row.get("PCF_OCF_TTM")),
            "ps_ttm": _round(row.get("PS_TTM")),
            # 行业平均行使用 *_VAG 字段；行业中值行使用普通市值/股本字段。
            "market_cap_avg": _round(row.get("MARKET_CAP_VAG"), 2),
            "float_market_cap_avg": _round(row.get("NOMARKETCAP_A_VAG"), 2),
            "total_shares_avg": _round(row.get("TOTAL_SHARES_VAG"), 2),
            "total_market_cap": _round(row.get("TOTAL_MARKET_CAP"), 2),
            "float_market_cap": _round(row.get("NOTLIMITED_MARKETCAP_A"), 2),
            "total_shares": _round(row.get("TOTAL_SHARES"), 2),
        }
        for row in rows
    ]


def clean_valuation_data(valuation_data: dict[str, Any], trend_limit: int = 60) -> dict[str, Any]:
    """清洗估值数据，生成估值分析摘要。

    清洗原则：
    1. 个股估值明细保留最新值和历史趋势。
    2. 行业排名只输出当前股票在行业里的排名，不把全行业列表全量传给模型。
    3. 行业平均/中值保留为对照基准。
    """
    modules = valuation_data.get("modules", {})
    details = modules.get("stock_detail", [])
    industry_rank = modules.get("industry_rank", [])
    industry_stats = modules.get("industry_stats", [])
    stock_code = valuation_data.get("stock_code")

    latest = _compact_detail(details[0]) if details else {}
    trends = [_compact_detail(row) for row in details[:trend_limit]]
    latest_trade_date = latest.get("trade_date") or _latest_date(industry_rank)
    latest_industry_rows = _filter_by_trade_date(industry_rank, latest_trade_date)
    latest_industry_stats = _filter_by_trade_date(industry_stats, latest_trade_date)
    target_rank = _rank_stock(latest_industry_rows, stock_code)
    stats = _stats_rows(latest_industry_stats or industry_stats)
    industry_percentiles = _industry_percentiles(latest_industry_rows, stock_code)

    risk_flags = []
    pe = _number(latest.get("pe_ttm"))
    peg = _number(latest.get("peg"))
    if pe is not None and pe <= 0:
        risk_flags.append({"level": "warning", "title": "滚动市盈率非正", "detail": f"滚动市盈率为 {pe}，通常意味着最近四个季度利润为负或异常，估值可比性较弱。"})
    if peg is not None and peg > 1:
        risk_flags.append({"level": "notice", "title": "估值对增长要求较高", "detail": f"PEG 为 {peg}，高于 1，说明当前估值需要后续盈利增长继续兑现来支撑。"})

    return {
        "stock_code": stock_code,
        "board_code": valuation_data.get("board_code"),
        "source": valuation_data.get("source", "eastmoney"),
        "metric_explanations": VALUATION_METRIC_EXPLANATIONS,
        "valuation_reading": _valuation_reading(latest, industry_percentiles),
        "latest": latest,
        "trends": trends,
        "industry_rank": target_rank,
        "industry_percentiles": industry_percentiles,
        "industry_stats": stats,
        "risk_flags": risk_flags,
    }
