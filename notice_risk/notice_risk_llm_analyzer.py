"""Analyze cleaned notice-risk data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion, parse_llm_json

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
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高，并满足以下分数与结论的对齐区间："
        "0-39偏弱可规避，40-59中性观察，60-74稳健，75-100优秀。"
        "评分基线：无任何风险候选或风险标记时默认从80分起评，按以下维度对应扣分；正向公告（分红、回购、增持、经营改善）最多额外+5分，不得突破95分。"
        "扣分口径：事件严重度40%（监管处罚、诉讼仲裁、业绩预警、担保违约、减持、重大资产变化等越严重扣分越多）；"
        "近期性25%（越接近当前披露期影响越大，近期重大风险继续扣分）；"
        "频率20%（同类风险反复出现、风险候选数量多或风险标记密集扣分）；"
        "影响范围15%（涉及利润、现金流、控制权、偿债、安全生产或持续经营的事项扣分更高）。"
        "数据缺失处理：若`risk_candidates`和`risk_flags`均为空且公告样本少于5条，应在`简短结论`末尾标注\"样本不足\"并将分数控制在65-75之间避免过度乐观。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如公告日期、公告标题、风险关键词、候选数量或风险级别。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕公告风险安全边际写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
        "字段值中可使用通用金融术语，但JSON键名必须全部使用上述中文键名。\n\n"
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
    analysis = parse_llm_json(content)
    return {
        "module": "notice_risk",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_notice_risk_analysis_context(cleaned),
    }
