"""Analyze cleaned financial indicators with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL


def build_financial_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    data = cleaned.get("data") if isinstance(cleaned.get("data"), dict) else cleaned
    latest = data.get("latest") or {}
    trends = data.get("trends") or {}
    return {
        "stock_code": cleaned.get("stock_code") or data.get("stock_code"),
        "source": cleaned.get("source") or data.get("source", "eastmoney"),
        "latest": latest,
        "risk_flags": data.get("risk_flags") or [],
        "metadata": data.get("metadata") or {},
        "trends": {
            "revenue": trends.get("revenue", []),
            "net_profit": trends.get("net_profit", []),
            "net_margin": trends.get("net_margin", []),
            "roe": trends.get("roe", []),
            "debt_asset_ratio": trends.get("debt_asset_ratio", []),
            "operating_cash_flow": trends.get("operating_cash_flow", []),
            "accounts_receivable": trends.get("accounts_receivable", []),
            "inventory": trends.get("inventory", []),
            "total_equity": trends.get("total_equity", []),
        },
    }


def build_financial_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_financial_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股财务分析助手。"
        "请基于给定的清洗后财务指标，判断收入、利润、毛利率、ROE、资产负债率、经营现金流、"
        "应收账款、存货和财务风险。只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的财务摘要输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高；"
        "评分需综合盈利增长、现金流质量、资产负债、营运资金占用和风险提示。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`汇总要点`用于后续最终投资结论汇总，可以稍完整但不要超过200字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_financial_reports(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_financial_analysis_messages(cleaned),
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
        "module": "financial",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_financial_analysis_context(cleaned),
    }
