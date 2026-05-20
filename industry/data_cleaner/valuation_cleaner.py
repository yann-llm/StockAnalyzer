"""Clean industry valuation module."""

from __future__ import annotations

from typing import Any

from .cleaning_common import date_only, number, round_number


INDUSTRY_VALUATION_EXPLANATIONS = {
    "pe_ttm": "行业滚动市盈率：行业总市值相对最近四个季度利润的倍数，越高代表市场对行业利润的定价越贵。",
    "pe_lar": "行业静态市盈率：行业总市值相对最近年度利润的倍数，适合利润较稳定的行业参考。",
    "pb_mrq": "行业市净率：行业总市值相对最近一期净资产的倍数，重资产行业常用。",
    "peg_car": "行业 PEG：市盈率相对盈利增速的倍数，越高说明估值越依赖后续增长兑现。",
    "pcf_ocf_ttm": "行业滚动经营现金流市现率：行业总市值相对最近四个季度经营现金流的倍数，用来观察现金流支撑。",
    "pcf_ocf_lar": "行业年度经营现金流市现率：行业总市值相对最近年度经营现金流的倍数。",
    "ps_ttm": "行业滚动市销率：行业总市值相对最近四个季度收入的倍数，适合利润波动较大的行业辅助参考。",
    "negative_pe_count": "负 PE 样本数：行业内滚动市盈率为负的公司数量，通常意味着亏损或利润异常，数量越多行业盈利质量越需谨慎。",
}


def compact_valuation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "industry_name": row.get("BOARD_NAME"),
        "valuation_board_code": row.get("BOARD_CODE"),
        "orig_board_code": row.get("ORIG_BOARD_CODE"),
        "trade_date": date_only(row.get("TRADE_DATE")),
        "industry_type": row.get("INDUSTRY_TYPE"),
        "security_code": row.get("SECURITY_CODE"),
        "security_name": row.get("SECURITY_NAME_ABBR"),
        "close_price": round_number(row.get("CLOSE_PRICE")),
        "change_rate": round_number(row.get("CHANGE_RATE")),
        "pe_ttm": round_number(row.get("PE_TTM")),
        "pe_lar": round_number(row.get("PE_LAR")),
        "pb_mrq": round_number(row.get("PB_MRQ")),
        "peg_car": round_number(row.get("PEG_CAR")),
        "pcf_ocf_ttm": round_number(row.get("PCF_OCF_TTM")),
        "pcf_ocf_lar": round_number(row.get("PCF_OCF_LAR")),
        "ps_ttm": round_number(row.get("PS_TTM")),
        "total_market_cap": round_number(row.get("TOTAL_MARKET_CAP"), 2),
        "market_cap_avg": round_number(row.get("MARKET_CAP_VAG"), 2),
        "free_float_market_cap": round_number(row.get("NOTLIMITED_MARKETCAP_A"), 2),
        "free_shares_a": round_number(row.get("FREE_SHARES_A"), 2),
        "total_shares": round_number(row.get("TOTAL_SHARES"), 2),
        "secucode": row.get("SECUCODE"),
        "trade_market": row.get("TRADE_MARKET"),
    }


def compact_valuation(module: dict[str, Any], rank_limit: int) -> dict[str, Any]:
    parsed = module.get("parsed", {})
    stats = [compact_valuation_row(row) for row in parsed.get("stats", [])]
    rank_rows = [compact_valuation_row(row) for row in parsed.get("rank", [])[:rank_limit]]
    negative_pe_count = sum(1 for row in parsed.get("rank", []) if (number(row.get("PE_TTM")) or 0) < 0)
    return {
        "missing_reason": module.get("missing_reason"),
        "metric_explanations": INDUSTRY_VALUATION_EXPLANATIONS,
        "stats": stats,
        "rank_sample": rank_rows,
        "rank_count": len(parsed.get("rank", [])),
        "negative_pe_count": negative_pe_count,
    }
