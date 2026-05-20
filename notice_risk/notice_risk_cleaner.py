"""Clean Eastmoney notice-risk data."""

from __future__ import annotations

from typing import Any


RISK_KEYWORDS = [
    "风险提示",
    "异常波动",
    "停牌",
    "复牌",
    "澄清",
    "诉讼",
    "仲裁",
    "处罚",
    "监管函",
    "问询函",
    "立案",
    "调查",
    "资金占用",
    "对外担保",
    "关联交易",
    "资产减值",
    "资产核销",
    "股份质押",
    "冻结",
    "债务",
    "授信",
    "募集资金",
    "审计意见",
    "内部控制",
    "会计差错",
    "业绩预告",
    "亏损",
    "重组",
    "分拆",
    "可转债",
]


def _notice_brief(row: dict[str, Any]) -> dict[str, Any]:
    """只保留风险分析需要的公告摘要字段。"""
    title = row.get("title") or ""
    column_names = [col.get("name") for col in row.get("columns", []) if col.get("name")]
    matched_keywords = [word for word in RISK_KEYWORDS if word in title or any(word in name for name in column_names)]
    return {
        "art_code": row.get("art_code"),
        "title": title,
        "notice_date": row.get("notice_date"),
        "publish_time": row.get("publish_time"),
        "columns": column_names,
        "matched_keywords": matched_keywords,
    }


def clean_notice_risk_data(notice_data: dict[str, Any], top_limit: int = 10) -> dict[str, Any]:
    """清洗公告风险数据，生成适合评分和大模型分析的摘要。

    清洗原则：
    1. 每个公告分类只保留前 top_limit 条，避免公告列表过长。
    2. 用标题和公告类型匹配风险关键词，形成候选风险事件。
    3. 只输出公告摘要，不在清洗阶段请求正文，正文应针对候选事件按需获取。
    """
    modules = notice_data.get("modules", {})
    cleaned_modules = {}
    candidates = []

    for category, module in modules.items():
        rows = [_notice_brief(row) for row in module.get("rows", [])[:top_limit]]
        cleaned_modules[category] = {
            "category": category,
            "total": module.get("total"),
            "notices": rows,
        }
        # 命中关键词的公告进入候选风险事件，后续可用 art_code 获取正文。
        candidates.extend(row for row in rows if row.get("matched_keywords"))

    return {
        "stock_code": notice_data.get("stock_code"),
        "source": notice_data.get("source", "eastmoney"),
        "modules": cleaned_modules,
        "risk_candidates": candidates,
        "risk_flags": [
            {
                "level": "warning",
                "title": "发现公告风险候选事件",
                "detail": f"共发现 {len(candidates)} 条命中风险关键词的公告。",
            }
        ]
        if candidates
        else [],
    }
