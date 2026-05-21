"""Resolve the broad security type before running stock analysis modules."""

from __future__ import annotations

from typing import Any


ETF_PREFIXES = ("15", "16", "51", "56", "58")


def normalize_stock_code(stock_code: str | int) -> str:
    """Return the plain six-digit security code used by Eastmoney endpoints."""
    code = str(stock_code).strip().upper()
    if "." in code:
        code = code.split(".", 1)[0]
    return code


def resolve_security_profile(stock_code: str | int) -> dict[str, Any]:
    """Classify a security enough to choose compatible analysis modules.

    The first phase deliberately keeps this local and deterministic. A future
    data-backed resolver can add Eastmoney search/basic-info fields while
    preserving this return contract.
    """
    code = normalize_stock_code(stock_code)
    if len(code) == 6 and code.startswith(ETF_PREFIXES):
        security_type = "etf"
        reason = "code_prefix"
    elif len(code) == 6:
        security_type = "stock"
        reason = "default_a_share"
    else:
        security_type = "unknown"
        reason = "unrecognized_code"

    return {
        "stock_code": code,
        "security_type": security_type,
        "classification_reason": reason,
    }


def is_etf_profile(profile: dict[str, Any] | None) -> bool:
    return bool(profile and profile.get("security_type") == "etf")
