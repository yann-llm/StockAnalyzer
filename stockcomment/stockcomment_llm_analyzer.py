"""Analyze cleaned stockcomment data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL


def build_stockcomment_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "score_features": cleaned.get("score_features") or {},
        "modules": cleaned.get("modules") or {},
        "risk_flags": cleaned.get("risk_flags") or [],
    }


def build_stockcomment_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_stockcomment_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股交易与市场情绪分析助手。"
        "请围绕综合评分、主力资金、技术趋势、市场热度、舆情和财务辅助信号做判断。"
        "评分要标准化、可复核，并尽量引用输入中的原始指标值。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的千股千评清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高。"
        "请优先参考`score_features.evaluation.total_score`，并按以下标准化口径复核："
        "平台综合评价25%（当前总评分、评分变化、市场/行业均值和排名分位）；"
        "资金流25%（主力净流入、超大/大/中/小单方向，多周期一致流入加分）；"
        "技术趋势20%（趋势研判、短中期信号、价格强弱，趋势走强加分，破位或弱势扣分）；"
        "市场热度10%（关注度、活跃度、量价配合，热度有效放大加分）；"
        "舆情事件10%（新闻、公告、研报数量和情绪，负面密集扣分）；"
        "财务辅助10%（输入中提供的盈利、负债、现金流辅助信号，质量改善加分）。"
        "若`risk_flags`出现高风险事项，应在对应维度继续扣分。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如总评分、评分变化、净流入金额、排名或舆情数量。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕交易信号与市场情绪写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_stockcomment(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_stockcomment_analysis_messages(cleaned),
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    try:
        analysis = json.loads(content)
    except json.JSONDecodeError:
        analysis = {"raw_text": content}
    return {
        "module": "stockcomment",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_stockcomment_analysis_context(cleaned),
    }
