"""Main entrypoint for Eastmoney stock analysis data preparation."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from financial import clean_financial_reports, fetch_financial_reports
from industry import clean_industry_trend_data, fetch_industry_trend_data, fetch_valuation_industry_mapping
from industry.industry_llm_analyzer import analyze_industry
from notice_risk import clean_notice_risk_data, fetch_notice_risk_data
from notice_risk.notice_risk_llm_analyzer import analyze_notice_risk
from stockcomment import clean_stockcomment_data, fetch_stockcomment_data
from stockcomment.stockcomment_llm_analyzer import analyze_stockcomment
from valuation import clean_valuation_data, fetch_valuation_data
from valuation.valuation_llm_analyzer import analyze_valuation
from final_evaluation_llm_analyzer import analyze_final_evaluation
from financial.financial_llm_analyzer import analyze_financial_reports


STOCK_CODE = "000157"
CACHE_SECONDS = 60 * 60
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
LOCAL_TZ = timezone(timedelta(hours=8))
ANALYSIS_MODULES = ("stockcomment", "financial", "industry", "notice_risk", "valuation")
LLM_PROGRESS_INTERVAL_SECONDS = 1
MODULE_WORKERS = len(ANALYSIS_MODULES)


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def timestamp_for_file(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S%z")


def isoformat(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def stock_data_dir(stock_code: str) -> Path:
    return DATA_DIR / stock_code


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cache_manifest_path(stock_code: str) -> Path:
    return stock_data_dir(stock_code) / "cache_manifest.json"


def is_cache_usable(stock_code: str, current_time: datetime) -> bool:
    manifest_path = cache_manifest_path(stock_code)
    if not manifest_path.exists():
        return False

    try:
        manifest = read_json(manifest_path)
        generated_at = datetime.fromisoformat(manifest["generated_at"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return False

    if current_time - generated_at > timedelta(seconds=CACHE_SECONDS):
        return False

    modules = manifest.get("modules", {})
    if sorted(modules) != sorted(EXPECTED_MODULES):
        return False

    base_dir = stock_data_dir(stock_code)
    for info in modules.values():
        if info.get("status") != "success":
            return False
        raw_file = info.get("raw_file")
        cleaned_file = info.get("cleaned_file")
        if not raw_file or not cleaned_file:
            return False
        if not (base_dir / raw_file).exists() or not (base_dir / cleaned_file).exists():
            return False

    final_evaluation = manifest.get("final_evaluation", {})
    final_file = final_evaluation.get("analysis_file") if isinstance(final_evaluation, dict) else None
    if not final_file or final_evaluation.get("analysis_status") != "success":
        return False
    if not (base_dir / final_file).exists():
        return False

    return True


def load_cached_result(stock_code: str) -> dict[str, Any]:
    manifest = read_json(cache_manifest_path(stock_code))
    return {
        "stock_code": stock_code,
        "status": "cache_hit",
        "cache_manifest": str(cache_manifest_path(stock_code)),
        "generated_at": manifest.get("generated_at"),
        "expires_at": manifest.get("expires_at"),
        "modules": manifest.get("modules", {}),
        "final_evaluation": manifest.get("final_evaluation", {}),
    }


def with_metadata(data: dict[str, Any], stock_code: str, module_name: str, generated_at: datetime) -> dict[str, Any]:
    return {
        "stock_code": stock_code,
        "module": module_name,
        "generated_at": isoformat(generated_at),
        "data": data,
    }


def run_module(
    stock_code: str,
    module_name: str,
    generated_at: datetime,
    fetcher: Callable[[], dict[str, Any]],
    cleaner: Callable[[dict[str, Any]], dict[str, Any]],
    postprocess: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    progress: Callable[[str, str, str, str | None], None] | None = None,
) -> dict[str, Any]:
    print(f"[开始] {module_name}")
    base_dir = stock_data_dir(stock_code)
    stamp = timestamp_for_file(generated_at)
    raw_relative = Path("raw") / f"{module_name}_raw_{stamp}.json"
    cleaned_relative = Path("cleaned") / f"{module_name}_cleaned_{stamp}.json"
    analysis_relative = Path("analysis") / f"{module_name}_analysis_{stamp}.json"

    try:
        notify_progress(progress, module_name, "fetch", "running", "抓取原始数据")
        raw_data = fetcher()
        notify_progress(progress, module_name, "fetch", "success", "原始数据已抓取")
        notify_progress(progress, module_name, "clean", "running", "清洗模块数据")
        cleaned_data = cleaner(raw_data)
        notify_progress(progress, module_name, "clean", "success", "模块数据已清洗")
        write_json(base_dir / raw_relative, with_metadata(raw_data, stock_code, module_name, generated_at))
        write_json(base_dir / cleaned_relative, with_metadata(cleaned_data, stock_code, module_name, generated_at))
        postprocess_result = None
        if postprocess is not None:
            try:
                notify_progress(progress, module_name, "llm", "running", "调用大模型分析")
                postprocess_result = run_llm_postprocess_with_progress(
                    cleaned_data,
                    postprocess,
                    progress,
                    module_name,
                )
                notify_progress(progress, module_name, "llm", "success", "大模型分析完成")
            except Exception as postprocess_exc:  # noqa: BLE001 - keep module success if LLM analysis fails.
                notify_progress(progress, module_name, "llm", "failed", str(postprocess_exc))
                error_data = {
                    "stock_code": stock_code,
                    "module": module_name,
                    "generated_at": isoformat(generated_at),
                    "stage": "analysis",
                    "error": str(postprocess_exc),
                }
                write_json(base_dir / analysis_relative.with_name(f"{module_name}_analysis_error_{stamp}.json"), error_data)
                print(f"[失败] {module_name} 分析: {postprocess_exc}")
                return {
                    "status": "failed",
                    "raw_file": raw_relative.as_posix(),
                    "cleaned_file": cleaned_relative.as_posix(),
                    "analysis_status": "failed",
                    "analysis_error": str(postprocess_exc),
                    "analysis_error_file": analysis_relative.with_name(f"{module_name}_analysis_error_{stamp}.json").as_posix(),
                }
    except Exception as exc:  # noqa: BLE001 - keep the batch running and persist per-module failure.
        notify_progress(progress, module_name, "module", "failed", str(exc))
        error_relative = Path("errors") / f"{module_name}_error_{stamp}.json"
        error_data = {
            "stock_code": stock_code,
            "module": module_name,
            "generated_at": isoformat(generated_at),
            "error": str(exc),
        }
        write_json(base_dir / error_relative, error_data)
        print(f"[失败] {module_name}: {exc}")
        return {
            "status": "failed",
            "error_file": error_relative.as_posix(),
            "error": str(exc),
        }

    print(f"[成功] {module_name}")
    notify_progress(progress, module_name, "module", "success", "模块完成")
    return {
        "status": "success",
        "raw_file": raw_relative.as_posix(),
        "cleaned_file": cleaned_relative.as_posix(),
        **(postprocess_result or {}),
    }


def notify_progress(
    progress: Callable[[str, str, str, str | None], None] | None,
    module_name: str,
    stage: str,
    status: str,
    message: str | None = None,
) -> None:
    if progress is not None:
        progress(module_name, stage, status, message)


def run_llm_postprocess_with_progress(
    cleaned_data: dict[str, Any],
    postprocess: Callable[[dict[str, Any]], dict[str, Any]],
    progress: Callable[[str, str, str, str | None], None] | None,
    module_name: str,
) -> dict[str, Any]:
    waited_seconds = 0
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(postprocess, cleaned_data)
    try:
        while True:
            try:
                return future.result(timeout=LLM_PROGRESS_INTERVAL_SECONDS)
            except TimeoutError:
                waited_seconds += LLM_PROGRESS_INTERVAL_SECONDS
                notify_progress(
                    progress,
                    module_name,
                    "llm",
                    "running",
                    f"大模型分析中，已等待 {waited_seconds} 秒",
                )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def save_module_analysis(
    stock_code: str,
    module_name: str,
    generated_at: datetime,
    cleaned_data: dict[str, Any],
    analyzer: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    analysis = analyzer(cleaned_data)
    base_dir = stock_data_dir(stock_code)
    analysis_relative = Path("analysis") / f"{module_name}_analysis_{timestamp_for_file(generated_at)}.json"
    write_json(base_dir / analysis_relative, analysis)
    return {
        "analysis_status": "success",
        "analysis_file": analysis_relative.as_posix(),
    }


def load_module_analyses(stock_code: str, module_results: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    base_dir = stock_data_dir(stock_code)
    analyses: dict[str, dict[str, Any]] = {}
    for module_name, info in module_results.items():
        if info.get("analysis_status") != "success":
            continue
        analysis_file = info.get("analysis_file")
        if not analysis_file:
            continue
        analyses[module_name] = read_json(base_dir / analysis_file)
    return analyses


def save_final_evaluation(
    stock_code: str,
    generated_at: datetime,
    module_results: dict[str, dict[str, Any]],
    progress: Callable[[str, str, str, str | None], None] | None = None,
) -> dict[str, Any]:
    base_dir = stock_data_dir(stock_code)
    stamp = timestamp_for_file(generated_at)
    analysis_relative = Path("analysis") / f"final_evaluation_{stamp}.json"
    error_relative = Path("analysis") / f"final_evaluation_error_{stamp}.json"

    try:
        notify_progress(progress, "final_evaluation", "llm", "running", "汇总五大模块结论")
        module_analyses = load_module_analyses(stock_code, module_results)
        missing_modules = [module_name for module_name in ANALYSIS_MODULES if module_name not in module_analyses]
        if missing_modules:
            raise ValueError(f"missing successful module analysis: {', '.join(missing_modules)}")
        if not module_analyses:
            raise ValueError("no successful module analysis is available for final evaluation")
        analysis = run_llm_postprocess_with_progress(
            module_analyses,
            lambda analyses: analyze_final_evaluation(stock_code, analyses),
            progress,
            "final_evaluation",
        )
        write_json(base_dir / analysis_relative, analysis)
        notify_progress(progress, "final_evaluation", "llm", "success", "最终投资结论已生成")
        return {
            "analysis_status": "success",
            "analysis_file": analysis_relative.as_posix(),
            "module_count": len(module_analyses),
        }
    except Exception as exc:  # noqa: BLE001 - persist final evaluation failure without hiding module results.
        notify_progress(progress, "final_evaluation", "llm", "failed", str(exc))
        error_data = {
            "stock_code": stock_code,
            "module": "final_evaluation",
            "generated_at": isoformat(generated_at),
            "stage": "analysis",
            "error": str(exc),
        }
        write_json(base_dir / error_relative, error_data)
        print(f"[失败] final_evaluation 分析: {exc}")
        return {
            "analysis_status": "failed",
            "analysis_error": str(exc),
            "analysis_error_file": error_relative.as_posix(),
        }


def fetch_industry_for_stock(stock_code: str) -> dict[str, Any]:
    mapping = fetch_valuation_industry_mapping(stock_code)
    industry_code = mapping.get("bk_code")
    if not industry_code:
        raise ValueError(f"stock {stock_code} has no Eastmoney BK industry code")

    raw_data = fetch_industry_trend_data(industry_code, stock_code=stock_code)
    raw_data["stock_industry_mapping"] = mapping
    return raw_data


def clean_industry_for_stock(raw_data: dict[str, Any]) -> dict[str, Any]:
    cleaned = clean_industry_trend_data(raw_data)
    cleaned["stock_industry_mapping"] = raw_data.get("stock_industry_mapping", {})
    return cleaned


def module_specs(
    stock_code: str,
    generated_at: datetime,
    progress: Callable[[str, str, str, str | None], None] | None = None,
) -> dict[str, Callable[[], dict[str, Any]]]:
    return {
        "stockcomment": lambda: run_module(
            stock_code,
            "stockcomment",
            generated_at,
            lambda: fetch_stockcomment_data(stock_code, page_size=1),
            clean_stockcomment_data,
            postprocess=lambda cleaned_data: save_module_analysis(
                stock_code, "stockcomment", generated_at, cleaned_data, analyze_stockcomment
            ),
            progress=progress,
        ),
        "financial": lambda: run_module(
            stock_code,
            "financial",
            generated_at,
            lambda: fetch_financial_reports(stock_code, page_size=5),
            clean_financial_reports,
            postprocess=lambda cleaned_data: save_module_analysis(
                stock_code, "financial", generated_at, cleaned_data, analyze_financial_reports
            ),
            progress=progress,
        ),
        "industry": lambda: run_module(
            stock_code,
            "industry",
            generated_at,
            lambda: fetch_industry_for_stock(stock_code),
            clean_industry_for_stock,
            postprocess=lambda cleaned_data: save_module_analysis(
                stock_code, "industry", generated_at, cleaned_data, analyze_industry
            ),
            progress=progress,
        ),
        "notice_risk": lambda: run_module(
            stock_code,
            "notice_risk",
            generated_at,
            lambda: fetch_notice_risk_data(stock_code, page_size=20),
            clean_notice_risk_data,
            postprocess=lambda cleaned_data: save_module_analysis(
                stock_code, "notice_risk", generated_at, cleaned_data, analyze_notice_risk
            ),
            progress=progress,
        ),
        "valuation": lambda: run_module(
            stock_code,
            "valuation",
            generated_at,
            lambda: fetch_valuation_data(stock_code, detail_size=60),
            clean_valuation_data,
            postprocess=lambda cleaned_data: save_module_analysis(
                stock_code, "valuation", generated_at, cleaned_data, analyze_valuation
            ),
            progress=progress,
        ),
    }


def run_modules_parallel(
    stock_code: str,
    generated_at: datetime,
    progress: Callable[[str, str, str, str | None], None] | None = None,
) -> dict[str, dict[str, Any]]:
    specs = module_specs(stock_code, generated_at, progress)
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=MODULE_WORKERS) as executor:
        futures = {executor.submit(run): module_name for module_name, run in specs.items()}
        for future in as_completed(futures):
            module_name = futures[future]
            try:
                results[module_name] = future.result()
            except Exception as exc:  # noqa: BLE001 - run_module should catch, but keep the manifest complete.
                notify_progress(progress, module_name, "module", "failed", str(exc))
                results[module_name] = {
                    "status": "failed",
                    "error": str(exc),
                }
    return {module_name: results[module_name] for module_name in ANALYSIS_MODULES}


def run_stock_analysis(
    stock_code: str,
    force_refresh: bool = False,
    progress: Callable[[str, str, str, str | None], None] | None = None,
) -> dict[str, Any]:
    generated_at = now_local()
    if not force_refresh and is_cache_usable(stock_code, generated_at):
        print(f"[缓存] {stock_code} 最近 1 小时已有完整数据，复用已有文件。")
        for module_name in ANALYSIS_MODULES:
            notify_progress(progress, module_name, "cache", "success", "复用缓存分析结果")
        return load_cached_result(stock_code)

    module_results = run_modules_parallel(stock_code, generated_at, progress)
    final_evaluation = save_final_evaluation(stock_code, generated_at, module_results, progress)

    expires_at = generated_at + timedelta(seconds=CACHE_SECONDS)
    manifest = {
        "stock_code": stock_code,
        "generated_at": isoformat(generated_at),
        "expires_at": isoformat(expires_at),
        "cache_seconds": CACHE_SECONDS,
        "modules": module_results,
        "final_evaluation": final_evaluation,
    }
    write_json(cache_manifest_path(stock_code), manifest)

    summary_path = stock_data_dir(stock_code) / f"analysis_summary_{timestamp_for_file(generated_at)}.json"
    write_json(summary_path, manifest)
    return {
        "stock_code": stock_code,
        "status": "fetched",
        "cache_manifest": str(cache_manifest_path(stock_code)),
        "summary_file": str(summary_path),
        "modules": module_results,
        "final_evaluation": final_evaluation,
    }


EXPECTED_MODULES = ("financial", "industry", "notice_risk", "stockcomment", "valuation")


def main() -> None:
    result = run_stock_analysis(STOCK_CODE)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
