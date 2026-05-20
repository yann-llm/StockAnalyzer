"""Analyze cleaned industry data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL


def build_industry_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "industry_name": cleaned.get("industry_name"),
        "score_summary": cleaned.get("score_summary") or {},
        "risk_flags": cleaned.get("risk_flags") or [],
        "modules": cleaned.get("modules") or {},
    }


def build_industry_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_industry_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股行业景气与资金分析助手。"
        "请围绕行业评分、涨跌广度、指数趋势、主力资金、研报情绪、融资融券和行业估值做判断。"
        "评分要标准化、可复核，并尽量引用输入中的原始指标值。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的行业清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高。"
        "请优先参考`score_summary.overall_score`和各维度分数，并按以下标准化口径复核："
        "行业景气/涨跌广度20%（涨跌幅、上涨家数占比、市场热度）；"
        "指数趋势20%（5日、10日、20日涨跌幅及均线偏离，趋势向上加分）；"
        "主力资金25%（主力净流入、主力净占比、不同周期资金方向，一致流入加分）；"
        "研报情绪10%（正负面标题、机构覆盖数量，正向覆盖加分）；"
        "融资融券10%（融资净买入、余额变化，杠杆资金净流入适度加分）；"
        "行业估值15%（PE/PB/PEG、负PE数量、行业分位，估值合理加分，过热或盈利失真扣分）。"
        "若`risk_flags`出现高风险事项，应在对应维度继续扣分。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如分数、涨跌幅、资金净额、估值倍数或分位。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕行业与资金环境写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_industry(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_industry_analysis_messages(cleaned),
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
        "module": "industry",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_industry_analysis_context(cleaned),
    }
