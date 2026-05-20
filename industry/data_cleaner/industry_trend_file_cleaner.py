"""File-based cleaner for persisted Eastmoney industry raw modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .industry_trend_cleaner import clean_industry_trend_data


MODULE_RAW_FILES = {
    "market": "industry_market_raw_{stock_code}.json",
    "capital_flow": "industry_capital_flow_raw_{stock_code}.json",
    "index_snapshot": "industry_index_snapshot_raw_{stock_code}.json",
    "index_kline": "industry_index_kline_raw_{stock_code}.json",
    "reports": "industry_reports_raw_{stock_code}.json",
    "margin_trading": "industry_margin_trading_raw_{stock_code}.json",
    "valuation": "industry_valuation_raw_{stock_code}.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_industry_data_from_raw_files(stock_code: str | int, data_dir: str | Path) -> dict[str, Any]:
    """Load persisted raw modules and build the aggregate industry data payload."""
    code = str(stock_code).strip()
    root = Path(data_dir)
    mapping = load_json(root / f"industry_mapping_raw_{code}.json")
    modules = {
        name: load_json(root / filename.format(stock_code=code))
        for name, filename in MODULE_RAW_FILES.items()
    }
    bk_code = mapping.get("bk_code")
    numeric_code = str(int(str(bk_code)[2:])) if bk_code else ""
    return {
        "source": "eastmoney",
        "stock_code": code,
        "codes": {
            "bk_code": bk_code,
            "numeric_code": numeric_code,
            "valuation_board_code": mapping.get("valuation_board_code"),
        },
        "mapping": mapping,
        "modules": modules,
    }


def clean_industry_raw_files(
    stock_code: str | int,
    data_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Clean persisted raw industry module files for one stock code."""
    code = str(stock_code).strip()
    industry_data = build_industry_data_from_raw_files(code, data_dir)
    cleaned = clean_industry_trend_data(industry_data)
    cleaned["stock_code"] = code
    cleaned["mapping"] = industry_data["mapping"]
    if output_path is not None:
        save_json(Path(output_path), cleaned)
    return cleaned
