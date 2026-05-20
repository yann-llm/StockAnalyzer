"""Clean industry margin-trading module."""

from __future__ import annotations

from typing import Any

from .cleaning_common import date_only, first, ratio, round_number


MARGIN_FIELDS = (
    "BOARD_CODE",
    "BOARD_NAME",
    "TRADE_DATE",
    "END_DATE",
    "INTERVAL_TYPE",
    "FIN_BALANCE",
    "FIN_BALANCE_DIFF",
    "FIN_BUY_AMT",
    "FIN_REPAY_AMT",
    "FIN_NETBUY_AMT",
    "FIN_NETSELL_AMT",
    "FIN_BALANCE_RATIO",
    "MARGIN_BALANCE",
    "LOAN_BALANCE",
    "LOAN_BALANCE_VOL",
    "LOAN_SELL_AMT",
    "LOAN_SELL_VOL",
    "LOAN_REPAY_VOL",
    "LOAN_NETSELL_AMT",
    "NOTLIMITED_MARKETCAP_A",
)


def compact_margin_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {}
    for field in MARGIN_FIELDS:
        value = row.get(field)
        key = field.lower()
        compact[key] = date_only(value) if field in ("TRADE_DATE", "END_DATE") else value
    for key in (
        "fin_balance",
        "fin_balance_diff",
        "fin_buy_amt",
        "fin_repay_amt",
        "fin_netbuy_amt",
        "fin_netsell_amt",
        "fin_balance_ratio",
        "margin_balance",
        "loan_balance",
        "loan_balance_vol",
        "loan_sell_amt",
        "loan_sell_vol",
        "loan_repay_vol",
        "loan_netsell_amt",
        "notlimited_marketcap_a",
    ):
        compact[key] = round_number(compact.get(key), 4 if key.endswith("ratio") else 2)
    compact["fin_netbuy_to_balance"] = ratio(compact.get("fin_netbuy_amt"), compact.get("fin_balance"))
    return compact


def compact_margin_trading(module: dict[str, Any]) -> dict[str, Any]:
    periods = module.get("parsed", {}).get("periods", {})
    return {period: compact_margin_row(first(rows)) for period, rows in periods.items()}
