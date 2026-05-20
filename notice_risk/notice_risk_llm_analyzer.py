"""Analyze cleaned notice-risk data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL


def build_notice_risk_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "risk_candidates": cleaned.get("risk_candidates") or [],
        "risk_flags": cleaned.get("risk_flags") or [],
        "modules": cleaned.get("modules") or {},
    }


def build_notice_risk_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_notice_risk_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股公告风险分析助手。"
        "请围绕公告标题、公告类型、风险关键词和候选风险事件判断风险等级与后续关注事项。"
        "评分要标准化、可复核，并尽量引用输入中的原始公告日期、标题、数量和风险级别。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的公告风险清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高。"
        "请按以下标准化口径评分：事件严重度40%（监管处罚、诉讼仲裁、业绩预警、担保违约、减持、重大资产变化等越严重扣分越多）；"
        "近期性25%（越接近当前披露期影响越大，近期重大风险继续扣分）；"
        "频率20%（同类风险反复出现、风险候选数量多或风险标记密集扣分）；"
        "影响范围15%（涉及利润、现金流、控制权、偿债、安全生产或持续经营的事项扣分更高）。"
        "若公告以分红、回购、经营改善等正向事项为主且无重大负面风险，可适度加分；公告风险越高分数越低。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如公告日期、公告标题、风险关键词、候选数量或风险级别。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕公告风险安全边际写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_notice_risk(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_notice_risk_analysis_messages(cleaned),
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
        "module": "notice_risk",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_notice_risk_analysis_context(cleaned),
    }
