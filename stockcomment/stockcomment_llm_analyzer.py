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
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的千股千评清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高；"
        "评分需综合个股评分、资金流、技术趋势、市场热度、舆情和辅助财务信号。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`汇总要点`用于后续最终投资结论汇总，可以稍完整但不要超过200字。"
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
