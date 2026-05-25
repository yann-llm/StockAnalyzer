"""Analyze cleaned stockcomment data with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, cached_text, chat_json, text_block

MODEL_NAME = DEFAULT_MODEL
EXPECTED_KEYS = ("综合评分", "简短结论", "主要依据", "风险提示", "汇总要点")


def build_stockcomment_analysis_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "score_features": cleaned.get("score_features") or {},
        "modules": cleaned.get("modules") or {},
        "risk_flags": cleaned.get("risk_flags") or [],
    }


def build_stockcomment_analysis_messages(cleaned: dict[str, Any]) -> list[dict[str, Any]]:
    context = build_stockcomment_analysis_context(cleaned)
    system_prompt = (
        "你是专业的A股交易与市场情绪分析助手。"
        "请围绕综合评分、主力资金、技术趋势、市场热度、舆情和财务辅助信号做判断。"
        "评分要标准化、可复核，并尽量引用输入中的原始指标值。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_static = (
        "请根据下面的千股千评清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合买入分数越高，并满足以下分数与结论的对齐区间："
        "0-39偏弱可规避，40-59中性观察，60-74稳健，75-100优秀。"
        "评分锚点规则：以`score_features.evaluation.total_score`为基线（缺失时按下方权重重算），"
        "本权重表用于在±10分内微调，不要脱离基线给出大幅偏离的分数。"
        "标准化复核口径："
        "平台综合评价30%（当前总评分、评分变化、市场/行业均值和排名分位）；"
        "资金流30%（主力净流入、超大/大/中/小单方向，多周期一致流入加分）；"
        "技术趋势25%（趋势研判、短中期信号、价格强弱，趋势走强加分，破位或弱势扣分）；"
        "市场情绪15%（关注度、活跃度、量价配合、新闻公告研报数量与情绪，热度有效放大加分，负面密集扣分）。"
        "本模块聚焦交易与市场情绪信号，不要对财务质量另行评分（财务由独立的`financial`模块负责，避免重复加权）；"
        "如输入包含财务辅助信号，仅在`主要依据`中作为佐证一笔带过，不参与本模块综合评分。"
        "若`risk_flags`出现高风险事项，应在对应维度继续扣分。"
        "数据缺失处理：若`total_score`和资金流字段均为null，应在`简短结论`末尾标注\"数据不足\"并避免给出85分以上的高分。"
        "`简短结论`控制在80字以内；`主要依据`最多3条；`风险提示`最多2条；"
        "`主要依据`和`风险提示`必须保留关键数据的原始值，例如总评分、评分变化、净流入金额、排名或舆情数量。"
        "`汇总要点`用于后续最终投资结论汇总，需围绕交易信号与市场情绪写成一段或短句列表，"
        "保留关键原始数值，不要超过1000字。"
        "字段值中可使用通用金融术语，但JSON键名必须全部使用上述中文键名。"
        "涉及金融专业术语（英文缩写或指标名）时，每次出现都必须在术语后用半角括号附中文解释，"
        "例如`MACD(指数平滑异同移动平均线)`、`KDJ(随机指标)`、`RSI(相对强弱指数)`、`BOLL(布林线)`；中文术语无需重复解释。"
    )
    user_dynamic = json.dumps(context, ensure_ascii=False, indent=2)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [cached_text(user_static), text_block(user_dynamic)]},
    ]


def analyze_stockcomment(cleaned: dict[str, Any]) -> dict[str, Any]:
    analysis = chat_json(
        build_stockcomment_analysis_messages(cleaned),
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        temperature=0.2,
        expected_keys=EXPECTED_KEYS,
    )
    return {
        "module": "stockcomment",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_stockcomment_analysis_context(cleaned),
    }
