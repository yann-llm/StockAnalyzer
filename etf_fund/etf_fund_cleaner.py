"""Clean Eastmoney ETF Fund F10 pages into five fund score blocks."""

from __future__ import annotations

import re
import json
from html import unescape
from html.parser import HTMLParser
from typing import Any


BLOCK_WEIGHTS = {
    "product_index": 0.15,
    "return_performance": 0.25,
    "risk_volatility": 0.20,
    "holding_exposure": 0.25,
    "scale_liquidity": 0.15,
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._capture_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []
            self._capture_cell = True

    def handle_data(self, data: str) -> None:
        if self._capture_cell and self._cell_parts is not None:
            text = data.strip()
            if text:
                self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._capture_cell:
            cell = " ".join(self._cell_parts or [])
            if self._row is not None:
                self._row.append(_normalize_text(cell))
            self._cell_parts = None
            self._capture_cell = False
        elif tag == "tr" and self._table is not None and self._row is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None


class _ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[str] = []
        self._parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            text = data.strip()
            if text:
                self._parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._parts is not None:
            item = _normalize_text(" ".join(self._parts))
            if item:
                self.items.append(item)
            self._parts = None


def _normalize_text(value: str) -> str:
    text = unescape(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_text(text)


def _tables(html: str) -> list[list[list[str]]]:
    parser = _TableParser()
    parser.feed(html or "")
    return parser.tables


def _table_pairs(table: list[list[str]]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for row in table:
        if len(row) == 3 and row[0] == "基金代码" and row[1] == "基金类型":
            pairs["基金类型"] = row[2]
            continue
        if len(row) == 3 and row[0] == "净资产规模" and row[1] == "份额规模":
            pairs["份额规模"] = row[2]
            continue
        if len(row) >= 2:
            for index in range(0, len(row) - 1, 2):
                key = row[index].rstrip(":：")
                value = row[index + 1]
                if key and value:
                    pairs[key] = value
    return pairs


def _all_pairs(tables: list[list[list[str]]]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for table in tables:
        pairs.update(_table_pairs(table))
    return pairs


def _number(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _percent(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None else None


def _compact_page(module: dict[str, Any]) -> dict[str, Any]:
    html = module.get("html") or ""
    dataset = module.get("dataset") or {}
    dataset_text = dataset.get("text") or ""
    dataset_html = _dataset_html(dataset_text)
    parsed_html = dataset_html or html
    tables = _tables(parsed_html)
    if not tables and module.get("page_key") == "stage_return":
        list_items = _list_items(parsed_html)
        if list_items:
            header = ["阶段", *list_items[:6]]
            rows = [header]
            body = list_items[6:]
            rows.extend(body[index : index + 7] for index in range(0, len(body), 7))
            tables = [rows]
    return {
        "page_name": module.get("page_name"),
        "url": module.get("url"),
        "dataset_url": dataset.get("url"),
        "dataset_json": _dataset_json(dataset_text),
        "chart_data": _chart_data(html),
        "available": bool(tables or dataset_text or _strip_html(html)),
        "tables": tables[:8],
        "pairs": _all_pairs(tables),
        "text_sample": _strip_html(parsed_html)[:1200],
    }


def _list_items(html: str) -> list[str]:
    parser = _ListParser()
    parser.feed(html or "")
    return parser.items


def _dataset_html(text: str) -> str:
    if not text:
        return ""
    match = re.search(r'content\s*:\s*"([\s\S]*?)"\s*(?:,|})', text)
    if not match:
        return ""
    content = match.group(1)
    content = content.replace(r"\/", "/")
    content = content.replace(r"\"", '"')
    content = content.replace(r"\r", "").replace(r"\n", "")
    return unescape(content)


def _dataset_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return {}
    return {}


def _chart_data(html: str) -> dict[str, Any]:
    match = re.search(r"var\s+chartData\s*=\s*(\{[\s\S]*?\});", html or "")
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _first_table_rows(page: dict[str, Any], limit: int = 20) -> list[list[str]]:
    tables = [
        table
        for table in page.get("tables") or []
        if table and not any("热点推荐" in " ".join(row) for row in table[:2])
    ]
    return tables[0][:limit] if tables else []


def _profile_block(profile: dict[str, Any]) -> dict[str, Any]:
    pairs = profile.get("pairs") or {}
    management_fee = _percent(pairs.get("管理费率") or pairs.get("管理费"))
    custody_fee = _percent(pairs.get("托管费率") or pairs.get("托管费"))
    size = _number(pairs.get("基金规模") or pairs.get("最新规模") or pairs.get("份额规模"))
    score = 60
    if pairs.get("跟踪标的") or pairs.get("业绩比较基准"):
        score += 12
    if size is not None and size >= 2:
        score += 8
    if management_fee is not None and management_fee <= 0.5:
        score += 5
    if custody_fee is not None and custody_fee <= 0.1:
        score += 5
    return {
        "name": "产品与指数定位",
        "weight": BLOCK_WEIGHTS["product_index"],
        "score": _clamp(score),
        "source_pages": ["基本概况"],
        "metrics": {
            "fund_name": pairs.get("基金全称") or pairs.get("基金简称"),
            "fund_type": pairs.get("基金类型"),
            "tracking_index": pairs.get("跟踪标的") or pairs.get("业绩比较基准"),
            "manager": pairs.get("基金管理人"),
            "fund_manager": pairs.get("基金经理人") or pairs.get("基金经理"),
            "inception_date": pairs.get("成立日期"),
            "fund_size": pairs.get("基金规模") or pairs.get("最新规模") or pairs.get("份额规模"),
            "management_fee": pairs.get("管理费率") or pairs.get("管理费"),
            "custody_fee": pairs.get("托管费率") or pairs.get("托管费"),
        },
        "notes": [
            "优先确认 ETF 类型、跟踪指数、管理人和费率是否清晰。",
            "规模和低费率会提升产品可投资性，但仍需结合成交活跃度。",
        ],
    }


def _return_block(nav_history: dict[str, Any], stage_return: dict[str, Any]) -> dict[str, Any]:
    rows = _first_table_rows(stage_return, 30)
    nav_rows = _nav_rows(nav_history)
    text = " ".join(" ".join(row) for row in rows)
    positive = len(re.findall(r"\+\d|\d+(?:\.\d+)?%", text))
    negative = len(re.findall(r"-\d", text))
    score = 55 + min(positive, 8) * 3 - min(negative, 8) * 4
    return {
        "name": "收益表现",
        "weight": BLOCK_WEIGHTS["return_performance"],
        "score": _clamp(score),
        "source_pages": ["历史净值", "阶段涨幅"],
        "metrics": {
            "stage_return_rows": rows,
            "latest_nav_rows": nav_rows[:10],
        },
        "notes": [
            "阶段涨幅用于观察近 1 月、3 月、6 月、1 年和成立以来收益。",
            "历史净值用于后续计算复权收益和净值趋势。",
        ],
    }


def _risk_block(nav_history: dict[str, Any], stage_return: dict[str, Any]) -> dict[str, Any]:
    nav_rows = _nav_rows(nav_history)
    stage_rows = _first_table_rows(stage_return, 30)
    changes = [_percent(row.get("JZZZL")) for row in nav_rows if isinstance(row, dict)]
    changes = [change for change in changes if change is not None]
    large_down_days = sum(1 for change in changes if change <= -2)
    score = 65 - min(large_down_days, 8) * 4
    return {
        "name": "风险与波动",
        "weight": BLOCK_WEIGHTS["risk_volatility"],
        "score": _clamp(score),
        "source_pages": ["历史净值", "阶段涨幅"],
        "metrics": {
            "large_down_days_sample": large_down_days,
            "nav_rows_sample_count": len(nav_rows),
            "stage_return_rows": stage_rows,
        },
        "notes": [
            "第一版用历史净值中的日涨跌样本识别明显波动，后续可扩展最大回撤和年化波动。",
            "主题 ETF 波动通常高于宽基 ETF，评分需结合跟踪指数行业属性解读。",
        ],
    }


def _holding_block(holdings: dict[str, Any], industry_allocation: dict[str, Any], asset_allocation: dict[str, Any]) -> dict[str, Any]:
    holding_rows = _first_table_rows(holdings, 15)
    industry_rows = _industry_rows(industry_allocation)
    asset_rows = _asset_rows(asset_allocation)
    concentration_values = [_percent(cell) for row in holding_rows for cell in row if "%" in cell]
    concentration_values = [value for value in concentration_values if value is not None]
    top_weight_sum = sum(concentration_values[:10]) if concentration_values else None
    score = 60
    if top_weight_sum is not None:
        if top_weight_sum <= 55:
            score += 8
        elif top_weight_sum >= 75:
            score -= 8
    if industry_rows:
        score += 6
    if asset_rows:
        score += 6
    return {
        "name": "持仓与行业暴露",
        "weight": BLOCK_WEIGHTS["holding_exposure"],
        "score": _clamp(score),
        "source_pages": ["基金持仓", "行业配置", "资产配置"],
        "metrics": {
            "top_holding_rows": holding_rows,
            "industry_allocation_rows": industry_rows,
            "asset_allocation_rows": asset_rows,
            "top_weight_sum_sample": round(top_weight_sum, 2) if top_weight_sum is not None else None,
        },
        "notes": [
            "基金持仓和行业配置用于替代普通股票的行业分析。",
            "前十大集中度越高，主题弹性越强，但单一产业链风险也更集中。",
        ],
    }


def _scale_block(profile: dict[str, Any], scale_change: dict[str, Any]) -> dict[str, Any]:
    pairs = profile.get("pairs") or {}
    rows = _first_table_rows(scale_change, 20)
    latest_scale = rows[1] if len(rows) > 1 else []
    latest_net_asset = latest_scale[4] if len(latest_scale) > 4 else None
    size = _number(pairs.get("基金规模") or pairs.get("最新规模") or latest_net_asset)
    score = 55
    if size is not None:
        if size >= 10:
            score += 18
        elif size >= 2:
            score += 10
        elif size < 1:
            score -= 12
    if rows:
        score += 8
    return {
        "name": "规模与流动性",
        "weight": BLOCK_WEIGHTS["scale_liquidity"],
        "score": _clamp(score),
        "source_pages": ["规模变动", "基本概况"],
        "metrics": {
            "fund_size": pairs.get("基金规模") or pairs.get("最新规模") or latest_net_asset,
            "scale_change_rows": rows,
        },
        "notes": [
            "基金规模和份额变化用于判断产品生命力与申赎趋势。",
            "场内 ETF 还需要补充成交额、盘口和折溢价数据，第一版暂以档案页规模为主。",
        ],
    }


def _nav_rows(nav_history: dict[str, Any]) -> list[dict[str, Any]]:
    data = nav_history.get("dataset_json") or {}
    rows = data.get("Data", {}).get("LSJZList", []) if isinstance(data, dict) else []
    return rows if isinstance(rows, list) else []


def _industry_rows(industry_allocation: dict[str, Any]) -> list[dict[str, Any]]:
    data = industry_allocation.get("dataset_json") or {}
    quarters = data.get("Data", {}).get("QuarterInfos", []) if isinstance(data, dict) else []
    if not quarters:
        return []
    rows = quarters[0].get("HYPZInfo", []) if isinstance(quarters[0], dict) else []
    return [
        {
            "date": row.get("FSRQ"),
            "industry": row.get("HYMC"),
            "market_value": row.get("SZDesc") or row.get("SZ"),
            "net_asset_ratio": row.get("ZJZBLDesc") or row.get("ZJZBL"),
        }
        for row in rows[:15]
        if isinstance(row, dict)
    ]


def _asset_rows(asset_allocation: dict[str, Any]) -> list[dict[str, Any]]:
    chart = asset_allocation.get("chart_data") or {}
    dates = chart.get("Dates") or []
    rows = []
    for index, date in enumerate(dates):
        rows.append(
            {
                "date": date,
                "stock_ratio": _chart_value(chart, "GP", index),
                "bond_ratio": _chart_value(chart, "ZQ", index),
                "cash_ratio": _chart_value(chart, "XJ", index),
                "net_asset": _chart_value(chart, "JZC", index),
            }
        )
    return rows[-10:]


def _chart_value(chart: dict[str, Any], key: str, index: int) -> Any:
    values = chart.get(key) or []
    return values[index] if index < len(values) else None


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _overall_score(blocks: dict[str, dict[str, Any]]) -> int:
    total = sum(block.get("score", 0) * block.get("weight", 0) for block in blocks.values())
    return _clamp(total)


def _risk_flags(blocks: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    scale = blocks["scale_liquidity"]["metrics"].get("fund_size")
    if scale and (_number(scale) or 0) < 1:
        flags.append({"level": "warning", "title": "基金规模偏小", "detail": f"基金规模为 {scale}。"})
    top_weight_sum = blocks["holding_exposure"]["metrics"].get("top_weight_sum_sample")
    if top_weight_sum is not None and top_weight_sum >= 75:
        flags.append({"level": "notice", "title": "持仓集中度较高", "detail": f"样本前十大权重合计约 {top_weight_sum}%。"})
    flags.append({"level": "notice", "title": "ETF 专属交易数据待补充", "detail": "当前第一版尚未抓取实时成交额、折溢价率和跟踪误差。"})
    return flags


def clean_etf_fund_data(etf_data: dict[str, Any]) -> dict[str, Any]:
    """Clean seven Fund F10 archive pages into five ETF score blocks."""
    modules = etf_data.get("modules", {})
    pages = {key: _compact_page(module) for key, module in modules.items()}
    blocks = {
        "product_index": _profile_block(pages.get("profile", {})),
        "return_performance": _return_block(pages.get("nav_history", {}), pages.get("stage_return", {})),
        "risk_volatility": _risk_block(pages.get("nav_history", {}), pages.get("stage_return", {})),
        "holding_exposure": _holding_block(
            pages.get("holdings", {}),
            pages.get("industry_allocation", {}),
            pages.get("asset_allocation", {}),
        ),
        "scale_liquidity": _scale_block(pages.get("profile", {}), pages.get("scale_change", {})),
    }
    return {
        "stock_code": etf_data.get("stock_code"),
        "source": etf_data.get("source", "eastmoney_fundf10"),
        "security_type": "etf",
        "block_weights": BLOCK_WEIGHTS,
        "overall_score": _overall_score(blocks),
        "blocks": blocks,
        "risk_flags": _risk_flags(blocks),
        "pages": {
            key: {
                "page_name": page.get("page_name"),
                "url": page.get("url"),
                "available": page.get("available"),
                "text_sample": page.get("text_sample"),
            }
            for key, page in pages.items()
        },
    }
