"""Analyze cleaned ETF fund score blocks with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion


MODEL_NAME = DEFAULT_MODEL


def build_etf_fund_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    blocks = cleaned.get("blocks") or {}
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney_fundf10"),
        "security_type": cleaned.get("security_type", "etf"),
        "overall_score": cleaned.get("overall_score"),
        "block_weights": cleaned.get("block_weights") or {},
        "blocks": {
            key: {
                "name": block.get("name"),
                "weight": block.get("weight"),
                "score": block.get("score"),
                "source_pages": block.get("source_pages"),
                "metrics": block.get("metrics"),
                "notes": block.get("notes"),
            }
            for key, block in blocks.items()
        },
        "risk_flags": cleaned.get("risk_flags") or [],
    }


def build_etf_fund_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_etf_fund_analysis_context(cleaned)
    system_prompt = (
        "你是专业的ETF基金分析助手。"
        "请基于基金档案清洗后的五个评分板块，判断产品定位、收益、风险、持仓暴露、规模流动性。"
        "评分要标准化、可复核，并明确说明缺失的ETF专属交易数据。只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的ETF基金摘要输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高。"
        "五个板块权重为：产品与指数定位15%，收益表现25%，风险与波动20%，持仓与行业暴露25%，规模与流动性15%。"
        "`主要依据`最多4条，`风险提示`最多3条。"
        "`汇总要点`用于最终投资结论汇总，需说明ETF跟踪对象、收益风险、持仓暴露、规模流动性和仍待补充的数据。"
        "不要超过1000字。不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_etf_fund(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_etf_fund_analysis_messages(cleaned),
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
        "module": "etf_fund",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney_fundf10"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_etf_fund_analysis_context(cleaned),
    }
