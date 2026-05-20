"""Build the final investment conclusion from module LLM summaries."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion

MODEL_NAME = DEFAULT_MODEL

MODULE_LABELS = {
    "stockcomment": "千股千评",
    "financial": "财务质量",
    "industry": "行业与资金",
    "valuation": "估值位置",
    "notice_risk": "公告风险",
}


def _analysis_payload(module_payload: dict[str, Any]) -> dict[str, Any]:
    analysis = module_payload.get("analysis") if isinstance(module_payload, dict) else None
    return analysis if isinstance(analysis, dict) else {}


def build_final_evaluation_context(
    stock_code: str,
    module_analyses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    modules = []
    for module_name, label in MODULE_LABELS.items():
        analysis = _analysis_payload(module_analyses.get(module_name, {}))
        modules.append(
            {
                "module": module_name,
                "name": label,
                "综合评分": analysis.get("综合评分"),
                "简短结论": analysis.get("简短结论"),
                "汇总要点": analysis.get("汇总要点"),
                "风险提示": analysis.get("风险提示"),
            }
        )
    return {
        "stock_code": stock_code,
        "modules": modules,
    }


def build_final_evaluation_messages(
    stock_code: str,
    module_analyses: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    context = build_final_evaluation_context(stock_code, module_analyses)
    system_prompt = (
        "你是专业的A股投资组合评估助手。"
        "请基于五个子模块的大模型汇总要点，做最终投资结论。"
        "结论要平衡收益机会、估值性价比、财务质量、行业环境、交易信号和公告风险，"
        "不得编造输入中没有的数据。只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面五个子模块的`汇总要点`输出最终汇总评估JSON，字段必须使用中文："
        "`最终评分`、`投资结论`、`操作建议`、`核心依据`、`主要风险`、`仓位建议`。"
        "`最终评分`必须是0-100之间的数字，越适合买入分数越高。"
        "请按以下标准化口径评分：财务质量25%，估值位置20%，行业与资金20%，交易/情绪信号20%，公告风险15%。"
        "若公告风险或财务现金流存在重大负面事项，应降低最终评分；若估值便宜但基本面或风险不匹配，不要机械给高分。"
        "`投资结论`从`积极关注`、`谨慎关注`、`中性观望`、`暂不介入`中选择一个，并给出一句理由。"
        "`操作建议`需说明买入、持有、等待回调、规避等动作条件；`仓位建议`需给出低/中/高仓位或空仓观察。"
        "`核心依据`最多4条，`主要风险`最多3条，必须保留各子模块`汇总要点`中的关键原始数据值。"
        "请把完整判断放入上述评价字段中，不要额外输出未要求的字段。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名。\n\n"
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
