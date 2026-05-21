"""Build the final investment conclusion from module LLM summaries."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL

MODULE_LABELS = {
    "stockcomment": "千股千评",
    "etf_product_index": "产品与指数定位",
    "etf_return_performance": "收益表现",
    "etf_risk_volatility": "风险与波动",
    "etf_holding_exposure": "持仓与行业暴露",
    "etf_scale_liquidity": "规模与流动性",
    "financial": "财务质量",
    "industry": "行业与资金",
    "valuation": "估值位置",
    "notice_risk": "公告风险",
}


def _module_label(module_name: str) -> str:
    return MODULE_LABELS.get(module_name, module_name)


def _analysis_payload(module_payload: dict[str, Any]) -> dict[str, Any]:
    analysis = module_payload.get("analysis") if isinstance(module_payload, dict) else None
    return analysis if isinstance(analysis, dict) else {}


def build_final_evaluation_context(
    stock_code: str,
    module_analyses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    modules = []
    security_type = None
    ordered_module_names = [module_name for module_name in MODULE_LABELS if module_name in module_analyses]
    ordered_module_names.extend(module_name for module_name in module_analyses if module_name not in MODULE_LABELS)
    for module_name in ordered_module_names:
        label = _module_label(module_name)
        module_payload = module_analyses.get(module_name, {})
        input_payload = module_payload.get("input") if isinstance(module_payload, dict) else None
        if security_type is None and isinstance(input_payload, dict):
            security_type = input_payload.get("security_type")
        analysis = _analysis_payload(module_payload)
        modules.append(
            {
                "module": module_name,
                "name": label,
                "status": input_payload.get("status") if isinstance(input_payload, dict) else None,
                "综合评分": analysis.get("综合评分"),
                "简短结论": analysis.get("简短结论"),
                "主要依据": analysis.get("主要依据"),
                "汇总要点": analysis.get("汇总要点"),
                "风险提示": analysis.get("风险提示"),
            }
        )
    return {
        "stock_code": stock_code,
        "security_type": security_type or "stock",
        "modules": modules,
    }


def build_final_evaluation_messages(
    stock_code: str,
    module_analyses: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    context = build_final_evaluation_context(stock_code, module_analyses)
    is_etf = context.get("security_type") == "etf"
    system_prompt = (
        "你是专业的ETF基金评估助手。"
        "请基于五个ETF子模块的大模型汇总要点，做最终投资结论。"
        "结论要平衡产品定位、收益表现、风险波动、持仓暴露、规模流动性，"
        "不得编造输入中没有的数据。只输出JSON对象，不要输出多余文本。"
        if is_etf
        else (
            "你是专业的A股投资组合评估助手。"
            "请基于各子模块的大模型汇总要点，做最终投资结论。"
            "结论要平衡收益机会、估值性价比、财务质量、行业环境、交易信号和公告风险，"
            "不得编造输入中没有的数据。只输出JSON对象，不要输出多余文本。"
        )
    )
    scoring_prompt = (
        "该证券识别为ETF。请基于五个ETF子模块评分：产品与指数定位15%，收益表现25%，"
        "风险与波动20%，持仓与行业暴露25%，规模与流动性15%。"
        "不要引用或等待股票的千股千评、财务、行业、估值、公告风险模块。"
        if is_etf
        else "请按以下标准化口径评分：财务质量25%，估值位置20%，行业与资金20%，交易/情绪信号20%，公告风险15%。"
    )
    risk_prompt = (
        "若风险波动、持仓集中或规模流动性存在明显负面事项，应降低最终评分；不要因为短期收益高就机械给高分。"
        if is_etf
        else "若公告风险或财务现金流存在重大负面事项，应降低最终评分；若估值便宜但基本面或风险不匹配，不要机械给高分。"
    )
    user_prompt = (
        "请根据下面各子模块的`汇总要点`和`主要依据`输出最终汇总评估JSON，字段必须使用中文："
        "`最终评分`、`投资结论`、`操作建议`、`核心依据`、`主要风险`、`仓位建议`。"
        "`最终评分`必须是0-100之间的数字，越适合买入分数越高。"
        f"{scoring_prompt}"
        f"{risk_prompt}"
        "`投资结论`必须严格按`最终评分`区间映射并给出一句理由："
        "75-100对应`积极关注`，60-74对应`谨慎关注`，40-59对应`中性观望`，0-39对应`暂不介入`。"
        "`操作建议`需说明买入、持有、等待回调、规避等动作条件；`仓位建议`需给出低/中/高仓位或空仓观察，并与`投资结论`保持一致。"
        "`核心依据`最多4条，`主要风险`最多3条，必须保留各子模块`主要依据`或`汇总要点`中出现的原始数据值"
        "（例如评分、同比、PE/PB、净流入金额、公告关键词等），不要凭空生成新数据。"
        "若多个子模块`status`非success或多个`综合评分`为null，应在`核心依据`中标注数据完整度受限并避免给出80分以上的高分。"
        "请把完整判断放入上述评价字段中，不要额外输出未要求的字段。"
        "字段值中可使用通用金融术语，但JSON键名必须全部使用上述中文键名。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_final_evaluation(stock_code: str, module_analyses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    response = chat_completion(
        build_final_evaluation_messages(stock_code, module_analyses),
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
        "module": "final_evaluation",
        "stock_code": stock_code,
        "source": "module_summary_points",
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_final_evaluation_context(stock_code, module_analyses),
    }
