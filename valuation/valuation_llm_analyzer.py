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
        "评分要标准化、可复核，并尽量引用输入中的原始指标值。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的估值清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高。"
        "请按以下标准化口径评分：相对估值35%（PE、PB、PS相对行业均值/中位数/分位，低于可比中枢加分，显著溢价扣分）；"
        "成长匹配25%（PEG和盈利增长匹配度，PEG合理或增长能覆盖估值加分）；"
        "现金流估值20%（PCF、经营现金流估值可解释性，现金流估值偏低加分，现金流失真扣分）；"
        "行业排名/分位15%（同行排名、行业分位，估值处于合理低位加分）；"
        "估值风险5%（负PE、极端倍数、数据缺失或`risk_flags`提示，风险越高扣分）。"
        "若盈利为负、PE失真或关键倍数缺失，不要机械给高分，应转向PB、PS、PCF并说明局限。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如PE、PB、PEG、PCF、PS、排名或分位。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕估值性价比写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
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
