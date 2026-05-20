"""Aggregate cleaners for Eastmoney industry trend data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .capital_flow_cleaner import compact_capital_flow
from .cleaning_common import number
from .index_cleaner import compact_index_kline, compact_index_snapshot
from .margin_trading_cleaner import compact_margin_trading
from .market_cleaner import compact_market
from .report_cleaner import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS, compact_reports
from .valuation_cleaner import compact_valuation


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _score_market(cleaned: dict[str, Any]) -> dict[str, Any]:
    market = cleaned.get("modules", {}).get("market", {})
    change_rate = number(market.get("change_rate")) or 0
    breadth = number(market.get("breadth_up_ratio"))
    main_net = number(market.get("main_net_inflow")) or 0
    score = 50 + change_rate * 3
    if breadth is not None:
        score += (breadth - 0.5) * 50
    score += 8 if main_net > 0 else -8 if main_net < 0 else 0
    return {
        "score": _clamp_score(score),
        "signals": {
            "change_rate": market.get("change_rate"),
            "breadth_up_ratio": market.get("breadth_up_ratio"),
            "main_net_inflow": market.get("main_net_inflow"),
            "top_stock_name": market.get("top_stock_name"),
        },
    }


def _score_index_trend(cleaned: dict[str, Any]) -> dict[str, Any]:
    kline = cleaned.get("modules", {}).get("index_kline", {})
    returns = kline.get("returns", {})
    latest_to_avg = number(kline.get("amount", {}).get("latest_to_5d_avg"))
    r5 = number(returns.get("5d")) or 0
    r10 = number(returns.get("10d")) or 0
    r20 = number(returns.get("20d")) or 0
    score = 50 + r5 * 2 + r10 * 1.2 + r20 * 0.8
    if latest_to_avg is not None:
        score += (latest_to_avg - 1) * 10
    return {
        "score": _clamp_score(score),
        "signals": {
            "latest": kline.get("latest"),
            "returns": returns,
            "latest_to_5d_avg": kline.get("amount", {}).get("latest_to_5d_avg"),
        },
    }


def _score_capital_flow(cleaned: dict[str, Any]) -> dict[str, Any]:
    periods = cleaned.get("modules", {}).get("capital_flow", {}).get("periods", {})
    weights = {"today": 0.45, "5d": 0.35, "10d": 0.2}
    score = 50
    signals = {}
    for period, weight in weights.items():
        row = periods.get(period, {})
        main_ratio = number(row.get("main_net_inflow_ratio"))
        main_net = number(row.get("main_net_inflow")) or 0
        if main_ratio is not None:
            score += main_ratio * weight * 2
        score += (8 if main_net > 0 else -8 if main_net < 0 else 0) * weight
        signals[period] = {
            "main_net_inflow": row.get("main_net_inflow"),
            "main_net_inflow_ratio": row.get("main_net_inflow_ratio"),
            "top_stock_name": row.get("top_stock_name"),
        }
    return {"score": _clamp_score(score), "signals": signals}


def _score_reports(cleaned: dict[str, Any]) -> dict[str, Any]:
    reports = cleaned.get("modules", {}).get("reports", {})
    keywords = reports.get("top_keywords", {})
    positive_hits = sum(keywords.get(word, 0) for word in POSITIVE_KEYWORDS)
    negative_hits = sum(keywords.get(word, 0) for word in NEGATIVE_KEYWORDS)
    unique_org_count = number(reports.get("unique_org_count")) or 0
    score = 50 + (positive_hits - negative_hits) * 5 + min(unique_org_count, 10)
    return {
        "score": _clamp_score(score),
        "signals": {
            "positive_keyword_hits": positive_hits,
            "negative_keyword_hits": negative_hits,
            "unique_org_count": reports.get("unique_org_count"),
            "rating_counts": reports.get("rating_counts"),
            "top_keywords": reports.get("top_keywords"),
        },
    }


def _score_margin(cleaned: dict[str, Any]) -> dict[str, Any]:
    margin = cleaned.get("modules", {}).get("margin_trading", {})
    today = margin.get("today", {})
    netbuy_ratio = number(today.get("fin_netbuy_to_balance")) or 0
    balance_ratio = number(today.get("fin_balance_ratio")) or 0
    score = 50 + netbuy_ratio * 200 + balance_ratio * 2
    return {
        "score": _clamp_score(score),
        "signals": {
            "today_fin_netbuy_amt": today.get("fin_netbuy_amt"),
            "today_fin_netbuy_to_balance": today.get("fin_netbuy_to_balance"),
            "today_fin_balance_ratio": today.get("fin_balance_ratio"),
        },
    }


def _score_valuation(cleaned: dict[str, Any]) -> dict[str, Any]:
    valuation = cleaned.get("modules", {}).get("valuation", {})
    stats = valuation.get("stats", [])
    first = stats[0] if stats else {}
    pe = number(first.get("pe_ttm"))
    pb = number(first.get("pb_mrq"))
    score = 50
    if pe is not None:
        if pe <= 0:
            score -= 15
        elif pe < 15:
            score += 10
        elif pe > 40:
            score -= 10
    if pb is not None:
        if pb < 2:
            score += 8
        elif pb > 5:
            score -= 8
    score -= min(number(valuation.get("negative_pe_count")) or 0, 10)
    return {
        "score": _clamp_score(score),
        "signals": {
            "pe_ttm": first.get("pe_ttm"),
            "pb_mrq": first.get("pb_mrq"),
            "negative_pe_count": valuation.get("negative_pe_count"),
            "rank_count": valuation.get("rank_count"),
        },
    }


def _score_summary(cleaned: dict[str, Any]) -> dict[str, Any]:
    dimensions = {
        "market": _score_market(cleaned),
        "index_trend": _score_index_trend(cleaned),
        "capital_flow": _score_capital_flow(cleaned),
        "reports": _score_reports(cleaned),
        "margin_trading": _score_margin(cleaned),
        "valuation": _score_valuation(cleaned),
    }
    weights = {
        "market": 0.18,
        "index_trend": 0.22,
        "capital_flow": 0.22,
        "reports": 0.16,
        "margin_trading": 0.1,
        "valuation": 0.12,
    }
    total = sum(dimensions[key]["score"] * weight for key, weight in weights.items())
    overall = _clamp_score(total)
    if overall >= 75:
        rating = "strong"
    elif overall >= 60:
        rating = "positive"
    elif overall >= 45:
        rating = "neutral"
    else:
        rating = "weak"
    return {"overall_score": overall, "rating": rating, "weights": weights, "dimensions": dimensions}


def _add_flag(flags: list[dict[str, Any]], level: str, title: str, detail: str) -> None:
    flags.append({"level": level, "title": title, "detail": detail})


def _build_flags(cleaned: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    name = cleaned.get("industry_name") or "目标行业"

    market = cleaned.get("modules", {}).get("market", {})
    if number(market.get("breadth_up_ratio")) is not None and number(market.get("breadth_up_ratio")) < 0.4:
        _add_flag(flags, "warning", "行业广度偏弱", f"{name}上涨占比为 {market.get('breadth_up_ratio')}。")

    flow_periods = cleaned.get("modules", {}).get("capital_flow", {}).get("periods", {})
    negative_periods = [
        period
        for period, row in flow_periods.items()
        if (number(row.get("main_net_inflow")) is not None and number(row.get("main_net_inflow")) < 0)
    ]
    if len(negative_periods) >= 2:
        _add_flag(flags, "warning", "主力资金多周期净流出", f"{name}主力资金在 {', '.join(negative_periods)} 周期为负。")

    margin = cleaned.get("modules", {}).get("margin_trading", {}).get("today", {})
    if (number(margin.get("fin_netbuy_amt")) or 0) > 0:
        _add_flag(flags, "notice", "融资资金净买入", f"{name}今日融资净买入为 {margin.get('fin_netbuy_amt')} 元。")

    valuation = cleaned.get("modules", {}).get("valuation", {})
    if valuation.get("missing_reason"):
        _add_flag(flags, "notice", "估值映射缺失", valuation["missing_reason"])
    elif valuation.get("negative_pe_count"):
        _add_flag(flags, "notice", "行业内存在负 PE 样本", f"估值排名样本中负 PE 数量为 {valuation.get('negative_pe_count')}。")

    reports = cleaned.get("modules", {}).get("reports", {})
    if reports.get("top_keywords"):
        positive_hits = sum(reports["top_keywords"].get(word, 0) for word in POSITIVE_KEYWORDS)
        negative_hits = sum(reports["top_keywords"].get(word, 0) for word in NEGATIVE_KEYWORDS)
        if positive_hits > negative_hits:
            _add_flag(flags, "notice", "研报标题正向词更多", f"{name}研报标题正向关键词次数为 {positive_hits}。")

    return flags


def _resolve_industry_identity(modules: dict[str, Any], codes: dict[str, Any]) -> tuple[str | None, str | None]:
    for key in ("market", "capital_flow", "index_snapshot"):
        parsed = modules.get(key, {}).get("parsed", {})
        if parsed.get("industry_code") or parsed.get("industry_name"):
            return parsed.get("industry_code"), parsed.get("industry_name")
    return codes.get("bk_code"), None


def clean_industry_trend_data(
    industry_data: dict[str, Any],
    report_limit: int = 10,
    kline_tail_limit: int = 10,
    valuation_rank_limit: int = 20,
) -> dict[str, Any]:
    """Clean all single-industry modules generated from the review documents."""
    modules = industry_data.get("modules", {})
    codes = industry_data.get("codes", {})
    industry_code, industry_name = _resolve_industry_identity(modules, codes)

    cleaned = {
        "source": industry_data.get("source", "eastmoney"),
        "codes": codes,
        "industry_code": industry_code,
        "industry_name": industry_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "modules": {
            "market": compact_market(modules.get("market", {})),
            "capital_flow": compact_capital_flow(modules.get("capital_flow", {})),
            "index_snapshot": compact_index_snapshot(modules.get("index_snapshot", {})),
            "index_kline": compact_index_kline(modules.get("index_kline", {}), kline_tail_limit),
            "reports": compact_reports(modules.get("reports", {}), report_limit),
            "margin_trading": compact_margin_trading(modules.get("margin_trading", {})),
            "valuation": compact_valuation(modules.get("valuation", {}), valuation_rank_limit),
        },
    }
    cleaned["score_summary"] = _score_summary(cleaned)
    cleaned["risk_flags"] = _build_flags(cleaned)
    return cleaned
