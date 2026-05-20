"""Analyze cleaned valuation data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL


def build_valuation_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "latest": cleaned.get("latest") or {},
        "industry_rank": cleaned.get("industry_rank") or {},
        "industry_percentiles": cleaned.get("industry_percentiles") or {},
        "industry_stats": cleaned.get("industry_stats") or [],
        "valuation_reading": cleaned.get("valuation_reading") or {},
        "risk_flags": cleaned.get("risk_flags") or [],
    }


def build_valuation_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_valuation_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股估值分析助手。"
        "请围绕PE、PB、PEG、PCF、PS、行业排名、同行分位和估值风险做判断。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的估值清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高；"
        "评分需综合估值高低、同行分位、盈利/现金流估值可比性和增长兑现压力。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`汇总要点`用于后续最终投资结论汇总，可以稍完整但不要超过200字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_valuation(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_valuation_analysis_messages(cleaned),
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
        "module": "valuation",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_valuation_analysis_context(cleaned),
    }
