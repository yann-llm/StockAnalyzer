"""FastAPI entrypoint for the local Eastmoney workbench."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api.services.analysis_runner import get_job, list_jobs, submit_stock_analysis
from api.services.data_store import (
    DataStoreError,
    PROJECT_DIR,
    StockNotFoundError,
    build_stock_summary,
    build_stocks_index,
    normalize_stock_code,
)


app = FastAPI(title="Eastmoney Workbench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PROJECT_DIR / "eastmoney.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "eastmoney-workbench"}


@app.get("/api/stocks")
def stocks() -> dict[str, object]:
    items = build_stocks_index()
    return {"items": items, "count": len(items)}


@app.get("/api/stocks/{stock_code}/summary")
def stock_summary(stock_code: str) -> dict[str, object]:
    try:
        return build_stock_summary(stock_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StockNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/stocks/{stock_code}/analyze")
def analyze_stock(stock_code: str, force: bool = False) -> dict[str, object]:
    try:
        code = normalize_stock_code(stock_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return submit_stock_analysis(code, force_refresh=force)


@app.get("/api/jobs")
def jobs(limit: int = 20) -> dict[str, object]:
    safe_limit = min(max(limit, 1), 50)
    items = list_jobs(limit=safe_limit)
    return {"items": items, "count": len(items)}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, object]:
    try:
        return get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
