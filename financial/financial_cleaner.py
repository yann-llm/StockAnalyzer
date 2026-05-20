"""Clean Eastmoney financial report data for LLM analysis."""

from __future__ import annotations

from typing import Any


def _raw(row: dict[str, Any], field: str) -> Any:
    return row.get("raw", {}).get(field)


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {"report_date": None, "raw": {}, "parsed": {}}


def _number(value: Any) -> float | None:
    """把接口值转为数字；空值、横线、异常字符串统一转为 None。"""
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> float | None:
    """统一小数精度，避免把过长小数直接塞给大模型。"""
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def _ratio(numerator: Any, denominator: Any, digits: int = 4) -> float | None:
    """安全计算比率，返回百分比口径。"""
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom in (None, 0):
        return None
    return round(top / bottom * 100, digits)


def _period_value(rows: list[dict[str, Any]], field: str, digits: int = 4) -> list[dict[str, Any]]:
    """按报告期提取某个字段，生成趋势序列。"""
    return [
        {
            "report_date": row.get("report_date"),
            "value": _round(_raw(row, field), digits),
        }
        for row in rows
    ]


def _add_flag(flags: list[dict[str, Any]], level: str, title: str, detail: str) -> None:
    flags.append({"level": level, "title": title, "detail": detail})


def _build_risk_flags(latest_rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """根据最新一期关键指标生成初步风险标记，供大模型解释。"""
    flags: list[dict[str, Any]] = []
    performance = latest_rows["performance_report"]
    balance = latest_rows["balance_sheet"]
    income = latest_rows["income_statement"]
    cashflow = latest_rows["cash_flow_statement"]

    net_profit_yoy = _number(_raw(performance, "SJLTZ"))
    revenue_yoy = _number(_raw(performance, "YSTZ"))
    deduct_profit_yoy = _number(_raw(income, "DPN_RATIO"))
    debt_ratio = _number(_raw(balance, "DEBT_ASSET_RATIO"))
    receivable_yoy = _number(_raw(balance, "ACCOUNTS_RECE_RATIO"))
    inventory_yoy = _number(_raw(balance, "INVENTORY_RATIO"))
    equity = _number(_raw(balance, "TOTAL_EQUITY"))
    operate_cash = _number(_raw(cashflow, "NETCASH_OPERATE"))
    net_profit = _number(_raw(income, "PARENT_NETPROFIT"))
    revenue = _number(_raw(performance, "TOTAL_OPERATE_INCOME"))

    # 利润同比下滑是财务分析里最直接的负面信号，先做显式标记。
    if net_profit_yoy is not None and net_profit_yoy < 0:
        _add_flag(flags, "warning", "归母净利润同比下降", f"最新一期归母净利润同比为 {net_profit_yoy}%。")

    # 收入增长但利润下滑，通常说明毛利率、费用、减值或非经常项存在压力。
    if revenue_yoy is not None and revenue_yoy > 0 and net_profit_yoy is not None and net_profit_yoy < 0:
        _add_flag(flags, "warning", "增收不增利", f"营业总收入同比 {revenue_yoy}%，归母净利润同比 {net_profit_yoy}%。")

    # 扣非净利润更接近主营质量，明显下滑需要单独提示。
    if deduct_profit_yoy is not None and deduct_profit_yoy < 0:
        _add_flag(flags, "warning", "扣非净利润同比下降", f"扣非归母净利润同比为 {deduct_profit_yoy}%。")

    # 资产负债率过高会影响偿债安全边际，这里先用 60% 作为温和预警线。
    if debt_ratio is not None and debt_ratio >= 60:
        _add_flag(flags, "warning", "资产负债率偏高", f"资产负债率为 {debt_ratio}%。")

    # 应收账款快速增长可能代表回款压力，需要结合收入增速一起解释。
    if receivable_yoy is not None and receivable_yoy >= 30:
        _add_flag(flags, "warning", "应收账款增长较快", f"应收账款同比增长 {receivable_yoy}%。")

    # 存货增长过快可能代表库存压力；当前仅做提示，不直接判定风险严重。
    if inventory_yoy is not None and inventory_yoy >= 30:
        _add_flag(flags, "notice", "存货增长较快", f"存货同比增长 {inventory_yoy}%。")

    # 经营现金流低于净利润，说明利润现金含量不足，需要大模型进一步解释。
    if operate_cash is not None and net_profit is not None and operate_cash < net_profit:
        _add_flag(
            flags,
            "notice",
            "经营现金流弱于净利润",
            f"经营性现金流量净额 {operate_cash}，净利润 {net_profit}。",
        )

    if net_profit is not None and net_profit < 0:
        _add_flag(flags, "warning", "归母净利润为负", f"最新一期归母净利润为 {net_profit}。")

    if equity is not None and equity <= 0:
        _add_flag(flags, "warning", "净资产非正", f"股东权益合计为 {equity}。")

    if revenue is not None and revenue > 0 and operate_cash is not None and operate_cash < 0:
        _add_flag(flags, "warning", "经营现金流为负", f"营业收入 {revenue}，经营性现金流量净额 {operate_cash}。")

    return flags


def clean_financial_reports(financial_reports: dict[str, Any]) -> dict[str, Any]:
    """把四张财务接口数据清洗成适合大模型分析的摘要。

    清洗原则：
    1. 保留最新一期核心指标，减少大模型需要阅读的数据量。
    2. 保留关键趋势序列，让模型能判断连续变化。
    3. 预先生成风险标记，让模型聚焦解释而不是海量字段搜索。
    4. 原始接口数据不在摘要中全量展开，避免 token 浪费。
    """
    modules = financial_reports.get("modules", {})
    performance_rows = modules.get("performance_report", [])
    balance_rows = modules.get("balance_sheet", [])
    income_rows = modules.get("income_statement", [])
    cashflow_rows = modules.get("cash_flow_statement", [])

    # 取每个模块最新一期数据，用于构造核心财务快照。
    latest_rows = {
        "performance_report": _latest(performance_rows),
        "balance_sheet": _latest(balance_rows),
        "income_statement": _latest(income_rows),
        "cash_flow_statement": _latest(cashflow_rows),
    }
    latest_performance = latest_rows["performance_report"]
    latest_balance = latest_rows["balance_sheet"]
    latest_income = latest_rows["income_statement"]
    latest_cashflow = latest_rows["cash_flow_statement"]

    # 只挑选能支撑财务质量分析的核心字段，避免把完整报表塞给大模型。
    revenue = _raw(latest_performance, "TOTAL_OPERATE_INCOME")
    net_profit = _raw(latest_performance, "PARENT_NETPROFIT")
    deduct_net_profit = _raw(latest_income, "DEDUCT_PARENT_NETPROFIT")
    operating_cash_flow = _raw(latest_cashflow, "NETCASH_OPERATE")
    sales_cash_received = _raw(latest_cashflow, "SALES_SERVICES")
    total_liabilities = _raw(latest_balance, "TOTAL_LIABILITIES")
    total_equity = _raw(latest_balance, "TOTAL_EQUITY")
    accounts_receivable = _raw(latest_balance, "ACCOUNTS_RECE")
    inventory = _raw(latest_balance, "INVENTORY")
    latest_summary = {
        "report_date": latest_performance.get("report_date") or latest_income.get("report_date"),
        "revenue": _round(revenue, 2),
        "revenue_yoy": _round(_raw(latest_performance, "YSTZ")),
        "revenue_qoq": _round(_raw(latest_performance, "YSHZ")),
        "net_profit": _round(net_profit, 2),
        "net_profit_yoy": _round(_raw(latest_performance, "SJLTZ")),
        "net_profit_qoq": _round(_raw(latest_performance, "SJLHZ")),
        "deduct_net_profit": _round(deduct_net_profit, 2),
        "deduct_net_profit_yoy": _round(_raw(latest_income, "DPN_RATIO")),
        "eps": _round(_raw(latest_performance, "BASIC_EPS")),
        "deduct_eps": _round(_raw(latest_performance, "DEDUCT_BASIC_EPS")),
        "bps": _round(_raw(latest_performance, "BPS")),
        "roe": _round(_raw(latest_performance, "WEIGHTAVG_ROE")),
        "gross_margin": _round(_raw(latest_performance, "XSMLL")),
        "net_margin": _ratio(net_profit, revenue),
        "deduct_net_margin": _ratio(deduct_net_profit, revenue),
        "total_assets": _round(_raw(latest_balance, "TOTAL_ASSETS"), 2),
        "total_assets_yoy": _round(_raw(latest_balance, "TOTAL_ASSETS_RATIO")),
        "fixed_asset": _round(_raw(latest_balance, "FIXED_ASSET"), 2),
        "monetary_funds": _round(_raw(latest_balance, "MONETARYFUNDS"), 2),
        "monetary_funds_yoy": _round(_raw(latest_balance, "MONETARYFUNDS_RATIO")),
        "accounts_receivable": _round(accounts_receivable, 2),
        "accounts_receivable_yoy": _round(_raw(latest_balance, "ACCOUNTS_RECE_RATIO")),
        "inventory": _round(inventory, 2),
        "inventory_yoy": _round(_raw(latest_balance, "INVENTORY_RATIO")),
        "accounts_payable": _round(_raw(latest_balance, "ACCOUNTS_PAYABLE"), 2),
        "accounts_payable_yoy": _round(_raw(latest_balance, "ACCOUNTS_PAYABLE_RATIO")),
        "advance_receivables": _round(_raw(latest_balance, "ADVANCE_RECEIVABLES"), 2),
        "advance_receivables_yoy": _round(_raw(latest_balance, "ADVANCE_RECEIVABLES_RATIO")),
        "total_liabilities": _round(total_liabilities, 2),
        "total_liabilities_yoy": _round(_raw(latest_balance, "TOTAL_LIAB_RATIO")),
        "total_equity": _round(total_equity, 2),
        "total_equity_yoy": _round(_raw(latest_balance, "TOTAL_EQUITY_RATIO")),
        "debt_asset_ratio": _round(_raw(latest_balance, "DEBT_ASSET_RATIO")),
        "liability_to_equity": _ratio(total_liabilities, total_equity),
        "accounts_receivable_to_revenue": _ratio(accounts_receivable, revenue),
        "inventory_to_revenue": _ratio(inventory, revenue),
        "operating_expense": _round(_raw(latest_income, "OPERATE_EXPENSE"), 2),
        "operating_expense_yoy": _round(_raw(latest_income, "OPERATE_EXPENSE_RATIO")),
        "sales_expense": _round(_raw(latest_income, "SALE_EXPENSE"), 2),
        "management_expense": _round(_raw(latest_income, "MANAGE_EXPENSE"), 2),
        "finance_expense": _round(_raw(latest_income, "FINANCE_EXPENSE"), 2),
        "total_operating_cost": _round(_raw(latest_income, "TOTAL_OPERATE_COST"), 2),
        "total_operating_cost_yoy": _round(_raw(latest_income, "TOE_RATIO")),
        "operating_profit": _round(_raw(latest_income, "OPERATE_PROFIT"), 2),
        "operating_profit_yoy": _round(_raw(latest_income, "OPERATE_PROFIT_RATIO")),
        "total_profit": _round(_raw(latest_income, "TOTAL_PROFIT"), 2),
        "operating_cash_flow": _round(operating_cash_flow, 2),
        "operating_cash_flow_yoy": _round(_raw(latest_cashflow, "NETCASH_OPERATE_RATIO")),
        "net_cash_flow": _round(_raw(latest_cashflow, "CCE_ADD"), 2),
        "net_cash_flow_yoy": _round(_raw(latest_cashflow, "CCE_ADD_RATIO")),
        "investing_cash_flow": _round(_raw(latest_cashflow, "NETCASH_INVEST"), 2),
        "investing_cash_flow_yoy": _round(_raw(latest_cashflow, "NETCASH_INVEST_RATIO")),
        "financing_cash_flow": _round(_raw(latest_cashflow, "NETCASH_FINANCE"), 2),
        "financing_cash_flow_yoy": _round(_raw(latest_cashflow, "NETCASH_FINANCE_RATIO")),
        "sales_cash_received": _round(sales_cash_received, 2),
        "sales_cash_received_yoy": _round(_raw(latest_cashflow, "SALES_SERVICES_RATIO")),
        "capital_expenditure": _round(_raw(latest_cashflow, "CONSTRUCT_LONG_ASSET"), 2),
        "capital_expenditure_yoy": _round(_raw(latest_cashflow, "CLA_RATIO")),
        "operating_cash_to_net_profit": _ratio(operating_cash_flow, net_profit),
        "sales_cash_to_revenue": _ratio(sales_cash_received, revenue),
    }

    # 趋势数据按报告期保留序列，供模型判断连续改善或恶化。
    trends = {
        "revenue": _period_value(performance_rows, "TOTAL_OPERATE_INCOME", 2),
        "revenue_yoy": _period_value(performance_rows, "YSTZ"),
        "net_profit": _period_value(performance_rows, "PARENT_NETPROFIT", 2),
        "net_profit_yoy": _period_value(performance_rows, "SJLTZ"),
        "deduct_net_profit": _period_value(income_rows, "DEDUCT_PARENT_NETPROFIT", 2),
        "deduct_net_profit_yoy": _period_value(income_rows, "DPN_RATIO"),
        "gross_margin": _period_value(performance_rows, "XSMLL"),
        "net_margin": [
            {
                "report_date": row.get("report_date"),
                "value": _ratio(_raw(row, "PARENT_NETPROFIT"), _raw(row, "TOTAL_OPERATE_INCOME")),
            }
            for row in performance_rows
        ],
        "roe": _period_value(performance_rows, "WEIGHTAVG_ROE"),
        "debt_asset_ratio": _period_value(balance_rows, "DEBT_ASSET_RATIO"),
        "total_equity": _period_value(balance_rows, "TOTAL_EQUITY", 2),
        "accounts_receivable": _period_value(balance_rows, "ACCOUNTS_RECE", 2),
        "inventory": _period_value(balance_rows, "INVENTORY", 2),
        "accounts_payable": _period_value(balance_rows, "ACCOUNTS_PAYABLE", 2),
        "operating_profit": _period_value(income_rows, "OPERATE_PROFIT", 2),
        "total_operating_cost": _period_value(income_rows, "TOTAL_OPERATE_COST", 2),
        "operating_cash_flow": _period_value(cashflow_rows, "NETCASH_OPERATE", 2),
        "operating_cash_flow_yoy": _period_value(cashflow_rows, "NETCASH_OPERATE_RATIO"),
        "net_cash_flow": _period_value(cashflow_rows, "CCE_ADD", 2),
        "capital_expenditure": _period_value(cashflow_rows, "CONSTRUCT_LONG_ASSET", 2),
    }

    return {
        "stock_code": financial_reports.get("stock_code"),
        "source": financial_reports.get("source", "eastmoney"),
        "latest": latest_summary,
        "trends": trends,
        "risk_flags": _build_risk_flags(latest_rows),
        "metadata": {
            "period_count": {
                "performance_report": len(performance_rows),
                "balance_sheet": len(balance_rows),
                "income_statement": len(income_rows),
                "cash_flow_statement": len(cashflow_rows),
            }
        },
    }
