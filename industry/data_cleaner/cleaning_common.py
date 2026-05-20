"""Shared cleaning helpers for Eastmoney industry modules."""

from __future__ import annotations

from typing import Any


def number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_number(value: Any, digits: int = 4) -> float | None:
    num = number(value)
    if num is None:
        return None
    return round(num, digits)


def first(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not rows:
        return {}
    return rows[0] if isinstance(rows[0], dict) else {}


def date_only(value: Any) -> str | None:
    if not value:
        return None
    return str(value).split(" ")[0]


def ratio(part: Any, total: Any) -> float | None:
    part_num = number(part)
    total_num = number(total)
    if part_num is None or total_num in (None, 0):
        return None
    return round(part_num / total_num, 4)
