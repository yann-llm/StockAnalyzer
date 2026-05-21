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
            "revenue_yoy": trends.get("revenue_yoy", []),
            "net_profit": trends.get("net_profit", []),
            "net_profit_yoy": trends.get("net_profit_yoy", []),
            "deduct_net_profit": trends.get("deduct_net_profit", []),
            "deduct_net_profit_yoy": trends.get("deduct_net_profit_yoy", []),
            "gross_margin": trends.get("gross_margin", []),
            "net_margin": trends.get("net_margin", []),
            "roe": trends.get("roe", []),
            "debt_asset_ratio": trends.get("debt_asset_ratio", []),
            "operating_cash_flow": trends.get("operating_cash_flow", []),
            "operating_cash_flow_yoy": trends.get("operating_cash_flow_yoy", []),
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
        "应收账款、存货和财务风险。评分要标准化、可复核，并尽量引用输入中的原始指标值。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的财务摘要输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高，并满足以下分数与结论的对齐区间："
        "0-39偏弱可规避，40-59中性观察，60-74稳健，75-100优秀。"
        "请按以下标准化口径评分：盈利增长30%（基于`latest`中的`revenue_yoy`/`net_profit_yoy`/`deduct_net_profit_yoy`及`trends`同比序列，持续增长加分，明显下滑扣分）；"
        "盈利质量20%（`latest.gross_margin`/`net_margin`/`roe`及对应`trends`，盈利能力稳定或改善加分）；"
        "现金流25%（`latest.operating_cash_flow`、`operating_cash_to_net_profit`、`sales_cash_to_revenue`及`trends.operating_cash_flow`，现金流覆盖利润加分，长期低于利润扣分）；"
        "资产负债15%（`debt_asset_ratio`、`liability_to_equity`、`total_equity_yoy`，杠杆适中加分，负债率偏高扣分）；"
        "营运占用10%（`accounts_receivable_yoy`/`inventory_yoy`与`revenue_yoy`匹配度，占用过快上升扣分）。"
        "若`risk_flags`出现`level=warning`事项，应在对应维度继续扣分；`level=notice`仅作提示。"
        "数据缺失处理：若关键字段为null或趋势序列少于3期，应在`简短结论`末尾标注\"数据不足\"并避免给出85分以上的高分。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如同比、比率、金额或期末值。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕财务质量写成一段或短句列表，保留关键原始数值，"
        "不要超过1000字。"
        "字段值中可使用通用金融术语（ROE、毛利率、净利率等），但JSON键名必须全部使用上述中文键名。\n\n"
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
