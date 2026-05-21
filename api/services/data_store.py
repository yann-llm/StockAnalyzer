"""Read local Eastmoney cache files and build UI-friendly summaries."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
EXPECTED_MODULES = ("financial", "industry", "notice_risk", "stockcomment", "valuation")
ETF_MODULES = (
    "etf_product_index",
    "etf_return_performance",
    "etf_risk_volatility",
    "etf_holding_exposure",
    "etf_scale_liquidity",
)
ALL_MODULES = tuple(dict.fromkeys((*EXPECTED_MODULES, *ETF_MODULES)))
ETF_MODULE_LABELS = {
    "etf_product_index": "产品与指数定位",
    "etf_return_performance": "收益表现",
    "etf_risk_volatility": "风险与波动",
    "etf_holding_exposure": "持仓与行业暴露",
    "etf_scale_liquidity": "规模与流动性",
}


class DataStoreError(Exception):
    """Base error for local data access."""


class StockNotFoundError(DataStoreError):
    """Raised when no local cache exists for a stock code."""


class ModuleDataError(DataStoreError):
    """Raised when a module points to unreadable data."""


def normalize_stock_code(stock_code: str) -> str:
    code = stock_code.strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("stock_code must be a 6 digit A-share code")
    return code


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModuleDataError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ModuleDataError(f"invalid json: {path}") from exc


def stock_dir(stock_code: str) -> Path:
    return DATA_DIR / normalize_stock_code(stock_code)


def manifest_path(stock_code: str) -> Path:
    return stock_dir(stock_code) / "cache_manifest.json"


def list_stock_codes() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(
        child.name
        for child in DATA_DIR.iterdir()
        if child.is_dir() and re.fullmatch(r"\d{6}", child.name) and (child / "cache_manifest.json").exists()
    )


def load_manifest(stock_code: str) -> dict[str, Any]:
    path = manifest_path(stock_code)
    if not path.exists():
        raise StockNotFoundError(f"no local cache for stock {normalize_stock_code(stock_code)}")
    return read_json(path)


def load_cleaned_module(stock_code: str, module_name: str) -> dict[str, Any]:
    code = normalize_stock_code(stock_code)
    manifest = load_manifest(code)
    info = manifest.get("modules", {}).get(module_name)
    if not isinstance(info, dict):
        raise ModuleDataError(f"module not recorded in manifest: {module_name}")
    cleaned_file = info.get("cleaned_file")
    if not cleaned_file:
        raise ModuleDataError(f"module has no cleaned file: {module_name}")
    return read_json(stock_dir(code) / cleaned_file)


def load_analysis_module(stock_code: str, module_name: str, modules: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    info = modules.get(module_name, {})
    analysis_file = info.get("analysis_file")
    if not analysis_file:
        return None
    try:
        return read_json(stock_dir(stock_code) / analysis_file)
    except DataStoreError:
        return None


def load_final_evaluation(stock_code: str, manifest: dict[str, Any]) -> dict[str, Any] | None:
    info = manifest.get("final_evaluation")
    if not isinstance(info, dict) or info.get("analysis_status") != "success":
        return None
    analysis_file = info.get("analysis_file")
    if not analysis_file:
        return None
    try:
        return read_json(stock_dir(stock_code) / analysis_file)
    except DataStoreError:
        return None


def build_stocks_index() -> list[dict[str, Any]]:
    return [build_stock_index_item(code) for code in list_stock_codes()]


def build_stock_index_item(stock_code: str) -> dict[str, Any]:
    manifest = load_manifest(stock_code)
    modules = manifest.get("modules", {})
    expected_modules = expected_modules_for_manifest(manifest)
    success_count = sum(1 for info in modules.values() if isinstance(info, dict) and info.get("status") == "success")
    cleaned = load_successful_modules(normalize_stock_code(stock_code), build_module_statuses(stock_code, manifest))
    item = {
        "stock_code": normalize_stock_code(stock_code),
        "stock_name": resolve_display_name(normalize_stock_code(stock_code), cleaned),
        "market_code": market_code(stock_code),
        "generated_at": manifest.get("generated_at"),
        "expires_at": manifest.get("expires_at"),
        "modules_total": len(expected_modules),
        "modules_success": success_count,
    }
    try:
        valuation = load_cleaned_module(stock_code, "valuation")
        item["stock_name"] = dig(valuation, "data", "latest", "stock_name") or item["stock_name"]
        item["industry_name"] = dig(valuation, "data", "latest", "board_name")
    except DataStoreError:
        pass
    return item


def build_stock_summary(stock_code: str) -> dict[str, Any]:
    code = normalize_stock_code(stock_code)
    manifest = load_manifest(code)
    modules = build_module_statuses(code, manifest)
    cleaned = load_successful_modules(code, modules)
    analysis = load_successful_analysis(code, modules)
    final_evaluation = load_final_evaluation(code, manifest)

    valuation_latest = dig(cleaned.get("valuation"), "data", "latest") or {}
    industry_data = dig(cleaned.get("industry"), "data") or {}
    stock_name = resolve_display_name(code, cleaned)
    industry_name = (
        valuation_latest.get("board_name")
        or industry_data.get("industry_name")
        or dig(industry_data, "stock_industry_mapping", "industry_name")
    )

    return {
        "stock_code": code,
        "stock_name": stock_name,
        "market_code": market_code(code),
        "generated_at": format_datetime(manifest.get("generated_at")),
        "expires_at": format_datetime(manifest.get("expires_at")),
        "cache_hit": all(info.get("status") == "success" for info in modules.values()),
        "data_source": f"data/{code}/cleaned/",
        "modules": modules,
        "final_evaluation": build_final_evaluation_summary(final_evaluation, manifest),
        "metrics": build_metrics(cleaned),
        "ability_scores": build_ability_scores(cleaned, analysis),
        "risk_flags": collect_risk_flags(cleaned),
        "sections": build_sections(cleaned, analysis, final_evaluation, stock_name, industry_name),
    }


def build_module_statuses(stock_code: str, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    manifest_modules = manifest.get("modules", {})
    for module_name in (*expected_modules_for_manifest(manifest), "final_evaluation"):
        if module_name == "final_evaluation":
            info = manifest.get("final_evaluation", {})
            analysis_file = info.get("analysis_file") if isinstance(info, dict) else None
            file_exists = bool(analysis_file and (stock_dir(stock_code) / analysis_file).exists())
            analysis_status = info.get("analysis_status") if isinstance(info, dict) else None
            status = "success" if analysis_status == "success" else analysis_status or "missing"
            if status == "success" and not file_exists:
                status = "missing_file"
            statuses[module_name] = {
                "status": status,
                "cleaned_file": None,
                "analysis_status": analysis_status,
                "analysis_file": analysis_file,
                "file_exists": file_exists,
                "error": info.get("analysis_error") if isinstance(info, dict) else None,
            }
            continue
        info = manifest_modules.get(module_name, {})
        cleaned_file = info.get("cleaned_file") if isinstance(info, dict) else None
        file_exists = bool(cleaned_file and (stock_dir(stock_code) / cleaned_file).exists())
        status = info.get("status", "missing") if isinstance(info, dict) else "missing"
        if status == "success" and not file_exists:
            status = "missing_file"
        statuses[module_name] = {
            "status": status,
            "cleaned_file": cleaned_file,
            "analysis_status": info.get("analysis_status") if isinstance(info, dict) else None,
            "analysis_file": info.get("analysis_file") if isinstance(info, dict) else None,
            "file_exists": file_exists,
            "error": info.get("error") if isinstance(info, dict) else None,
        }
    return statuses


def expected_modules_for_manifest(manifest: dict[str, Any]) -> tuple[str, ...]:
    profile = manifest.get("security_profile") if isinstance(manifest, dict) else {}
    if isinstance(profile, dict) and profile.get("security_type") == "etf":
        return ETF_MODULES
    manifest_modules = manifest.get("modules", {}) if isinstance(manifest, dict) else {}
    if any(module_name in manifest_modules for module_name in ETF_MODULES) or "etf_fund" in manifest_modules:
        return ETF_MODULES
    return EXPECTED_MODULES


def load_successful_modules(stock_code: str, modules: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cleaned: dict[str, dict[str, Any]] = {}
    for module_name, info in modules.items():
        if info.get("status") != "success":
            continue
        try:
            cleaned[module_name] = load_cleaned_module(stock_code, module_name)
        except DataStoreError:
            continue
    return cleaned


def load_successful_analysis(stock_code: str, modules: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    analysis: dict[str, dict[str, Any]] = {}
    for module_name, info in modules.items():
        if info.get("analysis_status") != "success":
            continue
        payload = load_analysis_module(stock_code, module_name, modules)
        if payload is not None:
            analysis[module_name] = payload
    return analysis


def build_metrics(cleaned: dict[str, dict[str, Any]]) -> dict[str, Any]:
    financial_latest = dig(cleaned.get("financial"), "data", "latest") or {}
    valuation_latest = dig(cleaned.get("valuation"), "data", "latest") or {}
    industry_data = dig(cleaned.get("industry"), "data") or {}
    stockcomment_data = dig(cleaned.get("stockcomment"), "data") or {}
    return {
        "revenue": financial_latest.get("revenue"),
        "revenue_yoy": financial_latest.get("revenue_yoy"),
        "net_profit": financial_latest.get("net_profit"),
        "net_profit_yoy": financial_latest.get("net_profit_yoy"),
        "roe": financial_latest.get("roe"),
        "operating_cash_flow": financial_latest.get("operating_cash_flow"),
        "pe_ttm": valuation_latest.get("pe_ttm"),
        "pb_mrq": valuation_latest.get("pb_mrq"),
        "peg": valuation_latest.get("peg"),
        "industry_name": valuation_latest.get("board_name") or industry_data.get("industry_name"),
        "industry_score": dig(industry_data, "score_summary", "overall_score"),
        "stock_score": dig(stockcomment_data, "score_features", "evaluation", "total_score"),
    }


def build_ability_scores(
    cleaned: dict[str, dict[str, Any]],
    analysis: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if has_etf_modules(cleaned, analysis):
        dimensions = [
            (module_name, label, dig(cleaned.get(module_name), "data", "score"))
            for module_name, label in ETF_MODULE_LABELS.items()
        ]
    else:
        dimensions = [
            ("stockcomment", "千股千评", dig(cleaned.get("stockcomment"), "data", "score_features", "evaluation", "total_score")),
            ("financial", "财务质量", None),
            ("industry", "行业与资金", dig(cleaned.get("industry"), "data", "score_summary", "overall_score")),
            ("valuation", "估值位置", None),
            ("notice_risk", "风险安全", None),
        ]
    scores: list[dict[str, Any]] = []
    for key, label, fallback in dimensions:
        score = clamp_score(extract_analysis_score(analysis.get(key)) if analysis.get(key) else fallback)
        scores.append({"key": key, "label": label, "score": score})
    return scores


def extract_analysis_score(payload: dict[str, Any] | None) -> Any:
    analysis_payload = payload.get("analysis") if isinstance(payload, dict) else None
    if not isinstance(analysis_payload, dict):
        return None
    return analysis_payload.get("综合评分")


def clamp_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if not match:
            return None
        value = match.group(0)
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def build_sections(
    cleaned: dict[str, dict[str, Any]],
    analysis: dict[str, dict[str, Any]],
    final_evaluation: dict[str, Any] | None,
    stock_name: str,
    industry_name: str | None,
) -> list[dict[str, Any]]:
    sections = [
        {
            "key": "thesis",
            "title": "投资结论",
            "body": build_final_evaluation_text(final_evaluation) or build_thesis(cleaned, stock_name, industry_name),
            "items": build_final_evaluation_items(final_evaluation) or [],
        },
    ]
    if has_etf_modules(cleaned, analysis):
        for module_name, label in ETF_MODULE_LABELS.items():
            if not cleaned.get(module_name) and not analysis.get(module_name):
                continue
            fallback = build_etf_fund_section(cleaned.get(module_name))
            sections.append(
                {
                    "key": module_name,
                    "title": label,
                    "body": build_llm_section_text(analysis.get(module_name)) or fallback["body"],
                    "items": build_llm_section_items(analysis.get(module_name)) or fallback["items"],
                }
            )
    else:
        sections.extend(
            [
        {
            "key": "stockcomment",
            "title": "千股千评",
            "body": build_llm_section_text(analysis.get("stockcomment")) or build_stockcomment_section(cleaned.get("stockcomment"))["body"],
            "items": build_llm_section_items(analysis.get("stockcomment")) or build_stockcomment_section(cleaned.get("stockcomment"))["items"],
        },
        {
            "key": "financial",
            "title": "财务质量",
            "body": build_llm_section_text(analysis.get("financial")) or build_financial_section(cleaned.get("financial"))["body"],
            "items": build_llm_section_items(analysis.get("financial")) or build_financial_section(cleaned.get("financial"))["items"],
        },
        {
            "key": "industry",
            "title": "行业与资金",
            "body": build_llm_section_text(analysis.get("industry")) or build_industry_section(cleaned.get("industry"), cleaned.get("stockcomment"))["body"],
            "items": build_llm_section_items(analysis.get("industry")) or build_industry_section(cleaned.get("industry"), cleaned.get("stockcomment"))["items"],
        },
        {
            "key": "valuation",
            "title": "估值位置",
            "body": build_llm_section_text(analysis.get("valuation")) or build_valuation_section(cleaned.get("valuation"))["body"],
            "items": build_llm_section_items(analysis.get("valuation")) or build_valuation_section(cleaned.get("valuation"))["items"],
        },
            ]
        )
    if not has_etf_modules(cleaned, analysis):
        sections.append(
            {
                "key": "risk",
                "title": "主要风险",
                "body": build_llm_section_text(analysis.get("notice_risk")) or build_risk_section(cleaned)["body"],
                "items": build_llm_section_items(analysis.get("notice_risk")) or build_risk_section(cleaned)["items"],
            }
        )
    return sections


def has_etf_modules(cleaned: dict[str, dict[str, Any]], analysis: dict[str, dict[str, Any]]) -> bool:
    return any(module_name in cleaned or module_name in analysis for module_name in ETF_MODULES) or "etf_fund" in cleaned or "etf_fund" in analysis


def resolve_display_name(stock_code: str, cleaned: dict[str, dict[str, Any]]) -> str:
    for module_name in ("etf_product_index", "etf_scale_liquidity", "etf_fund"):
        legacy_name = extract_etf_name_from_pages(stock_code, dig(cleaned.get(module_name), "data", "pages"))
        if legacy_name:
            return legacy_name
        fund_name = dig(cleaned.get(module_name), "data", "metrics", "fund_name")
        if fund_name:
            return str(fund_name)

    valuation_latest = dig(cleaned.get("valuation"), "data", "latest") or {}
    industry_data = dig(cleaned.get("industry"), "data") or {}
    return (
        valuation_latest.get("stock_name")
        or dig(industry_data, "stock_industry_mapping", "stock", "name")
        or stock_code
    )


def extract_etf_name_from_pages(stock_code: str, pages: Any) -> str | None:
    if not isinstance(pages, dict):
        return None
    code = normalize_stock_code(stock_code)
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        text = str(page.get("text_sample") or "")
        match = re.search(rf"([\u4e00-\u9fa5A-Za-z0-9]+)\({re.escape(code)}\)", text)
        if match:
            return match.group(1)
        match = re.search(rf"([\u4e00-\u9fa5A-Za-z0-9]+)\s*（{re.escape(code)}）", text)
        if match:
            return match.group(1)
        match = re.search(r"基金简称\s+([\u4e00-\u9fa5A-Za-z0-9]+)", text)
        if match:
            return match.group(1)
    return None


def build_llm_section_text(payload: dict[str, Any] | None) -> str | None:
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    if not isinstance(analysis, dict):
        return None
    items = build_llm_section_items(payload)
    if not items:
        return None
    return "；".join(item["value"] for item in items if item.get("value")) + "。"


def build_llm_section_items(payload: dict[str, Any] | None) -> list[dict[str, str]] | None:
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    if not isinstance(analysis, dict):
        return None
    items: list[dict[str, str]] = []
    conclusion = stringify_analysis_value(analysis.get("简短结论"))
    score = format_score(analysis.get("综合评分"))
    evidence = stringify_analysis_value(analysis.get("主要依据"))
    risk = stringify_analysis_value(analysis.get("风险提示"))
    if conclusion:
        items.append({"label": "结论", "value": conclusion})
    if score:
        items.append({"label": "综合评分", "value": score})
    if evidence:
        items.append({"label": "判断依据", "value": evidence})
    if risk:
        items.append({"label": "风险提示", "value": risk})
    return items or None


def build_final_evaluation_summary(payload: dict[str, Any] | None, manifest: dict[str, Any]) -> dict[str, Any] | None:
    info = manifest.get("final_evaluation")
    if not isinstance(info, dict):
        return None
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    return {
        "analysis_status": info.get("analysis_status"),
        "analysis_file": info.get("analysis_file"),
        "analysis_error": info.get("analysis_error"),
        "module_count": info.get("module_count"),
        "final_score": analysis.get("最终评分") if isinstance(analysis, dict) else None,
        "investment_conclusion": analysis.get("投资结论") if isinstance(analysis, dict) else None,
    }


def build_final_evaluation_text(payload: dict[str, Any] | None) -> str | None:
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    if not isinstance(analysis, dict):
        return None
    conclusion = stringify_analysis_value(analysis.get("投资结论"))
    advice = stringify_analysis_value(analysis.get("操作建议"))
    evidence = stringify_analysis_value(analysis.get("核心依据"))
    risk = stringify_analysis_value(analysis.get("主要风险"))
    position = stringify_analysis_value(analysis.get("仓位建议"))
    return "；".join(part for part in [conclusion, advice, evidence, risk, position] if part) or None


def build_final_evaluation_items(payload: dict[str, Any] | None) -> list[dict[str, str]] | None:
    analysis = payload.get("analysis") if isinstance(payload, dict) else None
    if not isinstance(analysis, dict):
        return None
    fields = [
        ("最终评分", format_score(analysis.get("最终评分"))),
        ("投资结论", stringify_analysis_value(analysis.get("投资结论"))),
        ("仓位建议", stringify_analysis_value(analysis.get("仓位建议"))),
        ("操作建议", stringify_analysis_value(analysis.get("操作建议"))),
        ("核心依据", stringify_analysis_value(analysis.get("核心依据"))),
        ("主要风险", stringify_analysis_value(analysis.get("主要风险"))),
    ]
    items = [{"label": label, "value": value} for label, value in fields if value]
    return items or None


def format_score(value: Any) -> str:
    if value is None:
        return ""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return f"综合评分 {value}"
    return f"{score:.1f}".rstrip("0").rstrip(".") + " 分"


def stringify_analysis_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return simplify_display_numbers(value.strip())
    if isinstance(value, list):
        return "；".join(item_text for item in value if (item_text := stringify_analysis_value(item)))
    if isinstance(value, dict):
        return "；".join(
            f"{key}: {stringify_analysis_value(item)}"
            for key, item in value.items()
            if stringify_analysis_value(item)
        )
    return simplify_display_numbers(str(value))


def simplify_display_numbers(text: str) -> str:
    text = re.sub(r"(?<![\d.])(-?\d+(?:\.\d+)?)元", _format_yuan_match, text)
    text = re.sub(r"(?<![\d.])(-?\d+\.\d+)%", lambda match: f"{format_number(float(match.group(1)))}%", text)
    return re.sub(r"(?<![\d.])(-?\d+\.\d{3,})(?![\d.])", lambda match: format_number(float(match.group(1))), text)


def _format_yuan_match(match: re.Match[str]) -> str:
    value = float(match.group(1))
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{format_number(value / 100_000_000)}亿元"
    if abs_value >= 10_000:
        return f"{format_number(value / 10_000)}万元"
    return f"{format_number(value)}元"


def build_thesis(cleaned: dict[str, dict[str, Any]], stock_name: str, industry_name: str | None) -> str:
    metrics = build_metrics(cleaned)
    score_parts = []
    if metrics.get("stock_score") is not None:
        score_parts.append(f"个股综合评分 {format_number(metrics['stock_score'])}")
    if metrics.get("industry_score") is not None:
        score_parts.append(f"行业景气评分 {format_number(metrics['industry_score'])}")
    valuation_text = ""
    if metrics.get("pe_ttm") is not None and metrics.get("pb_mrq") is not None:
        valuation_text = f"当前 PE(TTM) {format_number(metrics['pe_ttm'])}、PB {format_number(metrics['pb_mrq'])}。"
    industry_text = f"所属行业为{industry_name}，" if industry_name else ""
    score_text = "，".join(score_parts) or "本地模块已完成数据聚合"
    return f"{stock_name}：{industry_text}{score_text}。{valuation_text}建议结合财务增速、资金流和公告风险综合判断。"


def build_financial_section(financial: dict[str, Any] | None) -> dict[str, Any]:
    latest = dig(financial, "data", "latest") or {}
    if not latest:
        return {"body": "财务模块暂无可用摘要。", "items": []}
    evidence = "；".join(
        [
            f"营业收入 {format_amount(latest.get('revenue'))}，同比 {format_percent(latest.get('revenue_yoy'))}",
            f"归母净利润 {format_amount(latest.get('net_profit'))}，同比 {format_percent(latest.get('net_profit_yoy'))}",
            f"ROE {format_percent(latest.get('roe'))}",
            f"经营现金流 {format_amount(latest.get('operating_cash_flow'))}",
        ]
    )
    items = [
        {"label": "结论", "value": "财务质量可结合收入、利润、现金流综合判断。"},
        {"label": "判断依据", "value": evidence},
    ]
    flags = dig(financial, "data", "risk_flags") or []
    if flags:
        items.append({"label": "风险提示", "value": "；".join(flag.get("title", "") for flag in flags[:3] if isinstance(flag, dict))})
    return {"body": "；".join(item["value"] for item in items if item.get("value")) + "。", "items": items}


def build_industry_section(industry: dict[str, Any] | None, stockcomment: dict[str, Any] | None) -> dict[str, Any]:
    data = dig(industry, "data") or {}
    stockcomment_data = dig(stockcomment, "data") or {}
    industry_name = data.get("industry_name") or dig(data, "stock_industry_mapping", "industry_name")
    score = dig(data, "score_summary", "overall_score")
    today_flow = dig(data, "capital_flow", "periods", "today", "main_net_inflow")
    five_day_flow = dig(data, "capital_flow", "periods", "5d", "main_net_inflow")
    trend_comment = dig(stockcomment_data, "score_features", "trend", "trend_comment")
    conclusion = ""
    evidence_parts = []
    risk_parts = []
    if industry_name:
        conclusion = f"{industry_name}行业景气评分 {format_number(score) if score is not None else '暂无'}。"
    if today_flow is not None:
        evidence_parts.append(f"今日行业主力净流入 {format_amount(today_flow)}")
    if five_day_flow is not None:
        evidence_parts.append(f"5 日行业主力净流入 {format_amount(five_day_flow)}")
    if trend_comment:
        risk_parts.append(str(trend_comment))
    items = []
    if conclusion:
        items.append({"label": "结论", "value": conclusion})
    if score is not None:
        items.append({"label": "综合评分", "value": f"{format_number(score)} 分"})
    if evidence_parts:
        items.append({"label": "判断依据", "value": "；".join(evidence_parts)})
    if risk_parts:
        items.append({"label": "风险提示", "value": "；".join(risk_parts)})
    return {"body": "；".join(item["value"] for item in items if item.get("value")) + "。" if items else "行业与资金模块暂无可用摘要。", "items": items}


def build_stockcomment_section(stockcomment: dict[str, Any] | None) -> dict[str, Any]:
    data = dig(stockcomment, "data") or {}
    features = data.get("score_features") or {}
    overall = features.get("overall") or {}
    capital = features.get("capital_flow") or {}
    technical = features.get("technical") or {}
    sentiment = features.get("sentiment") or {}
    if not features:
        return {"body": "千股千评模块暂无可用摘要。", "items": []}
    conclusion = str(technical.get("trend_comment") or "")
    evidence_parts = []
    risk_parts = []
    if capital.get("capital_flows") is not None:
        evidence_parts.append(f"个股资金流 {format_amount(capital.get('capital_flows'))}")
    if capital.get("capital_flows_5days") is not None:
        evidence_parts.append(f"5 日资金流 {format_amount(capital.get('capital_flows_5days'))}")
    if sentiment.get("market_focus") is not None:
        evidence_parts.append(f"市场关注度 {format_number(sentiment.get('market_focus'))}")
    flags = data.get("risk_flags") or []
    if flags:
        risk_parts.append("；".join(flag.get("title", "") for flag in flags[:2] if isinstance(flag, dict)))
    items = []
    if conclusion:
        items.append({"label": "结论", "value": conclusion})
    if overall.get("total_score") is not None:
        items.append({"label": "综合评分", "value": format_number(overall.get("total_score")) + " 分"})
    if evidence_parts:
        items.append({"label": "判断依据", "value": "；".join(evidence_parts)})
    if risk_parts:
        items.append({"label": "风险提示", "value": "；".join(risk_parts)})
    return {"body": "；".join(item["value"] for item in items if item.get("value")) + "。" if items else "千股千评模块暂无可用摘要。", "items": items}


def build_valuation_section(valuation: dict[str, Any] | None) -> dict[str, Any]:
    data = dig(valuation, "data") or {}
    latest = data.get("latest") or {}
    rank = data.get("industry_rank") or {}
    percentiles = data.get("industry_percentiles") or {}
    if not latest:
        return {"body": "估值模块暂无可用摘要。", "items": []}
    evidence_parts = [
        f"PE(TTM) {format_number(latest.get('pe_ttm'))}",
        f"PB(MRQ) {format_number(latest.get('pb_mrq'))}",
        f"PEG {format_number(latest.get('peg'))}",
    ]
    if rank.get("rank_by_pe_ttm") and rank.get("industry_count"):
        evidence_parts.append(f"PE 行业排名 {rank['rank_by_pe_ttm']}/{rank['industry_count']}")
    pe_pct = dig(percentiles, "pe_ttm", "percentile")
    pb_pct = dig(percentiles, "pb_mrq", "percentile")
    if pe_pct is not None or pb_pct is not None:
        evidence_parts.append(f"PE 分位 {format_percent(pe_pct)}，PB 分位 {format_percent(pb_pct)}")
    items = [
        {"label": "结论", "value": "估值可用，但需要结合盈利和现金流判断。"},
        {"label": "判断依据", "value": "；".join(evidence_parts)},
    ]
    return {"body": "；".join(item["value"] for item in items if item.get("value")) + "。", "items": items}


def build_etf_fund_section(etf_fund: dict[str, Any] | None) -> dict[str, Any]:
    data = dig(etf_fund, "data") or {}
    if data.get("block_key") or data.get("metrics"):
        items: list[dict[str, str]] = []
        if data.get("score") is not None:
            items.append({"label": "综合评分", "value": f"{format_number(data.get('score'))} 分"})
        notes = data.get("notes") or []
        if notes:
            items.append({"label": "结论", "value": str(notes[0])})
        metrics = data.get("metrics") or {}
        metric_text = summarize_etf_metrics(metrics)
        if metric_text:
            items.append({"label": "判断依据", "value": metric_text})
        flags = data.get("risk_flags") or []
        if flags:
            items.append({"label": "风险提示", "value": "；".join(flag.get("title", "") for flag in flags[:3] if isinstance(flag, dict))})
        return {
            "body": "；".join(item["value"] for item in items if item.get("value")) + "。" if items else "ETF子模块暂无可用摘要。",
            "items": items,
        }

    blocks = data.get("blocks") or {}
    if not blocks:
        return {"body": "ETF基金档案模块暂无可用摘要。", "items": []}
    items: list[dict[str, str]] = []
    if data.get("overall_score") is not None:
        items.append({"label": "综合评分", "value": f"{format_number(data.get('overall_score'))} 分"})
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        name = block.get("name")
        score = block.get("score")
        notes = block.get("notes") or []
        value_parts = []
        if score is not None:
            value_parts.append(f"{format_number(score)} 分")
        if notes:
            value_parts.append(str(notes[0]))
        if name and value_parts:
            items.append({"label": str(name), "value": "；".join(value_parts)})
    return {
        "body": "；".join(item["value"] for item in items if item.get("value")) + "。" if items else "ETF基金档案模块暂无可用摘要。",
        "items": items,
    }


def summarize_etf_metrics(metrics: dict[str, Any]) -> str:
    parts: list[str] = []
    if metrics.get("tracking_index"):
        parts.append(f"跟踪标的 {metrics.get('tracking_index')}")
    if metrics.get("fund_type"):
        parts.append(f"基金类型 {metrics.get('fund_type')}")
    if metrics.get("fund_size"):
        parts.append(f"规模 {metrics.get('fund_size')}")
    stage_rows = metrics.get("stage_return_rows") or []
    if len(stage_rows) > 1:
        parts.append("阶段涨幅 " + " / ".join(" ".join(row[:2]) for row in stage_rows[1:4] if isinstance(row, list)))
    nav_rows = metrics.get("latest_nav_rows") or []
    if nav_rows and isinstance(nav_rows[0], dict):
        first = nav_rows[0]
        parts.append(f"最新净值 {first.get('DWJZ')}，日增长率 {first.get('JZZZL')}%")
    holding_rows = metrics.get("top_holding_rows") or []
    if len(holding_rows) > 1:
        parts.append("第一大持仓 " + " ".join(holding_rows[1][1:4]))
    industry_rows = metrics.get("industry_allocation_rows") or []
    if industry_rows and isinstance(industry_rows[0], dict):
        first = industry_rows[0]
        parts.append(f"第一大行业 {first.get('industry')} {first.get('net_asset_ratio')}")
    asset_rows = metrics.get("asset_allocation_rows") or []
    if asset_rows and isinstance(asset_rows[-1], dict):
        last = asset_rows[-1]
        parts.append(f"股票仓位 {last.get('stock_ratio')}%")
    scale_rows = metrics.get("scale_change_rows") or []
    if len(scale_rows) > 1:
        parts.append(f"期末净资产 {scale_rows[1][4]} 亿元")
    if metrics.get("large_down_days_sample") is not None:
        parts.append(f"样本大跌日 {metrics.get('large_down_days_sample')} 天")
    return "；".join(str(part) for part in parts if part)[:500]


def build_risk_section(cleaned: dict[str, dict[str, Any]]) -> dict[str, Any]:
    flags = collect_risk_flags(cleaned, limit=6)
    if not flags:
        return {"body": "本地模块未识别到明确风险标签，仍需关注后续公告和行情波动。", "items": []}
    items = [{"label": "风险提示", "value": "；".join(flag["title"] for flag in flags if flag.get("title"))}]
    return {"body": items[0]["value"] + "。", "items": items}


def collect_risk_flags(cleaned: dict[str, dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for module_name, payload in cleaned.items():
        for flag in dig(payload, "data", "risk_flags") or []:
            if not isinstance(flag, dict):
                continue
            flags.append(
                {
                    "module": module_name,
                    "level": flag.get("level", "notice"),
                    "title": flag.get("title") or flag.get("message") or "",
                    "detail": flag.get("detail") or flag.get("description"),
                }
            )
    return [flag for flag in flags if flag.get("title")][:limit]


def market_code(stock_code: str) -> str:
    code = normalize_stock_code(stock_code)
    suffix = "SH" if code.startswith(("6", "9")) else "SZ"
    return f"{code}.{suffix}"


def dig(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def format_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def format_number(value: Any) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, (int, float)):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def format_percent(value: Any) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"
    return str(value)


def format_amount(value: Any) -> str:
    if value is None:
        return "暂无"
    if not isinstance(value, (int, float)):
        return str(value)
    abs_value = abs(value)
    if abs_value >= 100_000_000:
        return f"{value / 100_000_000:.2f} 亿"
    if abs_value >= 10_000:
        return f"{value / 10_000:.2f} 万"
    return f"{value:.2f}"
