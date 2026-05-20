"""Clean industry report-list module."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cleaning_common import date_only, round_number


POSITIVE_KEYWORDS = ("增长", "改善", "复苏", "回暖", "上行", "维持增长", "景气", "出海", "更新", "龙头")
NEGATIVE_KEYWORDS = ("下滑", "承压", "风险", "下降", "亏损", "价格战", "放缓")
POLICY_KEYWORDS = ("政策", "基建", "设备更新", "地产", "出口", "关税")
GROWTH_KEYWORDS = ("成长", "空间", "需求", "订单", "智能化", "电动化", "出口")


def keyword_hits(title: str) -> dict[str, list[str]]:
    return {
        "positive": [word for word in POSITIVE_KEYWORDS if word in title],
        "negative": [word for word in NEGATIVE_KEYWORDS if word in title],
        "policy": [word for word in POLICY_KEYWORDS if word in title],
        "growth": [word for word in GROWTH_KEYWORDS if word in title],
    }


def compact_report_forecast(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "actual_last_year_eps": round_number(row.get("actualLastYearEps"), 4),
        "actual_last_two_year_eps": round_number(row.get("actualLastTwoYearEps"), 4),
        "predict_this_year_eps": round_number(row.get("predictThisYearEps"), 4),
        "predict_next_year_eps": round_number(row.get("predictNextYearEps"), 4),
        "predict_next_two_year_eps": round_number(row.get("predictNextTwoYearEps"), 4),
        "predict_this_year_pe": round_number(row.get("predictThisYearPe"), 4),
        "predict_next_year_pe": round_number(row.get("predictNextYearPe"), 4),
        "predict_next_two_year_pe": round_number(row.get("predictNextTwoYearPe"), 4),
        "target_price_low": round_number(row.get("indvAimPriceL"), 4),
        "target_price_high": round_number(row.get("indvAimPriceT"), 4),
    }


def compact_rating_change(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_rating_code": row.get("emRatingCode"),
        "current_rating_value": round_number(row.get("emRatingValue"), 4),
        "current_rating_name": row.get("emRatingName"),
        "last_rating_code": row.get("lastEmRatingCode"),
        "last_rating_value": round_number(row.get("lastEmRatingValue"), 4),
        "last_rating_name": row.get("lastEmRatingName"),
        "stock_rating_code": row.get("sRatingCode"),
        "stock_rating_name": row.get("sRatingName"),
    }


def compact_reports(module: dict[str, Any], limit: int) -> dict[str, Any]:
    rows = module.get("parsed", {}).get("rows", [])
    reports = []
    orgs = Counter()
    ratings = Counter()
    keyword_counter = Counter()

    for row in rows[:limit]:
        title = row.get("title") or ""
        org = row.get("orgSName") or row.get("orgName")
        rating = row.get("emRatingName") or "-"
        hits = keyword_hits(title)
        for words in hits.values():
            keyword_counter.update(words)
        if org:
            orgs[org] += 1
        ratings[rating] += 1
        reports.append(
            {
                "title": title,
                "publish_date": date_only(row.get("publishDate")),
                "industry_code": row.get("industryCode"),
                "industry_name": row.get("industryName"),
                "org": org,
                "researcher": row.get("researcher"),
                "rating": rating,
                "rating_change": row.get("ratingChange") or "-",
                "rating_detail": compact_rating_change(row),
                "forecast": compact_report_forecast(row),
                "monthly_report_count": round_number(row.get("count"), 0),
                "info_code": row.get("infoCode"),
                "keyword_hits": hits,
            }
        )

    return {
        "page": module.get("page", {}),
        "total_rows_in_page": len(rows),
        "unique_org_count": len(orgs),
        "rating_counts": dict(ratings),
        "top_keywords": dict(keyword_counter.most_common(15)),
        "latest_reports": reports,
    }
