"""Analyze cleaned ETF fund score blocks with a dedicated LLM prompt."""

from __future__ import annotations

import json
from typing import Any

from llm import DEFAULT_MODEL, chat_completion, parse_llm_json


MODEL_NAME = DEFAULT_MODEL

ETF_MODULE_LABELS = {
    "etf_product_index": "产品与指数定位",
    "etf_return_performance": "收益表现",
    "etf_risk_volatility": "风险与波动",
    "etf_holding_exposure": "持仓与行业暴露",
    "etf_scale_liquidity": "规模与流动性",
}


# 五个 ETF 子模块共用的评分尺度，与股票六模块保持一致，便于最终汇总。
_SCALE_RULES = (
    "请按下列尺度对齐评分：\n"
    "- 75-100：模块表现明显优于同类或宽基均值，无明显劣势。\n"
    "- 60-74：表现合理，可作为同类中性参考。\n"
    "- 40-59：存在明显短板（同类排名靠后、规模偏小、集中度过高等）。\n"
    "- 0-39：核心维度出现重大风险（规模逼近清盘线、跟踪指数失效、波动远超同类等）。\n"
    "`简短结论`所传达的语气必须与评分区间一致：高分对应正面表述，低分对应负面或谨慎。"
)

# `score` 是 cleaner 的启发式打分（如"正负号计数"、"前十大权重和"），过度沿用会淹没真实信号。
_BASELINE_RULE = (
    "输入中的`score`只是 cleaner 的启发式基线，可作为初始锚点；"
    "若`metrics`实际证据显示明显偏离，最终评分允许在锚点±15分内调整。"
)

# 区分 cleaner 输出的 warning / notice 等级，避免把"数据待补充"型 notice 当扣分项。
_RISK_FLAG_RULE = (
    "`risk_flags`处理规则：\n"
    "- `warning`级别：在对应维度直接扣3-8分，并写入`风险提示`。\n"
    "- `notice`级别：仅作为不确定性或数据完备性提示，写入`风险提示`但不直接扣分。\n"
    "特别地，\"ETF 专属交易数据待补充\"、\"波动测算待扩展\"等内置 notice 属于清洗版本的数据局限性提示，不应被解读为基金本身的缺陷。"
)

# 按 block_key 给出针对性评估口径。每段不超过 6 行，避免与上游通用规则冲突。
_BLOCK_GUIDANCE: dict[str, str] = {
    "product_index": (
        "本模块评估 ETF 的产品基础属性，重点看：\n"
        "- `tracking_index`（跟踪标的）与`fund_type`（基金类型）：定位是否清晰为指数/主题/行业 ETF。\n"
        "- `fund_size`（基金规模，单位亿元）：≥10亿规模较好，1-10亿可接受，<1亿存在持续运作风险。\n"
        "- `management_fee`、`custody_fee`：宽基 ETF 管理费通常≤0.50%、托管费≤0.10%，明显高于同类需扣分。\n"
        "- `manager`、`fund_manager`、`inception_date`：信息完整性影响置信度。\n"
        "评分基线：定位清晰+规模健康+费率正常 → 70-80 分；出现规模偏小、费率偏高或跟踪标的不清晰时下调。"
    ),
    "return_performance": (
        "本模块评估 ETF 的相对收益质量，重点看：\n"
        "- `stage_return_rows`（阶段涨幅表）：每行包含 ETF 自身涨幅与`同类平均`、`同类排名`等列，需以**相对同类**的位置为主，不要只看绝对涨幅。\n"
        "- `latest_nav_rows`（近期净值序列，含日涨跌幅`JZZZL`）：观察近期方向是否与阶段表现一致。\n"
        "评分基线：多周期同类排名在前 1/4 → 75-85 分；中位附近 → 60-70 分；同类后 1/4 → 40-55 分。\n"
        "当`同类平均`明显跑赢本基金时，需在`主要依据`明确指出跑输幅度。"
    ),
    "risk_volatility": (
        "本模块评估 ETF 的下行波动与抗跌能力，重点看：\n"
        "- `large_down_days_sample`（样本期内日跌幅≤-2%的天数）：天数越多说明短期波动越大。\n"
        "- `nav_rows_sample_count`（样本天数，当前清洗版本通常仅约20天）：属于短期估计，置信度有限。\n"
        "- `stage_return_rows`：可用于判断阶段性最大跌幅与同类对比。\n"
        "评分基线：样本天数充足且大跌天数<3 → 65-75 分；大跌天数≥5或样本不足时下调，并在`风险提示`明确\"波动样本仅 N 天，结论参考意义有限\"。\n"
        "主题 ETF（行业/概念）波动天然高于宽基 ETF，不应仅因高波动就扣到极低分。"
    ),
    "holding_exposure": (
        "本模块评估 ETF 的持仓结构与行业暴露，重点看：\n"
        "- `top_weight_sum_sample`（样本前十大权重合计，%）：宽基 ETF ≤30%、主题 ETF 30-70% 属正常，>75% 为高集中度。\n"
        "- `industry_allocation_rows`（最新一期行业配置）：是否单一行业占比过高（如>80%）。\n"
        "- `asset_allocation_rows`（资产配置序列）：股票仓位应稳定在 90%以上属正常 ETF，明显低于说明可能为增强型或新成立。\n"
        "对主题 ETF，高集中度不是缺点而是定位特征，应在`主要依据`明确\"主题暴露集中度 X%，与跟踪指数定位一致\"，不要因此扣分。"
    ),
    "scale_liquidity": (
        "本模块评估 ETF 的规模健康度与流动性，重点看：\n"
        "- `fund_size`（基金规模，亿元）：≥10亿→流动性较好；2-10亿→中等；0.5-2亿→需谨慎；<0.5亿→清盘风险显著。\n"
        "- `scale_change_rows`（规模变动表，含期末份额、净资产、变动率）：注意规模是否在持续萎缩。\n"
        "评分基线：规模≥10亿且份额稳定 → 75-85 分；规模显著萎缩或<1亿 → 下调至 40-55 分。\n"
        "当前清洗版本尚未覆盖场内成交额、买卖盘深度、折溢价率与跟踪误差，对应的 notice 仅作数据局限性提示，不应作为基金本身的缺陷扣分。"
    ),
}


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
        "你是专业的ETF基金评估助手。"
        "请基于五个评分板块的清洗数据，综合判断ETF的产品定位、收益、风险、持仓暴露与规模流动性。"
        "当某些板块数据缺失或样本不足时，应明确降低置信度而不是机械沿用`overall_score`。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的ETF档案摘要输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合配置该ETF分数越高。\n\n"
        "五个板块权重已在`block_weights`中：产品与指数定位15%，收益表现25%，风险与波动20%，"
        "持仓与行业暴露25%，规模与流动性15%。"
        "评分锚点：以输入的`overall_score`为基线，根据五个`blocks`的实际证据在±10分内微调；"
        "若任一板块出现 warning 级风险或证据明显偏离 cleaner 打分，可超出±10范围。\n\n"
        f"{_SCALE_RULES}\n\n"
        f"{_RISK_FLAG_RULE}\n\n"
        "`简短结论`控制在100字以内；`主要依据`最多4条；`风险提示`最多3条。"
        "`主要依据`和`风险提示`必须保留各板块的关键原始数值（基金规模、跟踪指数、前十大集中度、"
        "大跌样本天数、各阶段同类排名等）。"
        "`汇总要点`用于最终投资结论汇总，需说明ETF跟踪对象、收益风险特征、持仓暴露、规模流动性"
        "以及当前清洗版本仍待补充的场内交易数据，不要超过1000字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名（如`top_weight_sum_sample`、`JZZZL`），"
        "可以保留通用ETF术语（跟踪指数、规模、行业暴露、折溢价等）。"
        "涉及金融专业术语（英文缩写或指标名）时，每次出现都必须在术语后用半角括号附中文解释，"
        "例如`ETF(交易型开放式指数基金)`、`IOPV(基金净值估算)`、`AUM(资产管理规模)`、`PE_TTM(滚动市盈率)`；中文术语无需重复解释。\n\n"
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
    analysis = parse_llm_json(content)
    return {
        "module": "etf_fund",
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney_fundf10"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_etf_fund_analysis_context(cleaned),
    }


def build_etf_fund_module_context(cleaned: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_code": cleaned.get("stock_code"),
        "module": cleaned.get("module"),
        "source": cleaned.get("source", "eastmoney_fundf10"),
        "security_type": cleaned.get("security_type", "etf"),
        "block_key": cleaned.get("block_key"),
        "name": cleaned.get("name") or ETF_MODULE_LABELS.get(str(cleaned.get("module"))),
        "weight": cleaned.get("weight"),
        "score": cleaned.get("score"),
        "source_pages": cleaned.get("source_pages") or [],
        "metrics": cleaned.get("metrics") or {},
        "notes": cleaned.get("notes") or [],
        "risk_flags": cleaned.get("risk_flags") or [],
    }


def build_etf_fund_module_messages(cleaned: dict[str, Any]) -> list[dict[str, str]]:
    context = build_etf_fund_module_context(cleaned)
    module_name = context.get("name") or "ETF子模块"
    block_key = str(context.get("block_key") or "")
    block_guidance = _BLOCK_GUIDANCE.get(block_key, "")
    system_prompt = (
        "你是专业的ETF基金分析助手，每次只评估一个评分子模块。"
        f"本次只分析`{module_name}`这一板块，不要扩展到其他板块。"
        "请基于清洗后的数值、比率与样本量做判断，结合ETF的产品定位、收益、风险、持仓暴露与规模流动性逻辑。"
        "当数据缺失或样本不足时，应明确降低置信度，而不是给中性高分。"
        "只输出JSON对象，不要输出多余文本。"
    )
    user_prompt = (
        "请根据下面的ETF子模块清洗数据输出JSON，字段必须使用中文："
        "`综合评分`、`简短结论`、`主要依据`、`风险提示`、`汇总要点`。"
        "`综合评分`必须是0-100之间的数字，越适合配置该ETF分数越高。\n\n"
        f"{_BASELINE_RULE}\n\n"
        f"{block_guidance}\n\n"
        f"{_SCALE_RULES}\n\n"
        f"{_RISK_FLAG_RULE}\n\n"
        "`简短结论`控制在80字以内；`主要依据`最多4条；`风险提示`最多3条。"
        "`主要依据`和`风险提示`必须保留输入中的原始数值（基金规模、费率、同类排名、前十大权重合计、"
        "大跌样本天数等），不要泛泛而谈。"
        "`汇总要点`用于最终ETF投资结论汇总，需围绕本子模块在ETF投资决策中的角色写成短句列表，"
        "保留关键原始数值，不要超过700字。"
        "不要使用英文字段名，不要输出用户难懂的技术字段名（如`top_weight_sum_sample`、`JZZZL`），"
        "可以保留通用ETF术语（跟踪指数、规模、行业暴露、折溢价等）。"
        "涉及金融专业术语（英文缩写或指标名）时，每次出现都必须在术语后用半角括号附中文解释，"
        "例如`ETF(交易型开放式指数基金)`、`IOPV(基金净值估算)`、`AUM(资产管理规模)`、`PE_TTM(滚动市盈率)`；中文术语无需重复解释。\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def analyze_etf_fund_module(cleaned: dict[str, Any]) -> dict[str, Any]:
    response = chat_completion(
        build_etf_fund_module_messages(cleaned),
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    analysis = parse_llm_json(content)
    return {
        "module": cleaned.get("module"),
        "stock_code": cleaned.get("stock_code"),
        "source": cleaned.get("source", "eastmoney_fundf10"),
        "model": MODEL_NAME,
        "analysis": analysis,
        "input": build_etf_fund_module_context(cleaned),
    }
