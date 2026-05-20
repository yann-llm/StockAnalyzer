"""In-memory stock analysis jobs for the local API."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

LOCAL_TZ = timezone(timedelta(hours=8))

_executor = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()
MAX_JOBS = 50
MODULE_NAMES = ("stockcomment", "financial", "industry", "notice_risk", "valuation")
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
            "module_tasks": initial_module_tasks(),
            "deduplicated": False,
        }
        prune_jobs_locked()

    future = _executor.submit(_run_job, job_id, stock_code, force_refresh)
    future.add_done_callback(_capture_unhandled_error(job_id))
    return get_job(job_id)


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
        "summary_file": result.get("summary_file"),
        "cache_manifest": result.get("cache_manifest"),
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


def initial_module_tasks() -> list[dict[str, Any]]:
    return [
        {
            "module": module_name,
            "stage": "queued",
            "stage_name": "等待",
            "status": "queued",
            "message": "等待执行",
            "updated_at": None,
        }
        for module_name in MODULE_NAMES
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
        tasks = job.setdefault("module_tasks", initial_module_tasks())
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
