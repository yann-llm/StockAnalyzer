"""清洗千股千评接口数据，输出适合综合评分程序使用的摘要。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _first(module: dict[str, Any]) -> dict[str, Any]:
    rows = module.get("rows") or []
    return rows[0] if rows else {}


def _number(value: Any) -> float | None:
    """把接口返回值统一转为数字；空值、横线和异常文本统一转为 None。"""
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> float | None:
    """统一数值精度，避免后续评分或大模型分析被超长小数干扰。"""
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def _ratio(numerator: Any, denominator: Any, digits: int = 4) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom in (None, 0):
        return None
    return round(top / bottom * 100, digits)


def _rank_percentile(rank: Any, total: Any) -> float | None:
    """排名越靠前分位越高，便于评分器正向读取。"""
    rank_number = _number(rank)
    total_number = _number(total)
    if rank_number is None or total_number in (None, 0):
        return None
    return round((1 - (rank_number - 1) / total_number) * 100, 4)


def _distance_ratio(value: Any, base: Any) -> float | None:
    return _ratio((_number(value) or 0) - (_number(base) or 0), base)


def _date(value: Any) -> Any:
    """页面多数日期只展示到天，清洗时保留 yyyy-mm-dd 方便人工对照。"""
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return value


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[: len(fmt.replace("%f", "000"))], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value[:19])
    except ValueError:
        return None


def _count_recent(
    rows: list[dict[str, Any]],
    date_field: str,
    days: int = 7,
    reference_date: datetime | None = None,
) -> int:
    """按页面逻辑统计近一周舆情数量，新闻、公告、研报分别统计后汇总。"""
    reference = reference_date or datetime.now()
    cutoff = reference - timedelta(days=days)
    count = 0
    for row in rows:
        item_date = _parse_date(row.get(date_field))
        if item_date and cutoff <= item_date <= reference:
            count += 1
    return count


def _add_flag(flags: list[dict[str, Any]], level: str, title: str, detail: str) -> None:
    flags.append({"level": level, "title": title, "detail": detail})


def _rating_counts(report_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in report_rows:
        rating = row.get("emRatingName") or "未评级"
        counts[rating] = counts.get(rating, 0) + 1
    return counts


def clean_stockcomment_data(stockcomment_data: dict[str, Any]) -> dict[str, Any]:
    """按 review.md 的 7 大板块清洗千股千评数据。

    清洗逻辑：
    1. 只使用 review.md 中确认过的接口字段，不引入页面外字段。
    2. 每个板块保留原接口字段含义相近的英文摘要键，方便评分程序稳定读取。
    3. 舆情监控按页面脚本逻辑统计近一周新闻、公告、研报数量。
    4. 涨跌预测模块在 review.md 中没有独立接口字段，只输出 unsupported 说明。
    """
    modules = stockcomment_data.get("modules", {})
    custom = _first(modules.get("custom_stock_pk", {}))
    history = _first(modules.get("history_mark", {}))
    rank = _first(modules.get("pk_rank", {}))
    evaluate = _first(modules.get("stock_evaluate", {}))
    focus = _first(modules.get("market_focus", {}))
    participation = _first(modules.get("participation", {}))
    trend_comment = _first(modules.get("trend_comment", {}))
    trend_volume = _first(modules.get("trend_volume", {}))
    macd = _first(modules.get("macd", {}))
    capital = _first(modules.get("capital_flows", {}))
    margin = _first(modules.get("margin_trend", {}))
    financial = _first(modules.get("financial_analysis", {}))
    company_type = _first(modules.get("company_type", {}))

    news_rows = modules.get("news", {}).get("rows", [])
    announcement_rows = modules.get("announcements", {}).get("rows", [])
    report_rows = modules.get("reports", {}).get("rows", [])
    stockboard_rows = modules.get("stockboard_rank", {}).get("rows", [])
    secucode = capital.get("SECUCODE")
    current_stockboard = next((row for row in stockboard_rows if row.get("SECUCODE") == secucode), {})

    reference_date = (
        _parse_date(custom.get("DIAGNOSE_TIME"))
        or _parse_date(rank.get("TRADE_DATE"))
        or _parse_date(evaluate.get("TRADE_DATE"))
    )
    news_count = _count_recent(news_rows, "Art_ShowTime", reference_date=reference_date)
    notice_count = _count_recent(announcement_rows, "notice_date", reference_date=reference_date)
    report_count = _count_recent(report_rows, "publishDate", reference_date=reference_date)

    cleaned = {
        "stock_code": stockcomment_data.get("stock_code"),
        "source": stockcomment_data.get("source", "eastmoney"),
        "modules": {
            "综合评价": {
                "diagnose_time": custom.get("DIAGNOSE_TIME"),
                "total_score": _round(custom.get("TOTAL_SCORE")),
                "total_score_change": _round(custom.get("TOTAL_SCORE_CHANGE")),
                "stock_rank_ratio": _round(custom.get("STOCK_RANK_RATIO")),
                "rise_1_probability": _round(custom.get("RISE_1_PROBABILITY")),
                "words_explain": custom.get("WORDS_EXPLAIN"),
                "history_date": _date(history.get("DIAGNOSE_DATE")),
                "history_close": _round(history.get("CLOSE")),
                "history_total_score": _round(history.get("TOTAL_SCORE")),
                "market_rank": rank.get("MARKET_RANK"),
                "evaluate_market_num": rank.get("EVALUATE_MARKET_NUM"),
                "market_stock_num": rank.get("MARKET_STOCK_NUM"),
                "market_rank_percentile": _rank_percentile(rank.get("MARKET_RANK"), rank.get("EVALUATE_MARKET_NUM")),
                "market_score_high": _round(rank.get("MARKET_SCORE_HIGH")),
                "market_score_low": _round(rank.get("MARKET_SCORE_LOW")),
                "market_score_avg": _round(rank.get("MARKET_SCORE_AVG")),
                "industry_rank": rank.get("INDUSTRY_RANK"),
                "industry_name": rank.get("BOARD_NAME"),
                "evaluate_industry_num": rank.get("EVALUATE_INDUSTRY_NUM"),
                "industry_stock_num": rank.get("INDUSTRY_STOCK_NUM"),
                "industry_rank_percentile": _rank_percentile(rank.get("INDUSTRY_RANK"), rank.get("EVALUATE_INDUSTRY_NUM")),
                "industry_score_high": _round(rank.get("INDUSTRY_SCORE_HIGH")),
                "industry_score_low": _round(rank.get("INDUSTRY_SCORE_LOW")),
                "industry_score_avg": _round(rank.get("INDUSTRY_SCORE_AVG")),
                "change_rate": _round(rank.get("CHANGE_RATE")),
                "unsupported": stockcomment_data.get("unsupported_by_review", {}),
            },
            "主力控盘": {
                "trade_date": _date(evaluate.get("TRADE_DATE")),
                "close_price": _round(evaluate.get("CLOSE_PRICE")),
                "change_rate": _round(evaluate.get("CHANGE_RATE")),
                "turnover_rate": _round(evaluate.get("TURNOVERRATE")),
                "superdeal_inflow": _round(evaluate.get("SUPERDEAL_INFLOW"), 2),
                "superdeal_outflow": _round(evaluate.get("SUPERDEAL_OUTFLOW"), 2),
                "bigdeal_inflow": _round(evaluate.get("BIGDEAL_INFLOW"), 2),
                "bigdeal_outflow": _round(evaluate.get("BIGDEAL_OUTFLOW"), 2),
                "prime_inflow": _round(evaluate.get("PRIME_INFLOW"), 2),
                "prime_cost": _round(evaluate.get("PRIME_COST")),
                "prime_cost_20days": _round(evaluate.get("PRIME_COST_20DAYS")),
                "prime_cost_60days": _round(evaluate.get("PRIME_COST_60DAYS")),
                "org_participate": _round(evaluate.get("ORG_PARTICIPATE")),
                "participate_type": evaluate.get("PARTICIPATE_TYPE"),
                "participate_type_cn": evaluate.get("PARTICIPATE_TYPE_CN"),
                "buy_superdeal_ratio": _round(evaluate.get("BUY_SUPERDEAL_RATIO")),
                "buy_bigdeal_ratio": _round(evaluate.get("BUY_BIGDEAL_RATIO")),
                "ratio": _round(evaluate.get("RATIO")),
                "ratio_3days": _round(evaluate.get("RATIO_3DAYS")),
                "ratio_50days": _round(evaluate.get("RATIO_50DAYS")),
                "pe_dynamic": _round(evaluate.get("PE_DYNAMIC")),
            },
            "舆情监控": {
                "recent_total_count": news_count + notice_count + report_count,
                "recent_news_count": news_count,
                "recent_notice_count": notice_count,
                "recent_report_count": report_count,
                "news": [
                    {
                        "title": row.get("Art_Title"),
                        "date": _date(row.get("Art_ShowTime")),
                        "code": row.get("Art_Code"),
                        "url": row.get("Art_Url"),
                    }
                    for row in news_rows
                ],
                "announcements": [
                    {"title": row.get("title"), "date": _date(row.get("notice_date")), "art_code": row.get("art_code")}
                    for row in announcement_rows
                ],
                "reports": [
                    {
                        "title": row.get("title"),
                        "date": _date(row.get("publishDate")),
                        "info_code": row.get("infoCode"),
                        "org_name": row.get("orgSName"),
                        "rating": row.get("emRatingName"),
                    }
                    for row in report_rows
                ],
                "report_rating_counts": _rating_counts(report_rows),
            },
            "市场热度": {
                "trade_date": _date(focus.get("TRADE_DATE") or participation.get("TRADE_DATE")),
                "market_focus": _round(focus.get("MARKET_FOCUS")),
                "market_focus_rank": focus.get("MARKET_FOCUS_RANK"),
                "total_market": focus.get("TOTAL_MARKET"),
                "market_focus_change": _round(focus.get("MARKET_FOCUS_CHANGE")),
                "close_price": _round(focus.get("CLOSE_PRICE")),
                "participation_wish": _round(participation.get("PARTICIPATION_WISH")),
                "participation_wish_5days": _round(participation.get("PARTICIPATION_WISH_5DAYS")),
                "participation_wish_change": _round(participation.get("PARTICIPATION_WISH_CHANGE")),
                "participation_wish_5days_change": _round(participation.get("PARTICIPATION_WISH_5DAYSCHANGE")),
            },
            "趋势研判": {
                "trade_date": _date(trend_comment.get("TRADE_DATE") or macd.get("TRADEDATE")),
                "comment": trend_comment.get("COMMENT_TXT"),
                "price_avg_relation": trend_volume.get("PRICE_AVG_RELATION"),
                "volume_judge": trend_volume.get("VOLUME_JUDGE"),
                "par_focus": trend_volume.get("PAR_FOCUS"),
                "support_level": _round(trend_volume.get("SUPPORT_LEVEL")),
                "pressure_level": _round(trend_volume.get("PRESSURE_LEVEL")),
                "avg_price": trend_volume.get("AVG_PRICE"),
                "deal_amount": _round(trend_volume.get("DEAL_AMOUNT"), 2),
                "avg_amount_5days": _round(trend_volume.get("AVG_AMOUNT_5DAYS"), 2),
                "deal_amount_vs_5day_avg": _distance_ratio(
                    trend_volume.get("DEAL_AMOUNT"), trend_volume.get("AVG_AMOUNT_5DAYS")
                ),
                "words_explain": trend_volume.get("WORDS_EXPLAIN"),
                "new_price": _round(macd.get("NEW")),
                "open_price": _round(macd.get("OPEN")),
                "high_price": _round(macd.get("HIGH")),
                "low_price": _round(macd.get("LOW")),
                "pctchange_stock": _round(macd.get("PCTCHANGE_STOCK")),
                "pctchange_index": _round(macd.get("PCTCHANGE_INDEX")),
                "relative_pctchange": _round(
                    (_number(macd.get("PCTCHANGE_STOCK")) or 0) - (_number(macd.get("PCTCHANGE_INDEX")) or 0)
                ),
                "swing": _round(macd.get("SWING")),
                "avg_turnover": _round(macd.get("AVGTURN")),
                "dif": _round(macd.get("DIF")),
                "dea": _round(macd.get("DEA")),
                "macd": _round(macd.get("MACD")),
                "k": _round(macd.get("K")),
                "d": _round(macd.get("D")),
                "j": _round(macd.get("J")),
                "rsi1": _round(macd.get("RSI1")),
                "rsi2": _round(macd.get("RSI2")),
                "rsi3": _round(macd.get("RSI3")),
                "boll_mid": _round(macd.get("MID")),
                "boll_upper": _round(macd.get("UPPER")),
                "boll_lower": _round(macd.get("LOWER")),
                "macd_signal": macd.get("MACDCOUT"),
                "macd_color": macd.get("MACDCLOR"),
                "kdj_signal": macd.get("KDJOUT"),
                "kdj_color": macd.get("KDJCLOR"),
                "rsi_signal": macd.get("RSIOUT"),
                "rsi_color": macd.get("RSICLOR"),
                "boll_signal": macd.get("BOLLOUT"),
                "boll_color": macd.get("BOLLCLOR"),
                "bias_signal": macd.get("BIASOUT"),
                "bias_color": macd.get("BIASCLOR"),
                "wr_signal": macd.get("WROUT"),
                "wr_color": macd.get("WRCLOR"),
            },
            "资金动向": {
                "trade_date": _date(capital.get("TRADE_DATE")),
                "capital_flows": _round(capital.get("CAPITAL_FLOWS"), 2),
                "capital_flows_5days": _round(capital.get("CAPITAL_FLOWS_5DAYS"), 2),
                "capital_flows_ratio": _round(capital.get("CAPITAL_FLOWS_RATIO")),
                "capital_flows_5days_ratio": _round(capital.get("CAPITAL_FLOWS_5DAYSRATIO")),
                "board_code": capital.get("BOARD_CODE"),
                "board_name": capital.get("BOARD_NAME"),
                "board_capital_flows": _round(capital.get("BOARD_CAPITAL_FLOWS"), 2),
                "board_capital_5flows": _round(capital.get("BOARD_CAPITAL_5FLOWS"), 2),
                "stockboard_top": [
                    {
                        "rank": row.get("CAPITAL_FLOWS_RANK"),
                        "name": row.get("SECURITY_NAME_ABBR"),
                        "capital_flows": _round(row.get("CAPITAL_FLOWS"), 2),
                    }
                    for row in stockboard_rows[:3]
                ],
                "current_stockboard_rank": current_stockboard.get("CAPITAL_FLOWS_RANK"),
                "current_stockboard_name": current_stockboard.get("SECURITY_NAME_ABBR"),
                "current_stockboard_capital_flows": _round(current_stockboard.get("CAPITAL_FLOWS"), 2),
                "margin_trade_date": _date(margin.get("TRADE_DATE")),
                "fin_balance_diff": _round(margin.get("FIN_BALANCE_DIFF"), 2),
                "free_ratio": _round(margin.get("FREE_RATIO")),
                "avg_free_ratio": _round(margin.get("AVG_FREE_RATIO")),
                "finbalance_diff_change": _round(margin.get("FINBALANCE_DIFF_CHANGE")),
                "fin_balance": _round(margin.get("FIN_BALANCE"), 2),
                "loan_balance": _round(margin.get("LOAN_BALANCE"), 2),
                "margin_explain": margin.get("EXPLAIN"),
            },
            "财务评估": {
                "report_date": _date(financial.get("REPORT_DATE")),
                "group_date": _date(financial.get("GROUP_DATE")),
                "date_type": financial.get("DATE_TYPE"),
                "company_type": company_type.get("COMPANY_TYPE"),
                "weight_roe": _round(financial.get("WEIGHT_ROE")),
                "core_profit": _round(financial.get("CORE_RPOFIT"), 2),
                "total_profit": _round(financial.get("TOTAL_PROFIT"), 2),
                "core_profit_ratio": _round(financial.get("CORE_RPOFIT_RATIO")),
                "gross_profit_ratio": _round(financial.get("GROSS_RPOFIT_RATIO")),
                "sale_npr": _round(financial.get("SALE_NPR")),
                "debt_asset_ratio": _round(financial.get("DEBT_ASSET_RATIO")),
                "current_ratio": _round(financial.get("CURRENT_RATIO")),
                "inventory_turnover": _round(financial.get("INVENTORY_TR")),
                "accounts_receivable_turnover": _round(financial.get("ACCOUNTS_RECE_TR")),
                "total_assets_turnover": _round(financial.get("TOTAL_ASSETS_TR")),
                "current_total_assets_turnover": _round(financial.get("CURRENT_TOTAL_ASSETS_TR")),
                "weight_roe_rank": _round(financial.get("WEIGHT_ROE_RANK")),
                "netprofit_yoy_ratio_rank": _round(financial.get("NETPROFIT_YOY_RATIO_RANK")),
                "total_assets_turnover_rank": _round(financial.get("TOTAL_ASSETS_TR_RANK")),
                "sale_cash_ratio_rank": _round(financial.get("SALE_CASH_RATIO_RANK")),
                "debt_asset_ratio_rank": _round(financial.get("DEBT_ASSET_RATIO_RANK")),
                "sale_cash_ratio": _round(financial.get("SALE_CASH_RATIO")),
                "sx_ratio": _round(financial.get("SX_RATIO")),
                "jx_ratio": _round(financial.get("JX_RATIO")),
                "netcash_operate": _round(financial.get("NETCASH_OPERATE"), 2),
                "netcash_invest": _round(financial.get("NETCASH_INVEST"), 2),
                "netcash_finance": _round(financial.get("NETCASH_FINANCE"), 2),
                "netprofit_yoy_ratio": _round(financial.get("NETPROFIT_YOY_RATIO")),
                "total_operate_income_ratio": _round(financial.get("TOTAL_OPERATE_INCOME_RATIO")),
                "total_assets_ratio": _round(financial.get("TOTAL_ASSETS_RATIO")),
            },
        },
    }
    modules_cleaned = cleaned["modules"]
    cleaned["score_features"] = {
        "overall": {
            "total_score": modules_cleaned["综合评价"].get("total_score"),
            "total_score_change": modules_cleaned["综合评价"].get("total_score_change"),
            "rise_1_probability": modules_cleaned["综合评价"].get("rise_1_probability"),
            "market_rank_percentile": modules_cleaned["综合评价"].get("market_rank_percentile"),
            "industry_rank_percentile": modules_cleaned["综合评价"].get("industry_rank_percentile"),
            "market_score_avg": modules_cleaned["综合评价"].get("market_score_avg"),
            "industry_score_avg": modules_cleaned["综合评价"].get("industry_score_avg"),
        },
        "capital_flow": {
            "prime_inflow": modules_cleaned["主力控盘"].get("prime_inflow"),
            "buy_superdeal_ratio": modules_cleaned["主力控盘"].get("buy_superdeal_ratio"),
            "buy_bigdeal_ratio": modules_cleaned["主力控盘"].get("buy_bigdeal_ratio"),
            "capital_flows": modules_cleaned["资金动向"].get("capital_flows"),
            "capital_flows_5days": modules_cleaned["资金动向"].get("capital_flows_5days"),
            "board_capital_flows": modules_cleaned["资金动向"].get("board_capital_flows"),
            "board_capital_5flows": modules_cleaned["资金动向"].get("board_capital_5flows"),
            "current_stockboard_rank": modules_cleaned["资金动向"].get("current_stockboard_rank"),
            "fin_balance_diff": modules_cleaned["资金动向"].get("fin_balance_diff"),
            "finbalance_diff_change": modules_cleaned["资金动向"].get("finbalance_diff_change"),
            "margin_explain": modules_cleaned["资金动向"].get("margin_explain"),
        },
        "technical": {
            "trend_comment": modules_cleaned["趋势研判"].get("comment"),
            "price_avg_relation": modules_cleaned["趋势研判"].get("price_avg_relation"),
            "volume_judge": modules_cleaned["趋势研判"].get("volume_judge"),
            "support_level": modules_cleaned["趋势研判"].get("support_level"),
            "pressure_level": modules_cleaned["趋势研判"].get("pressure_level"),
            "deal_amount_vs_5day_avg": modules_cleaned["趋势研判"].get("deal_amount_vs_5day_avg"),
            "relative_pctchange": modules_cleaned["趋势研判"].get("relative_pctchange"),
            "macd": modules_cleaned["趋势研判"].get("macd"),
            "k": modules_cleaned["趋势研判"].get("k"),
            "d": modules_cleaned["趋势研判"].get("d"),
            "j": modules_cleaned["趋势研判"].get("j"),
            "rsi1": modules_cleaned["趋势研判"].get("rsi1"),
            "boll_lower": modules_cleaned["趋势研判"].get("boll_lower"),
            "boll_signal": modules_cleaned["趋势研判"].get("boll_signal"),
            "wr_signal": modules_cleaned["趋势研判"].get("wr_signal"),
        },
        "sentiment": {
            "market_focus": modules_cleaned["市场热度"].get("market_focus"),
            "market_focus_rank": modules_cleaned["市场热度"].get("market_focus_rank"),
            "participation_wish": modules_cleaned["市场热度"].get("participation_wish"),
            "participation_wish_change": modules_cleaned["市场热度"].get("participation_wish_change"),
            "recent_total_count": modules_cleaned["舆情监控"].get("recent_total_count"),
            "recent_news_count": modules_cleaned["舆情监控"].get("recent_news_count"),
            "recent_notice_count": modules_cleaned["舆情监控"].get("recent_notice_count"),
            "recent_report_count": modules_cleaned["舆情监控"].get("recent_report_count"),
            "report_rating_counts": modules_cleaned["舆情监控"].get("report_rating_counts"),
        },
        "aux_financial": {
            "weight_roe": modules_cleaned["财务评估"].get("weight_roe"),
            "weight_roe_rank": modules_cleaned["财务评估"].get("weight_roe_rank"),
            "netprofit_yoy_ratio": modules_cleaned["财务评估"].get("netprofit_yoy_ratio"),
            "netprofit_yoy_ratio_rank": modules_cleaned["财务评估"].get("netprofit_yoy_ratio_rank"),
            "debt_asset_ratio": modules_cleaned["财务评估"].get("debt_asset_ratio"),
            "debt_asset_ratio_rank": modules_cleaned["财务评估"].get("debt_asset_ratio_rank"),
            "current_ratio": modules_cleaned["财务评估"].get("current_ratio"),
            "total_assets_turnover_rank": modules_cleaned["财务评估"].get("total_assets_turnover_rank"),
            "sale_cash_ratio_rank": modules_cleaned["财务评估"].get("sale_cash_ratio_rank"),
        },
    }
    cleaned["risk_flags"] = _build_risk_flags(cleaned["modules"])
    return cleaned


def _build_risk_flags(modules: dict[str, Any]) -> list[dict[str, Any]]:
    """基于千股千评字段生成初步风险提示，不引入 review 外数据。"""
    flags: list[dict[str, Any]] = []
    score = _number(modules["综合评价"].get("total_score"))
    prime_inflow = _number(modules["主力控盘"].get("prime_inflow"))
    capital_flows = _number(modules["资金动向"].get("capital_flows"))
    trend_comment = modules["趋势研判"].get("comment") or ""
    netprofit_yoy = _number(modules["财务评估"].get("netprofit_yoy_ratio"))

    if score is not None and score < 60:
        _add_flag(flags, "warning", "综合评分偏低", f"综合评分为 {score}。")
    if prime_inflow is not None and prime_inflow < 0:
        _add_flag(flags, "notice", "主力控盘资金净流出", f"主力净流入为 {prime_inflow}。")
    if capital_flows is not None and capital_flows < 0:
        _add_flag(flags, "warning", "资金动向净流出", f"个股主力净流入为 {capital_flows}。")
    if "风险较高" in trend_comment:
        _add_flag(flags, "warning", "趋势研判提示风险较高", trend_comment)
    if netprofit_yoy is not None and netprofit_yoy < 0:
        _add_flag(flags, "warning", "财务评估净利润同比下降", f"净利润同比增速为 {netprofit_yoy}%。")
    return flags
