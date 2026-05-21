"""In-memory stock analysis jobs for the local API."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from security_profile import is_etf_profile, resolve_security_profile

LOCAL_TZ = timezone(timedelta(hours=8))

_executor = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()
MAX_JOBS = 50
MODULE_NAMES = ("stockcomment", "financial", "industry", "notice_risk", "valuation")
ETF_MODULE_NAMES = (
    "etf_product_index",
    "etf_return_performance",
    "etf_risk_volatility",
    "etf_holding_exposure",
    "etf_scale_liquidity",
)
ALL_MODULE_NAMES = tuple(dict.fromkeys((*MODULE_NAMES, *ETF_MODULE_NAMES)))
TASK_NAMES = (*ALL_MODULE_NAMES, "final_evaluation")
STAGE_NAMES = {
    "cache": "缓存",
    "fetch": "抓取",
    "clean": "清洗",
    "llm": "大模型分析",
    "module": "模块完成",
}


def submit_stock_analysis(stock_code: str, force_refresh: bool = False) -> dict[str, Any]:
    active_job = find_active_job(stock_code)
    if active_job:
        active_job["deduplicated"] = True
        return active_job

    job_id = uuid4().hex
    now = now_text()
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "stock_code": stock_code,
            "force_refresh": force_refresh,
            "summary": None,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "result": None,
            "module_tasks": initial_module_tasks(stock_code=stock_code),
            "deduplicated": False,
        }
        prune_jobs_locked()

    future = _executor.submit(_run_job, job_id, stock_code, force_refresh)
    future.add_done_callback(_capture_unhandled_error(job_id))
    return get_job(job_id)


def submit_module_llm_analysis(stock_code: str, module_name: str) -> dict[str, Any]:
    if module_name not in TASK_NAMES:
        raise ValueError(f"unsupported module: {module_name}")
    if module_name not in task_names_for_stock(stock_code):
        raise ValueError(f"module {module_name} is not available for {resolve_security_profile(stock_code).get('security_type')}")

    job_id = uuid4().hex
    now = now_text()
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "stock_code": stock_code,
            "force_refresh": False,
            "module_name": module_name,
            "job_type": "module_llm",
            "summary": None,
            "status": "queued",
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "result": None,
            "module_tasks": initial_module_tasks(active_module=module_name, stock_code=stock_code),
            "deduplicated": False,
        }
        prune_jobs_locked()

    future = _executor.submit(_run_module_llm_job, job_id, stock_code, module_name)
    future.add_done_callback(_capture_unhandled_error(job_id))
    return get_job(job_id)


def rerun_module_llm_analysis(stock_code: str, module_name: str, job_id: str | None = None) -> dict[str, Any]:
    if module_name not in TASK_NAMES:
        raise ValueError(f"unsupported module: {module_name}")
    task_names = task_names_for_stock(stock_code)
    if module_name not in task_names:
        raise ValueError(f"module {module_name} is not available for {resolve_security_profile(stock_code).get('security_type')}")

    from financial.financial_llm_analyzer import analyze_financial_reports
    from industry.industry_llm_analyzer import analyze_industry
    from etf_fund.etf_fund_llm_analyzer import analyze_etf_fund_module
    from main import (
        cache_manifest_path,
        now_local,
        read_json,
        run_llm_postprocess_with_progress,
        save_final_evaluation,
        save_module_analysis,
        stock_data_dir,
        write_json,
    )
    from notice_risk.notice_risk_llm_analyzer import analyze_notice_risk
    from stockcomment.stockcomment_llm_analyzer import analyze_stockcomment
    from valuation.valuation_llm_analyzer import analyze_valuation

    analyzers = {
        "stockcomment": analyze_stockcomment,
        "etf_product_index": analyze_etf_fund_module,
        "etf_return_performance": analyze_etf_fund_module,
        "etf_risk_volatility": analyze_etf_fund_module,
        "etf_holding_exposure": analyze_etf_fund_module,
        "etf_scale_liquidity": analyze_etf_fund_module,
        "financial": analyze_financial_reports,
        "industry": analyze_industry,
        "notice_risk": analyze_notice_risk,
        "valuation": analyze_valuation,
    }

    manifest_file = cache_manifest_path(stock_code)
    manifest = read_json(manifest_file)
    modules = manifest.setdefault("modules", {})

    if module_name == "final_evaluation":
        generated_at = now_local()
        dependency_names = [name for name in task_names if name != "final_evaluation" and name in modules]
        for dependency_name in dependency_names:
            dependency_info = modules.get(dependency_name)
            if not isinstance(dependency_info, dict):
                raise ValueError(f"module not recorded in manifest: {dependency_name}")
            if dependency_info.get("analysis_status") == "success" and dependency_info.get("analysis_file"):
                if job_id:
                    update_module_task(job_id, dependency_name, "llm", "success", "已有大模型分析结果")
                continue
            cleaned_file = dependency_info.get("cleaned_file")
            if not cleaned_file:
                raise ValueError(f"module has no cleaned file: {dependency_name}")
            cleaned_payload = read_json(stock_data_dir(stock_code) / Path(cleaned_file))
            cleaned_data = cleaned_payload.get("data", cleaned_payload)
            if job_id:
                update_module_task(job_id, dependency_name, "llm", "running", "补齐大模型分析")
            try:
                dependency_result = run_llm_postprocess_with_progress(
                    cleaned_data,
                    lambda data, dep=dependency_name: save_module_analysis(
                        stock_code,
                        dep,
                        generated_at,
                        data,
                        analyzers[dep],
                    ),
                    (lambda module, stage, status, message=None: update_module_task(job_id, module, stage, status, message))
                    if job_id
                    else None,
                    dependency_name,
                )
            except Exception as exc:  # noqa: BLE001 - persist dependency failure before final evaluation.
                dependency_info.update(
                    {
                        "status": "failed",
                        "analysis_status": "failed",
                        "analysis_error": str(exc),
                        "error": str(exc),
                    }
                )
                write_json(manifest_file, manifest)
                raise
            dependency_info.update(
                {
                    "status": "success",
                    "analysis_status": "success",
                    "analysis_file": dependency_result.get("analysis_file"),
                    "analysis_error": None,
                    "error": None,
                }
            )
            if job_id:
                update_module_task(job_id, dependency_name, "llm", "success", "大模型分析已补齐")
        manifest["final_evaluation"] = save_final_evaluation(
            stock_code,
            generated_at,
            {name: modules[name] for name in dependency_names},
            (lambda module, stage, status, message=None: update_module_task(job_id, module, stage, status, message))
            if job_id
            else None,
        )
        write_json(manifest_file, manifest)
        final_status = manifest["final_evaluation"].get("analysis_status")
        if final_status != "success":
            raise ValueError(manifest["final_evaluation"].get("analysis_error") or "final evaluation failed")
        return {
            "stock_code": stock_code,
            "module": module_name,
            "status": "success",
            "final_evaluation": manifest.get("final_evaluation"),
        }

    module_info = modules.get(module_name)
    if not isinstance(module_info, dict):
        raise ValueError(f"module not recorded in manifest: {module_name}")

    cleaned_file = module_info.get("cleaned_file")
    if not cleaned_file:
        raise ValueError(f"module has no cleaned file: {module_name}")

    cleaned_payload = read_json(stock_data_dir(stock_code) / Path(cleaned_file))
    cleaned_data = cleaned_payload.get("data", cleaned_payload)

    try:
        generated_at = now_local()
        if job_id:
            update_module_task(job_id, module_name, "llm", "running", "调用大模型分析")
            analysis_result = run_llm_postprocess_with_progress(
                cleaned_data,
                lambda data: save_module_analysis(stock_code, module_name, generated_at, data, analyzers[module_name]),
                lambda module, stage, status, message=None: update_module_task(job_id, module, stage, status, message),
                module_name,
            )
        else:
            analysis_result = save_module_analysis(
                stock_code,
                module_name,
                generated_at,
                cleaned_data,
                analyzers[module_name],
            )
    except Exception as exc:  # noqa: BLE001 - persist the module-level retry failure for the UI.
        if job_id:
            update_module_task(job_id, module_name, "llm", "failed", str(exc))
        module_info.update(
            {
                "status": "failed",
                "analysis_status": "failed",
                "analysis_error": str(exc),
                "error": str(exc),
            }
        )
        write_json(manifest_file, manifest)
        raise

    module_info.update(
        {
            "status": "success",
            "analysis_status": "success",
            "analysis_file": analysis_result.get("analysis_file"),
            "analysis_error": None,
            "error": None,
        }
    )
    if job_id:
        update_module_task(job_id, "final_evaluation", "llm", "running", "刷新最终投资结论")
    manifest["final_evaluation"] = save_final_evaluation(
        stock_code,
        generated_at,
        modules,
        (lambda module, stage, status, message=None: update_module_task(job_id, module, stage, status, message))
        if job_id
        else None,
    )
    write_json(manifest_file, manifest)
    if job_id:
        update_module_task(job_id, module_name, "module", "success", "模块大模型分析完成")
    return {
        "stock_code": stock_code,
        "module": module_name,
        "status": "success",
        "final_evaluation": manifest.get("final_evaluation"),
        **analysis_result,
    }


def get_job(job_id: str) -> dict[str, Any]:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return snapshot_job(job)


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda item: item["created_at"], reverse=True)
        return [snapshot_job(job) for job in jobs[:limit]]


def find_active_job(stock_code: str) -> dict[str, Any] | None:
    with _lock:
        active = [
            job
            for job in _jobs.values()
            if job.get("stock_code") == stock_code and job.get("status") in {"queued", "running"}
        ]
        if not active:
            return None
        active.sort(key=lambda item: item["created_at"], reverse=True)
        return dict(active[0])


def _run_job(job_id: str, stock_code: str, force_refresh: bool) -> None:
    update_job(job_id, status="running", started_at=now_text())
    try:
        result = run_stock_analysis(
            stock_code,
            force_refresh=force_refresh,
            progress=lambda module, stage, status, message=None: update_module_task(
                job_id,
                module,
                stage,
                status,
                message,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - expose job failure without crashing the API worker.
        update_job(job_id, status="failed", finished_at=now_text(), error=str(exc))
        return
    summary = {
        "stock_code": result.get("stock_code", stock_code),
        "status": result.get("status"),
        "modules": result.get("modules", {}),
        "final_evaluation": result.get("final_evaluation", {}),
        "summary_file": result.get("summary_file"),
        "cache_manifest": result.get("cache_manifest"),
    }
    update_job(job_id, status="success", finished_at=now_text(), result=result, summary=summary)


def _run_module_llm_job(job_id: str, stock_code: str, module_name: str) -> None:
    update_job(job_id, status="running", started_at=now_text())
    try:
        result = rerun_module_llm_analysis(stock_code, module_name, job_id=job_id)
    except Exception as exc:  # noqa: BLE001 - expose module retry failure without crashing the API worker.
        update_job(job_id, status="failed", finished_at=now_text(), error=str(exc))
        return
    summary = {
        "stock_code": stock_code,
        "status": result.get("status"),
        "module": module_name,
        "analysis_file": result.get("analysis_file"),
        "final_evaluation": result.get("final_evaluation"),
    }
    update_job(job_id, status="success", finished_at=now_text(), result=result, summary=summary)


def _capture_unhandled_error(job_id: str):
    def callback(future: Future[Any]) -> None:
        exc = future.exception()
        if exc is not None:
            update_job(job_id, status="failed", finished_at=now_text(), error=str(exc))

    return callback


def update_job(job_id: str, **updates: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(updates)


def snapshot_job(job: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(job)
    if "module_tasks" in snapshot:
        snapshot["module_tasks"] = [dict(task) for task in snapshot["module_tasks"]]
    return snapshot


def task_names_for_stock(stock_code: str | None = None) -> tuple[str, ...]:
    if stock_code and is_etf_profile(resolve_security_profile(stock_code)):
        return (*ETF_MODULE_NAMES, "final_evaluation")
    return (*MODULE_NAMES, "final_evaluation")


def initial_module_tasks(active_module: str | None = None, stock_code: str | None = None) -> list[dict[str, Any]]:
    task_names = list(task_names_for_stock(stock_code))
    return [
        {
            "module": module_name,
            "stage": "queued",
            "stage_name": "等待",
            "status": "queued" if active_module is None or module_name == active_module else "skipped",
            "message": "等待执行" if active_module is None or module_name == active_module else "本次不执行",
            "updated_at": None,
        }
        for module_name in task_names
    ]


def update_module_task(
    job_id: str,
    module_name: str,
    stage: str,
    status: str,
    message: str | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        tasks = job.setdefault("module_tasks", initial_module_tasks(stock_code=job.get("stock_code")))
        task = next((item for item in tasks if item.get("module") == module_name), None)
        if task is None:
            task = {"module": module_name}
            tasks.append(task)
        task.update(
            {
                "stage": stage,
                "stage_name": STAGE_NAMES.get(stage, stage),
                "status": status,
                "message": message,
                "updated_at": now_text(),
            }
        )


def prune_jobs_locked() -> None:
    if len(_jobs) <= MAX_JOBS:
        return
    completed = [
        job
        for job in _jobs.values()
        if job.get("status") not in {"queued", "running"}
    ]
    completed.sort(key=lambda item: item["created_at"])
    for job in completed[: max(0, len(_jobs) - MAX_JOBS)]:
        _jobs.pop(job["job_id"], None)


def now_text() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def run_stock_analysis(
    stock_code: str,
    force_refresh: bool = False,
    progress: Any | None = None,
) -> dict[str, Any]:
    from main import run_stock_analysis as core_run_stock_analysis

    return core_run_stock_analysis(stock_code, force_refresh=force_refresh, progress=progress)
