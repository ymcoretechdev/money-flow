from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from utils import format_yen, ensure_parent


LAST_CATEGORY_POSITIONS = {"その他": 1, "未分類": 2}
INVESTMENT_CATEGORY = "投資"
HUSBAND_OWNER = "夫"
WIFE_OWNER = "妻"
COMMON_OWNER = "共通"
INDIVIDUAL_OWNERS = [HUSBAND_OWNER, WIFE_OWNER]
COLUMN_LABELS = {
    "date": "利用日",
    "month": "月",
    "year": "年",
    "transaction_type": "種別",
    "owner": "家計区分",
    "payment_source": "支払元",
    "shop": "利用先",
    "income_source": "収入元",
    "income_type": "収入種別",
    "category": "カテゴリ",
    "amount": "金額",
    "income_amount": "収入",
    "expense_amount": "支出",
    "own_expense_amount": "個人支出",
    "shared_expense_amount": "共通負担",
    "balance": "収支",
    "source_file": "取込ファイル",
}
MONEY_COLUMNS = {
    "amount",
    "income_amount",
    "expense_amount",
    "own_expense_amount",
    "shared_expense_amount",
    "balance",
}

INCOME_TYPE_LABELS = {
    "salary": "給与",
    "bonus": "賞与",
    "other": "その他",
}


def income_type_label(source_file: str) -> str:
    stem = Path(str(source_file)).stem
    return INCOME_TYPE_LABELS.get(stem.lower(), stem)


def sort_category_summary(df: pd.DataFrame, leading_columns: list[str] | None = None) -> pd.DataFrame:
    leading_columns = leading_columns or []

    out = df.copy()
    out["_category_position"] = out["category"].map(LAST_CATEGORY_POSITIONS).fillna(0)
    out = out.sort_values(
        [*leading_columns, "_category_position", "amount"],
        ascending=[True] * len(leading_columns) + [True, False],
    )
    return out.drop(columns="_category_position").reset_index(drop=True)


def build_owner_cashflow(
    income: pd.DataFrame,
    spending: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "month",
        "owner",
        "income_amount",
        "own_expense_amount",
        "shared_expense_amount",
        "expense_amount",
        "balance",
    ]
    months = sorted(set(income["month"]) | set(spending["month"]))
    income_amounts = income.groupby(["month", "owner"])["amount"].sum().to_dict()
    expense_amounts = spending.groupby(["month", "owner"])["amount"].sum().to_dict()
    rows = []

    for month in months:
        common_expense = expense_amounts.get((month, COMMON_OWNER), 0)

        for owner in INDIVIDUAL_OWNERS:
            income_amount = income_amounts.get((month, owner), 0)
            own_expense = expense_amounts.get((month, owner), 0)
            shared_expense = common_expense / 2
            expense_amount = own_expense + shared_expense
            if income_amount or expense_amount:
                rows.append(
                    {
                        "month": month,
                        "owner": owner,
                        "income_amount": income_amount,
                        "own_expense_amount": own_expense,
                        "shared_expense_amount": shared_expense,
                        "expense_amount": expense_amount,
                        "balance": income_amount - expense_amount,
                    }
                )

        common_income = income_amounts.get((month, COMMON_OWNER), 0)
        if common_income or common_expense:
            rows.append(
                {
                    "month": month,
                    "owner": COMMON_OWNER,
                    "income_amount": common_income,
                    "own_expense_amount": 0,
                    "shared_expense_amount": common_expense,
                    "expense_amount": common_expense,
                    "balance": common_income - common_expense,
                }
            )

    monthly = pd.DataFrame(rows, columns=columns)
    if monthly.empty:
        yearly = pd.DataFrame(columns=["year", *columns[1:]])
        return monthly, yearly

    yearly = monthly.copy()
    yearly["year"] = yearly["month"].str[:4]
    yearly = yearly.groupby(["year", "owner"], as_index=False)[
        [
            "income_amount",
            "own_expense_amount",
            "shared_expense_amount",
            "expense_amount",
            "balance",
        ]
    ].sum()
    return monthly, yearly


def build_summaries(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if df.empty:
        empty = pd.DataFrame()
        return {
            "monthly": empty,
            "source_monthly": empty,
            "category_monthly": empty,
            "category_total": empty,
            "investment_monthly": empty,
            "income_monthly": empty,
            "cashflow_monthly": empty,
            "cashflow_yearly": empty,
            "owner_cashflow_monthly": empty,
            "owner_cashflow_yearly": empty,
        }

    work = df.copy()
    work["month"] = work["date"].dt.strftime("%Y-%m")
    expense = work[work["transaction_type"] == "expense"]
    income = work[work["transaction_type"] == "income"]
    spending = expense[expense["category"] != INVESTMENT_CATEGORY]
    investment = expense[expense["category"] == INVESTMENT_CATEGORY]

    monthly = spending.groupby("month", as_index=False)["amount"].sum()
    source_monthly = spending.groupby(
        ["month", "payment_source"], as_index=False
    )["amount"].sum()
    category_monthly = spending.groupby(["month", "category"], as_index=False)["amount"].sum()
    category_total = spending.groupby("category", as_index=False)["amount"].sum()
    investment_monthly = investment.groupby("month", as_index=False)["amount"].sum()
    income_monthly = income.groupby("month", as_index=False)["amount"].sum()
    cashflow_monthly = income_monthly.rename(
        columns={"amount": "income_amount"}
    ).merge(
        monthly.rename(columns={"amount": "expense_amount"}),
        on="month",
        how="outer",
    )
    cashflow_monthly[["income_amount", "expense_amount"]] = cashflow_monthly[
        ["income_amount", "expense_amount"]
    ].fillna(0).astype(int)
    cashflow_monthly["balance"] = (
        cashflow_monthly["income_amount"] - cashflow_monthly["expense_amount"]
    )
    cashflow_monthly = cashflow_monthly.sort_values("month").reset_index(drop=True)

    cashflow_yearly = cashflow_monthly.copy()
    cashflow_yearly["year"] = cashflow_yearly["month"].str[:4]
    cashflow_yearly = cashflow_yearly.groupby("year", as_index=False)[
        ["income_amount", "expense_amount", "balance"]
    ].sum()
    owner_cashflow_monthly, owner_cashflow_yearly = build_owner_cashflow(
        income,
        spending,
    )

    return {
        "monthly": monthly,
        "source_monthly": source_monthly,
        "category_monthly": sort_category_summary(category_monthly, ["month"]),
        "category_total": sort_category_summary(category_total),
        "investment_monthly": investment_monthly,
        "income_monthly": income_monthly,
        "cashflow_monthly": cashflow_monthly,
        "cashflow_yearly": cashflow_yearly,
        "owner_cashflow_monthly": owner_cashflow_monthly,
        "owner_cashflow_yearly": owner_cashflow_yearly,
    }


def yen_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in MONEY_COLUMNS.intersection(out.columns):
        out[column] = out[column].apply(format_yen)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def df_to_html_table(
    df: pd.DataFrame,
    table_id: str,
    row_attributes: dict[str, str | object] | None = None,
    empty_message: str = "データがありません。",
    amount_column: str = "amount",
) -> str:
    if df.empty:
        return f"<p class='empty'>{html.escape(empty_message)}</p>"

    row_attributes = row_attributes or {}
    formatted = yen_table(df)
    headers = "".join(
        f"<th>{html.escape(COLUMN_LABELS.get(str(column), str(column)))}</th>"
        for column in formatted.columns
    )
    rows = []

    for (_, raw_row), (_, display_row) in zip(df.iterrows(), formatted.iterrows()):
        attributes = [f'data-amount="{int(raw_row[amount_column])}"']
        for attribute_name, source in row_attributes.items():
            value = source(raw_row) if callable(source) else raw_row[source]
            escaped_value = html.escape(str(value), quote=True)
            attributes.append(f'data-{attribute_name}="{escaped_value}"')

        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in display_row)
        rows.append(f"<tr {' '.join(attributes)}>{cells}</tr>")

    return (
        f'<table class="dataframe data-table" id="{html.escape(table_id, quote=True)}">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def filter_toolbar(
    table_id: str,
    filters: list[tuple[str, str, list[str]]],
    row_count: int,
    total: int,
    count_unit: str = "行",
    page_size: int | None = None,
) -> str:
    fields = []
    for filter_name, label, options in filters:
        option_html = ['<option value="">全て</option>']
        for option in options:
            escaped_option = html.escape(str(option), quote=True)
            option_html.append(
                f'<option value="{escaped_option}">{escaped_option}</option>'
            )
        select_id = f"{table_id}-{filter_name}-filter"
        fields.append(
            '<div class="filter-field">'
            f'<label for="{select_id}">{html.escape(label)}</label>'
            f'<select id="{select_id}" data-filter-table="{table_id}" '
            f'data-filter-name="{filter_name}">{"".join(option_html)}</select>'
            "</div>"
        )

    pagination = ""
    if page_size:
        pagination = (
            f'<div class="pagination" data-pagination="{table_id}" '
            f'data-page-size="{page_size}">'
            '<button type="button" data-page-action="previous" '
            'aria-label="前のページ" title="前のページ">&#8249;</button>'
            '<span data-page-status>1 / 1</span>'
            '<button type="button" data-page-action="next" '
            'aria-label="次のページ" title="次のページ">&#8250;</button>'
            "</div>"
        )

    return (
        '<div class="filter-toolbar">'
        f'<div class="filter-fields">{"".join(fields)}</div>'
        '<div class="filter-meta">'
        f'<div class="filter-result" data-filter-result="{table_id}" '
        f'data-count-unit="{html.escape(count_unit, quote=True)}">'
        f"{row_count:,}{html.escape(count_unit)} / {format_yen(total)}</div>"
        f"{pagination}</div>"
        "</div>"
    )


def generate_html_report(df: pd.DataFrame, output_path: Path) -> None:
    ensure_parent(output_path)
    summaries = build_summaries(df)
    expense = df[df["transaction_type"] == "expense"] if not df.empty else df
    income = df[df["transaction_type"] == "income"] if not df.empty else df
    spending = expense[expense["category"] != INVESTMENT_CATEGORY]
    investment = expense[expense["category"] == INVESTMENT_CATEGORY]
    spending_total = int(spending["amount"].sum()) if not spending.empty else 0
    investment_total = int(investment["amount"].sum()) if not investment.empty else 0
    income_total = int(income["amount"].sum()) if not income.empty else 0
    expense_total = spending_total + investment_total
    balance = income_total - spending_total
    count = len(df)

    detail = expense.copy()
    if not detail.empty:
        detail = detail[
            [
                "date",
                "owner",
                "payment_source",
                "shop",
                "category",
                "amount",
                "source_file",
            ]
        ]
        detail = detail.sort_values("date", ascending=False)

    income_detail = income.copy()
    if not income_detail.empty:
        income_detail["income_type"] = income_detail["source_file"].apply(income_type_label)
        income_detail = income_detail[
            ["date", "owner", "income_type", "shop", "amount", "source_file"]
        ]
        income_detail = income_detail.rename(columns={"shop": "income_source"})
        income_detail = income_detail.sort_values("date", ascending=False)

    months = (
        sorted(expense["date"].dt.strftime("%Y-%m").unique(), reverse=True)
        if not expense.empty
        else []
    )
    years = sorted({month[:4] for month in months}, reverse=True)
    income_months = (
        sorted(income["date"].dt.strftime("%Y-%m").unique(), reverse=True)
        if not income.empty
        else []
    )
    income_years = sorted({month[:4] for month in income_months}, reverse=True)
    cashflow_years = (
        sorted(
            {month[:4] for month in summaries["cashflow_monthly"]["month"]},
            reverse=True,
        )
        if not summaries["cashflow_monthly"].empty
        else []
    )
    owner_cashflow_years = (
        sorted(
            {
                month[:4]
                for month in summaries["owner_cashflow_monthly"]["month"]
            },
            reverse=True,
        )
        if not summaries["owner_cashflow_monthly"].empty
        else []
    )
    owner_options = [
        owner
        for owner in [HUSBAND_OWNER, WIFE_OWNER, COMMON_OWNER]
        if not df.empty and owner in set(df["owner"])
    ]
    owner_balances = (
        summaries["owner_cashflow_monthly"].groupby("owner")["balance"].sum().to_dict()
        if not summaries["owner_cashflow_monthly"].empty
        else {}
    )
    payment_sources = (
        sorted(expense["payment_source"].astype(str).unique())
        if not expense.empty
        else []
    )
    income_sources = (
        sorted(income["shop"].astype(str).unique()) if not income.empty else []
    )
    income_types = (
        sorted({income_type_label(source_file) for source_file in income["source_file"]})
        if not income.empty
        else []
    )
    spending_categories = (
        summaries["category_total"]["category"].astype(str).tolist()
        if not summaries["category_total"].empty
        else []
    )
    categories = spending_categories.copy()
    if not investment.empty:
        special_position = next(
            (index for index, category in enumerate(categories) if category in LAST_CATEGORY_POSITIONS),
            len(categories),
        )
        categories.insert(special_position, INVESTMENT_CATEGORY)

    cashflow_chart_rows = [
        {
            "month": str(row["month"]),
            "income": float(row["income_amount"]),
            "expense": float(row["expense_amount"]),
        }
        for _, row in summaries["cashflow_monthly"].iterrows()
    ]

    income_chart_rows = []
    income_chart_owners = []
    income_chart_series = []
    if not income.empty:
        income_chart = income.assign(
            month=income["date"].dt.strftime("%Y-%m"),
            income_type=income["source_file"].apply(income_type_label),
        ).groupby(["month", "owner", "income_type"], as_index=False)["amount"].sum()
        owners_in_chart = set(income_chart["owner"].astype(str))
        income_chart_owners = [
            owner
            for owner in [HUSBAND_OWNER, WIFE_OWNER, COMMON_OWNER]
            if owner in owners_in_chart
        ]
        income_type_totals = (
            income_chart.groupby("income_type")["amount"].sum().sort_values(ascending=False)
        )
        income_type_order = income_type_totals.index.tolist()
        income_chart_series = [
            {"owner": owner, "incomeType": income_type}
            for owner in income_chart_owners
            for income_type in income_type_order
            if not income_chart[
                (income_chart["owner"] == owner)
                & (income_chart["income_type"] == income_type)
            ].empty
        ]
        income_chart_rows = [
            {
                "month": str(row["month"]),
                "owner": str(row["owner"]),
                "incomeType": str(row["income_type"]),
                "amount": float(row["amount"]),
            }
            for _, row in income_chart.iterrows()
        ]

    category_chart = summaries["category_monthly"].copy()
    chart_categories = []
    category_chart_rows = []
    grouped_categories = []
    if not category_chart.empty:
        category_totals = (
            category_chart.groupby("category")["amount"].sum().abs().sort_values(
                ascending=False
            )
        )
        reserved_categories = [
            category
            for category in [
                "医療費",
                "育児",
                "外食",
                "娯楽",
                "未分類",
                "その他",
            ]
            if category in category_totals.index
        ]
        top_categories = (
            category_totals.drop(index=reserved_categories, errors="ignore")
            .head(10)
            .index.tolist()
        )
        preserved_categories = set(top_categories) | set(reserved_categories)
        grouped_categories = [
            str(category)
            for category in category_totals.index
            if category not in preserved_categories
        ]
        category_chart["chart_category"] = category_chart["category"].where(
            category_chart["category"].isin(preserved_categories),
            "その他カテゴリ",
        )
        category_chart = category_chart.groupby(
            ["month", "chart_category"], as_index=False
        )["amount"].sum()
        chart_categories = top_categories.copy()
        chart_categories.extend(
            category
            for category in reserved_categories
            if category not in {"未分類", "その他"}
        )
        if "未分類" in reserved_categories:
            chart_categories.append("未分類")
        if "その他カテゴリ" in set(category_chart["chart_category"]):
            chart_categories.append("その他カテゴリ")
        if "その他" in reserved_categories:
            chart_categories.append("その他")
        category_chart_rows = [
            {
                "month": str(row["month"]),
                "category": str(row["chart_category"]),
                "amount": float(row["amount"]),
            }
            for _, row in category_chart.iterrows()
        ]

    detail_category_groups = {"生活支出": spending_categories}
    if grouped_categories:
        detail_category_groups["その他カテゴリ"] = grouped_categories
    categories.insert(0, "生活支出")
    if grouped_categories:
        grouped_position = next(
            (
                index
                for index, category in enumerate(categories)
                if category in LAST_CATEGORY_POSITIONS
            ),
            len(categories),
        )
        categories.insert(grouped_position, "その他カテゴリ")

    chart_data_json = json.dumps(
        {
            "cashflow": cashflow_chart_rows,
            "income": income_chart_rows,
            "incomeOwners": income_chart_owners,
            "incomeSeries": income_chart_series,
            "categorySpending": category_chart_rows,
            "categories": chart_categories,
            "detailCategoryGroups": detail_category_groups,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    chart_year_options = ['<option value="">全て</option>']
    for index, year in enumerate(cashflow_years):
        selected = " selected" if index == 0 else ""
        chart_year_options.append(
            f'<option value="{html.escape(year, quote=True)}"{selected}>'
            f"{html.escape(year)}</option>"
        )

    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>家計収支レポート</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; background: #f7f8fb; color: #222; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; border-left: 6px solid #3367d6; padding-left: 10px; }}
    h3 {{ margin: 24px 0 12px; font-size: 18px; }}
    h4 {{ margin: 20px 0 10px; color: #475569; font-size: 14px; }}
    .section-note {{ margin: -4px 0 18px; color: #64748b; font-size: 13px; }}
    .summary-group {{ margin-top: 24px; }}
    .summary-group h3 {{ margin-bottom: 10px; }}
    .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
    .summary-group .summary {{ margin-top: 0; }}
    .card {{ background: white; border-radius: 6px; padding: 18px 22px; box-shadow: 0 2px 10px rgba(0,0,0,.06); min-width: 180px; }}
    .label {{ color: #666; font-size: 14px; }}
    .value {{ font-size: 26px; font-weight: 700; margin-top: 6px; }}
    .data-table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 2px 10px rgba(0,0,0,.04); }}
    .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px 10px; font-size: 14px; }}
    .data-table th {{ background: #eef3ff; text-align: left; }}
    .data-table tr:nth-child(even) {{ background: #fafafa; }}
    .filter-toolbar {{ display: flex; align-items: end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin: 0 0 12px; }}
    .filter-fields {{ display: flex; align-items: end; gap: 12px; flex-wrap: wrap; }}
    .filter-meta {{ display: flex; align-items: center; justify-content: flex-end; gap: 16px; flex-wrap: wrap; }}
    .filter-field {{ display: grid; gap: 6px; min-width: 220px; }}
    .filter-field label {{ color: #555; font-size: 13px; font-weight: 600; }}
    .filter-field select {{ min-height: 40px; padding: 8px 34px 8px 10px; border: 1px solid #aeb7c6; border-radius: 4px; background: white; color: #222; font: inherit; }}
    .filter-result {{ color: #555; font-size: 14px; font-variant-numeric: tabular-nums; }}
    .pagination {{ display: flex; align-items: center; gap: 8px; color: #555; font-size: 14px; font-variant-numeric: tabular-nums; }}
    .pagination button {{ width: 36px; height: 36px; border: 1px solid #aeb7c6; border-radius: 4px; background: white; color: #222; font-size: 24px; line-height: 1; cursor: pointer; }}
    .pagination button:disabled {{ color: #a0a6af; background: #f1f2f4; cursor: default; }}
    .report-nav {{ position: sticky; top: 0; z-index: 10; display: flex; align-items: center; gap: 4px; margin: 20px -32px 24px; padding: 10px 32px; background: rgba(247, 248, 251, 0.96); border-top: 1px solid #dfe3ea; border-bottom: 1px solid #dfe3ea; backdrop-filter: blur(8px); }}
    .nav-group {{ position: relative; flex: 0 0 auto; }}
    .report-nav a {{ display: block; padding: 7px 10px; border-radius: 4px; color: #334155; font-size: 13px; font-weight: 600; text-decoration: none; white-space: nowrap; }}
    .nav-group > a::after {{ content: '▼'; margin-left: 6px; color: #64748b; font-size: 9px; }}
    .report-nav a:hover, .report-nav a:focus-visible {{ background: #e2e8f0; color: #111827; outline: none; }}
    .nav-submenu {{ position: absolute; top: 100%; left: 0; display: none; min-width: 180px; padding: 6px; background: white; border: 1px solid #cbd5e1; border-radius: 6px; box-shadow: 0 8px 24px rgba(15, 23, 42, .14); }}
    .nav-submenu a {{ padding: 9px 10px; font-weight: 500; }}
    .nav-group:nth-last-child(-n+2) .nav-submenu {{ right: 0; left: auto; }}
    .nav-group:hover .nav-submenu, .nav-group:focus-within .nav-submenu {{ display: block; }}
    h2[id], h3[id], h4[id] {{ scroll-margin-top: 72px; }}
    .chart-toolbar {{ display: flex; align-items: end; gap: 12px; margin-bottom: 16px; }}
    .chart-toolbar.compact {{ margin: -4px 0 12px; }}
    .chart-grid {{ display: grid; gap: 20px; }}
    .chart-panel {{ min-width: 0; background: white; border: 1px solid #dfe3ea; border-radius: 6px; padding: 16px; }}
    .chart-panel h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .chart-scroll {{ width: 100%; max-width: 100%; overflow-x: auto; overflow-y: hidden; scrollbar-gutter: stable; }}
    .chart-scroll svg {{ display: block; min-width: 100%; }}
    .chart-drilldown {{ cursor: pointer; transition: opacity .15s ease, filter .15s ease; }}
    .chart-drilldown:hover {{ filter: brightness(.9); }}
    .chart-drilldown:focus {{ outline: none; opacity: .72; stroke: #111827; stroke-width: 2; }}
    .chart-legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin: 0 0 12px; color: #4b5563; font-size: 13px; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
    .legend-swatch {{ width: 12px; height: 12px; border-radius: 2px; flex: 0 0 auto; }}
    .empty {{ background: white; padding: 16px; border-radius: 8px; }}
    .note {{ color: #666; font-size: 13px; }}
    @media (max-width: 640px) {{ body {{ margin: 18px; }} .report-nav {{ flex-wrap: wrap; margin-right: -18px; margin-left: -18px; padding-right: 18px; padding-left: 18px; }} .filter-fields, .filter-field {{ width: 100%; }} }}
  </style>
</head>
<body>
  <h1>家計収支レポート</h1>
  <p class="note">CSVを読み込んで自動生成したローカルHTMLレポートです。</p>

  <nav class="report-nav" aria-label="レポート目次">
    <div class="nav-group">
      <a href="#overview">概要</a>
      <div class="nav-submenu">
        <a href="#monthly-trends">月別推移</a>
        <a href="#balance-summary">収支</a>
        <a href="#total-summary">全期間の合計</a>
      </div>
    </div>
    <div class="nav-group">
      <a href="#cashflow">収支</a>
      <div class="nav-submenu">
        <a href="#household-cashflow">世帯全体</a>
        <a href="#owner-cashflow">夫・妻・共通</a>
      </div>
    </div>
    <div class="nav-group">
      <a href="#income">収入</a>
      <div class="nav-submenu"><a href="#monthly-income">月ごとの収入</a></div>
    </div>
    <div class="nav-group">
      <a href="#expenses">支出</a>
      <div class="nav-submenu">
        <a href="#monthly-expenses">月ごとの合計</a>
        <a href="#category-expenses">カテゴリごと</a>
        <a href="#source-expenses">支払元ごと</a>
      </div>
    </div>
    <div class="nav-group">
      <a href="#investments">投資</a>
      <div class="nav-submenu"><a href="#monthly-investments">月ごとの投資</a></div>
    </div>
    <div class="nav-group">
      <a href="#details">明細</a>
      <div class="nav-submenu">
        <a href="#income-details">収入明細</a>
        <a href="#expense-details">支出明細</a>
      </div>
    </div>
  </nav>

  <h2 id="overview">概要</h2>
  <p class="section-note">読み込んだ全期間の合計と、月ごとの推移です。</p>
  <h3 id="monthly-trends">月別推移</h3>
  <div class="chart-toolbar">
    <div class="filter-field">
      <label for="chart-year-filter">年</label>
      <select id="chart-year-filter">{''.join(chart_year_options)}</select>
    </div>
  </div>
  <div class="chart-grid">
    <section class="chart-panel">
      <h3>収入と支出</h3>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-swatch" style="background:#059669"></span>収入</span>
        <span class="legend-item"><span class="legend-swatch" style="background:#e11d48"></span>支出</span>
      </div>
      <div class="chart-scroll"><svg id="cashflow-chart" role="img" aria-label="月別の収入と支出"></svg></div>
    </section>
    <section class="chart-panel">
      <h3>夫・妻別の収入内訳</h3>
      <div class="chart-legend" id="income-chart-legend"></div>
      <div class="chart-scroll"><svg id="income-chart" role="img" aria-label="月別の家計区分・種別別収入"></svg></div>
    </section>
    <section class="chart-panel">
      <h3>カテゴリ別支出</h3>
      <div class="chart-toolbar compact">
        <div class="filter-field">
          <label for="category-chart-category-filter">カテゴリ</label>
          <select id="category-chart-category-filter"><option value="">全て</option></select>
        </div>
      </div>
      <div class="chart-legend" id="category-chart-legend"></div>
      <div class="chart-scroll"><svg id="category-chart" role="img" aria-label="月別のカテゴリ別支出"></svg></div>
    </section>
  </div>
  <script type="application/json" id="chart-data">{chart_data_json}</script>

  <div class="summary-group">
    <h3 id="balance-summary">収支</h3>
    <div class="summary">
      <div class="card"><div class="label">世帯全体</div><div class="value">{format_yen(balance)}</div></div>
      <div class="card"><div class="label">夫</div><div class="value">{format_yen(owner_balances.get(HUSBAND_OWNER, 0))}</div></div>
      <div class="card"><div class="label">妻</div><div class="value">{format_yen(owner_balances.get(WIFE_OWNER, 0))}</div></div>
      <div class="card"><div class="label">共通</div><div class="value">{format_yen(owner_balances.get(COMMON_OWNER, 0))}</div></div>
    </div>
  </div>
  <div class="summary-group">
    <h3 id="total-summary">全期間の合計</h3>
    <div class="summary">
      <div class="card"><div class="label">収入</div><div class="value">{format_yen(income_total)}</div></div>
      <div class="card"><div class="label">生活支出</div><div class="value">{format_yen(spending_total)}</div></div>
      <div class="card"><div class="label">投資</div><div class="value">{format_yen(investment_total)}</div></div>
      <div class="card"><div class="label">明細件数</div><div class="value">{count:,}件</div></div>
    </div>
  </div>

  <h2 id="cashflow">収支</h2>
  <p class="section-note">生活支出を収入から差し引いた金額です。共通支出は夫・妻に半分ずつ配分します。</p>
  <h3 id="household-cashflow">世帯全体</h3>
  <h4>年ごと</h4>
  {filter_toolbar('cashflow-yearly-table', [], len(summaries['cashflow_yearly']), balance)}
  {df_to_html_table(summaries['cashflow_yearly'], 'cashflow-yearly-table', amount_column='balance')}

  <h4>月ごと</h4>
  {filter_toolbar('cashflow-monthly-table', [('year', '年', cashflow_years)], len(summaries['cashflow_monthly']), balance)}
  {df_to_html_table(summaries['cashflow_monthly'], 'cashflow-monthly-table', {'year': lambda row: str(row['month'])[:4]}, amount_column='balance')}

  <h3 id="owner-cashflow">夫・妻・共通</h3>
  <h4>年ごと</h4>
  {filter_toolbar('owner-cashflow-yearly-table', [('owner', '家計区分', owner_options)], len(summaries['owner_cashflow_yearly']), int(summaries['owner_cashflow_yearly']['balance'].sum()) if not summaries['owner_cashflow_yearly'].empty else 0)}
  {df_to_html_table(summaries['owner_cashflow_yearly'], 'owner-cashflow-yearly-table', {'owner': 'owner'}, amount_column='balance')}

  <h4>月ごと</h4>
  {filter_toolbar('owner-cashflow-monthly-table', [('year', '年', owner_cashflow_years), ('owner', '家計区分', owner_options)], len(summaries['owner_cashflow_monthly']), int(summaries['owner_cashflow_monthly']['balance'].sum()) if not summaries['owner_cashflow_monthly'].empty else 0)}
  {df_to_html_table(summaries['owner_cashflow_monthly'], 'owner-cashflow-monthly-table', {'year': lambda row: str(row['month'])[:4], 'owner': 'owner'}, amount_column='balance')}

  <h2 id="income">収入</h2>
  <p class="section-note">給与や賞与など、手入力した収入の月別合計です。</p>
  <h3 id="monthly-income">月ごとの収入</h3>
  {filter_toolbar('income-monthly-table', [('year', '年', income_years)], len(summaries['income_monthly']), income_total)}
  {df_to_html_table(summaries['income_monthly'], 'income-monthly-table', {'year': lambda row: str(row['month'])[:4]}, '収入データがありません。')}

  <h2 id="expenses">支出</h2>
  <p class="section-note">投資を除いた生活支出を、月・カテゴリ・支払元の順に確認できます。</p>
  <h3 id="monthly-expenses">月ごとの合計</h3>
  {filter_toolbar('monthly-table', [('year', '年', years)], len(summaries['monthly']), spending_total)}
  {df_to_html_table(summaries['monthly'], 'monthly-table', {'year': lambda row: str(row['month'])[:4]})}

  <h3 id="category-expenses">カテゴリごとの支出</h3>
  <h4>全期間の合計</h4>
  {filter_toolbar('category-total-table', [('category', 'カテゴリ', spending_categories)], len(summaries['category_total']), spending_total)}
  {df_to_html_table(summaries['category_total'], 'category-total-table', {'category': 'category'})}

  <h4>月ごとの内訳</h4>
  {filter_toolbar('category-monthly-table', [('month', '月', months), ('category', 'カテゴリ', spending_categories)], len(summaries['category_monthly']), spending_total)}
  {df_to_html_table(summaries['category_monthly'], 'category-monthly-table', {'month': 'month', 'category': 'category'})}

  <h3 id="source-expenses">支払元ごとの支出</h3>
  {filter_toolbar('source-monthly-table', [('source', '支払元', payment_sources)], len(summaries['source_monthly']), spending_total)}
  {df_to_html_table(summaries['source_monthly'], 'source-monthly-table', {'source': 'payment_source'})}

  <h2 id="investments">投資</h2>
  <p class="section-note">生活支出とは分けて集計しています。</p>
  <h3 id="monthly-investments">月ごとの投資</h3>
  {filter_toolbar('investment-monthly-table', [('year', '年', years)], len(summaries['investment_monthly']), investment_total)}
  {df_to_html_table(summaries['investment_monthly'], 'investment-monthly-table', {'year': lambda row: str(row['month'])[:4]}, '投資データがありません。')}

  <h2 id="details">明細</h2>
  <p class="section-note">個々の取引を絞り込んで確認できます。</p>
  <h3 id="income-details">収入明細</h3>
  {filter_toolbar('income-detail-table', [('month', '月', income_months), ('owner', '家計区分', owner_options), ('income_type', '収入種別', income_types), ('source', '収入元', income_sources)], len(income_detail), income_total, '件', 100)}
  {df_to_html_table(income_detail, 'income-detail-table', {'month': lambda row: row['date'].strftime('%Y-%m'), 'owner': 'owner', 'income_type': 'income_type', 'source': 'income_source'}, '収入データがありません。')}

  <h3 id="expense-details">支出明細</h3>
  {filter_toolbar('detail-table', [('month', '月', months), ('owner', '家計区分', owner_options), ('source', '支払元', payment_sources), ('category', 'カテゴリ', categories)], len(detail), expense_total, '件', 100)}
  {df_to_html_table(detail, 'detail-table', {'month': lambda row: row['date'].strftime('%Y-%m'), 'owner': 'owner', 'source': 'payment_source', 'category': 'category'})}
  <script>
    const chartData = JSON.parse(document.getElementById('chart-data').textContent);
    const chartPalette = [
      '#2563eb', '#059669', '#d97706', '#0891b2', '#65a30d',
      '#4f46e5', '#ea580c', '#0f766e', '#92400e', '#0369a1'
    ];
    const incomeOwnerColors = {{
      '夫': '#2563eb',
      '妻': '#db2777',
      '共通': '#64748b'
    }};
    const incomeOwnerPalettes = {{
      '夫': ['#1d4ed8', '#60a5fa', '#0f766e', '#38bdf8'],
      '妻': ['#db2777', '#f472b6', '#9333ea', '#c084fc'],
      '共通': ['#64748b', '#94a3b8', '#475569', '#cbd5e1']
    }};
    const specialCategoryColors = {{
      '医療費': '#0d9488',
      '育児': '#f59e0b',
      '外食': '#e11d48',
      '娯楽': '#7c3aed',
      'その他カテゴリ': '#64748b',
      'その他': '#cbd5e1',
      '未分類': '#a8a29e'
    }};
    const svgNamespace = 'http://www.w3.org/2000/svg';

    function categoryColor(category) {{
      return specialCategoryColors[category]
        || chartPalette[chartData.categories.indexOf(category) % chartPalette.length];
    }}

    function incomeOwnerColor(owner) {{
      return incomeOwnerColors[owner] || '#64748b';
    }}

    function incomeSeriesKey(series) {{
      return `${{series.owner}}|${{series.incomeType}}`;
    }}

    function incomeSeriesColor(series) {{
      const sameOwnerSeries = chartData.incomeSeries.filter(item => item.owner === series.owner);
      const index = sameOwnerSeries.findIndex(item => item.incomeType === series.incomeType);
      const palette = incomeOwnerPalettes[series.owner] || ['#64748b'];
      return palette[Math.max(index, 0) % palette.length];
    }}

    function createSvgElement(tag, attributes = {{}}, text = '') {{
      const element = document.createElementNS(svgNamespace, tag);
      Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
      if (text) element.textContent = text;
      return element;
    }}

    function addBarTitle(bar, text) {{
      bar.appendChild(createSvgElement('title', {{}}, text));
    }}

    function makeBarInteractive(bar, label, callback) {{
      bar.setAttribute('class', 'chart-drilldown');
      bar.setAttribute('tabindex', '0');
      bar.setAttribute('role', 'link');
      bar.setAttribute('aria-label', `${{label}}の明細を表示`);
      bar.addEventListener('click', callback);
      bar.addEventListener('keydown', (event) => {{
        if (event.key === 'Enter' || event.key === ' ') {{
          event.preventDefault();
          callback();
        }}
      }});
    }}

    function showFilteredDetails(tableId, headingId, values) {{
      document.querySelectorAll(`[data-filter-table="${{tableId}}"]`).forEach((filter) => {{
        filter.value = values[filter.dataset.filterName] || '';
      }});
      applyTableFilters(tableId);
      document.getElementById(headingId).scrollIntoView({{
        behavior: 'smooth', block: 'start'
      }});
    }}

    function formatChartYen(value) {{
      return new Intl.NumberFormat('ja-JP', {{
        style: 'currency', currency: 'JPY', maximumFractionDigits: 1
      }}).format(value);
    }}

    function formatCompactYen(value) {{
      return new Intl.NumberFormat('ja-JP', {{
        notation: 'compact', maximumFractionDigits: 1
      }}).format(value);
    }}

    function drawEmptyChart(svg, width, height) {{
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      svg.appendChild(createSvgElement('text', {{
        x: width / 2, y: height / 2, 'text-anchor': 'middle', fill: '#6b7280'
      }}, 'データがありません'));
    }}

    function drawYAxis(svg, width, top, bottom, left, maximum, minimum = 0) {{
      const plotHeight = bottom - top;
      const range = maximum - minimum || 1;
      for (let index = 0; index <= 5; index += 1) {{
        const value = maximum - (range * index / 5);
        const y = top + (plotHeight * index / 5);
        svg.appendChild(createSvgElement('line', {{
          x1: left, y1: y, x2: width - 20, y2: y, stroke: '#e5e7eb'
        }}));
        svg.appendChild(createSvgElement('text', {{
          x: left - 8, y: y + 4, 'text-anchor': 'end', fill: '#6b7280',
          'font-size': 11
        }}, formatCompactYen(value)));
      }}
    }}

    function renderCashflowChart(year) {{
      const svg = document.getElementById('cashflow-chart');
      svg.replaceChildren();
      const rows = chartData.cashflow.filter(row => !year || row.month.startsWith(year));
      const width = Math.max(760, rows.length * 72 + 100);
      const height = 340;
      const left = 72;
      const top = 20;
      const bottom = 285;
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      if (!rows.length) {{ drawEmptyChart(svg, width, height); return; }}

      const maximum = Math.max(1, ...rows.flatMap(row => [row.income, row.expense]));
      drawYAxis(svg, width, top, bottom, left, maximum);
      const scale = (bottom - top) / maximum;
      const groupWidth = (width - left - 20) / rows.length;
      const barWidth = Math.min(24, Math.max(10, groupWidth * 0.3));

      rows.forEach((row, index) => {{
        const center = left + groupWidth * (index + 0.5);
        [
          {{ key: 'income', color: '#059669', offset: -barWidth - 2, label: '収入' }},
          {{ key: 'expense', color: '#e11d48', offset: 2, label: '支出' }}
        ].forEach(series => {{
          const value = row[series.key];
          const barHeight = Math.max(0, value * scale);
          const bar = createSvgElement('rect', {{
            x: center + series.offset,
            y: bottom - barHeight,
            width: barWidth,
            height: barHeight,
            fill: series.color,
            rx: 2
          }});
          const label = `${{row.month}} ${{series.label}} ${{formatChartYen(value)}}`;
          addBarTitle(bar, label);
          makeBarInteractive(bar, label, () => {{
            if (series.key === 'income') {{
              showFilteredDetails('income-detail-table', 'income-details', {{
                month: row.month
              }});
            }} else {{
              showFilteredDetails('detail-table', 'expense-details', {{
                month: row.month,
                category: '生活支出'
              }});
            }}
          }});
          svg.appendChild(bar);
        }});
        svg.appendChild(createSvgElement('text', {{
          x: center, y: bottom + 22, 'text-anchor': 'middle', fill: '#4b5563',
          'font-size': 11
        }}, row.month));
      }});
    }}

    function renderIncomeChart(year) {{
      const svg = document.getElementById('income-chart');
      const legend = document.getElementById('income-chart-legend');
      svg.replaceChildren();
      legend.replaceChildren();
      const rows = chartData.income.filter(row => !year || row.month.startsWith(year));
      const months = [...new Set(rows.map(row => row.month))].sort();
      const visibleSeries = chartData.incomeSeries.filter(
        series => rows.some(row =>
          row.owner === series.owner
          && row.incomeType === series.incomeType
          && row.amount !== 0
        )
      );
      const width = Math.max(760, months.length * 64 + 100);
      const height = 340;
      const left = 72;
      const top = 20;
      const bottom = 285;
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      if (!rows.length) {{ drawEmptyChart(svg, width, height); return; }}

      const valuesByMonth = new Map();
      months.forEach(month => valuesByMonth.set(month, new Map()));
      rows.forEach(row => valuesByMonth.get(row.month).set(`${{row.owner}}|${{row.incomeType}}`, row.amount));
      const totals = months.map(month =>
        [...valuesByMonth.get(month).values()].reduce((total, value) => total + value, 0)
      );
      const maximum = Math.max(1, ...totals);
      drawYAxis(svg, width, top, bottom, left, maximum);
      const scale = (bottom - top) / maximum;
      const groupWidth = (width - left - 20) / months.length;
      const barWidth = Math.min(38, Math.max(16, groupWidth * 0.58));

      visibleSeries.forEach(series => {{
        const item = document.createElement('span');
        item.className = 'legend-item';
        const swatch = document.createElement('span');
        swatch.className = 'legend-swatch';
        swatch.style.background = incomeSeriesColor(series);
        item.append(swatch, document.createTextNode(`${{series.owner}} / ${{series.incomeType}}`));
        legend.appendChild(item);
      }});

      months.forEach((month, index) => {{
        const center = left + groupWidth * (index + 0.5);
        let offset = 0;
        visibleSeries.forEach(series => {{
          const value = valuesByMonth.get(month).get(incomeSeriesKey(series)) || 0;
          if (!value) return;
          const barHeight = Math.max(0, value * scale);
          const bar = createSvgElement('rect', {{
            x: center - barWidth / 2,
            y: bottom - (offset + value) * scale,
            width: barWidth,
            height: barHeight,
            fill: incomeSeriesColor(series)
          }});
          const label = `${{month}} ${{series.owner}} / ${{series.incomeType}} ${{formatChartYen(value)}}`;
          addBarTitle(bar, label);
          makeBarInteractive(bar, label, () => {{
            showFilteredDetails('income-detail-table', 'income-details', {{
              month,
              owner: series.owner,
              income_type: series.incomeType
            }});
          }});
          svg.appendChild(bar);
          offset += value;
        }});
        svg.appendChild(createSvgElement('text', {{
          x: center, y: bottom + 22, 'text-anchor': 'middle', fill: '#4b5563',
          'font-size': 11
        }}, month));
      }});
    }}

    function renderCategoryChart(year, selectedCategory) {{
      const svg = document.getElementById('category-chart');
      const legend = document.getElementById('category-chart-legend');
      svg.replaceChildren();
      legend.replaceChildren();
      const allRowsForYear = chartData.categorySpending.filter(
        row => !year || row.month.startsWith(year)
      );
      const rows = chartData.categorySpending.filter(
        row => (!year || row.month.startsWith(year))
          && (!selectedCategory || row.category === selectedCategory)
      );
      const months = [...new Set(allRowsForYear.map(row => row.month))].sort();
      const visibleCategories = chartData.categories.filter(
        category => (!selectedCategory || category === selectedCategory)
          && (
            selectedCategory === category
            || rows.some(row => row.category === category && row.amount !== 0)
          )
      );
      const width = Math.max(760, months.length * 64 + 100);
      const height = 340;
      const left = 72;
      const top = 20;
      const bottom = 285;
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      svg.setAttribute('width', width);
      svg.setAttribute('height', height);
      if (!months.length || !visibleCategories.length) {{ drawEmptyChart(svg, width, height); return; }}

      const valuesByMonth = new Map();
      months.forEach(month => valuesByMonth.set(month, new Map()));
      rows.forEach(row => valuesByMonth.get(row.month).set(row.category, row.amount));
      const positiveTotals = months.map(month =>
        [...valuesByMonth.get(month).values()].filter(value => value > 0)
          .reduce((total, value) => total + value, 0)
      );
      const negativeTotals = months.map(month =>
        Math.abs([...valuesByMonth.get(month).values()].filter(value => value < 0)
          .reduce((total, value) => total + value, 0))
      );
      const maximum = Math.max(1, ...positiveTotals);
      const negativeMaximum = Math.max(0, ...negativeTotals);
      drawYAxis(svg, width, top, bottom, left, maximum, -negativeMaximum);
      const scale = (bottom - top) / (maximum + negativeMaximum || 1);
      const baseline = top + maximum * scale;
      svg.appendChild(createSvgElement('line', {{
        x1: left, y1: baseline, x2: width - 20, y2: baseline,
        stroke: '#6b7280', 'stroke-width': 1.2
      }}));
      const groupWidth = (width - left - 20) / months.length;
      const barWidth = Math.min(38, Math.max(16, groupWidth * 0.58));

      visibleCategories.forEach(category => {{
        const color = categoryColor(category);
        const item = document.createElement('span');
        item.className = 'legend-item';
        const swatch = document.createElement('span');
        swatch.className = 'legend-swatch';
        swatch.style.background = color;
        item.append(swatch, document.createTextNode(category));
        legend.appendChild(item);
      }});

      months.forEach((month, index) => {{
        const center = left + groupWidth * (index + 0.5);
        let positiveOffset = 0;
        let negativeOffset = 0;
        visibleCategories.forEach(category => {{
          const value = valuesByMonth.get(month).get(category) || 0;
          if (!value) return;
          const color = categoryColor(category);
          const barHeight = Math.abs(value) * scale;
          const y = value > 0
            ? baseline - (positiveOffset + value) * scale
            : baseline + negativeOffset * scale;
          const bar = createSvgElement('rect', {{
            x: center - barWidth / 2, y, width: barWidth,
            height: barHeight, fill: color
          }});
          const label = `${{month}} ${{category}} ${{formatChartYen(value)}}`;
          addBarTitle(bar, label);
          makeBarInteractive(bar, label, () => {{
            showFilteredDetails('detail-table', 'expense-details', {{
              month,
              category
            }});
          }});
          svg.appendChild(bar);
          if (value > 0) positiveOffset += value;
          else negativeOffset += Math.abs(value);
        }});
        svg.appendChild(createSvgElement('text', {{
          x: center, y: bottom + 22, 'text-anchor': 'middle', fill: '#4b5563',
          'font-size': 11
        }}, month));
      }});
    }}

    function renderCharts() {{
      const year = document.getElementById('chart-year-filter').value;
      const selectedCategory = document.getElementById('category-chart-category-filter').value;
      renderCashflowChart(year);
      renderIncomeChart(year);
      renderCategoryChart(year, selectedCategory);
    }}

    function setupCategoryChartFilter() {{
      const filter = document.getElementById('category-chart-category-filter');
      chartData.categories.forEach((category) => {{
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        filter.appendChild(option);
      }});
      filter.addEventListener('change', renderCharts);
    }}

    document.getElementById('chart-year-filter').addEventListener('change', renderCharts);
    setupCategoryChartFilter();
    renderCharts();

    const tableRows = new Map();
    const filteredTableRows = new Map();
    const currentTablePages = new Map();
    const pendingFilterFrames = new Map();

    document.querySelectorAll('[data-filter-result]').forEach((result) => {{
      const tableId = result.dataset.filterResult;
      const table = document.getElementById(tableId);
      if (table) {{
        const rows = Array.from(table.querySelectorAll('tbody tr'));
        tableRows.set(tableId, rows);
        filteredTableRows.set(tableId, rows);
        currentTablePages.set(tableId, 0);
      }}
    }});

    function renderTableRows(tableId) {{
      const table = document.getElementById(tableId);
      if (!table) return;

      const rows = filteredTableRows.get(tableId) || [];
      const pagination = document.querySelector(`[data-pagination="${{tableId}}"]`);
      const pageSize = pagination ? Number(pagination.dataset.pageSize) : Math.max(rows.length, 1);
      const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
      const requestedPage = currentTablePages.get(tableId) || 0;
      const currentPage = Math.max(0, Math.min(requestedPage, pageCount - 1));
      const pageRows = rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
      const visibleRows = document.createDocumentFragment();

      pageRows.forEach((row) => visibleRows.appendChild(row));
      table.tBodies[0].replaceChildren(visibleRows);
      currentTablePages.set(tableId, currentPage);

      if (pagination) {{
        pagination.querySelector('[data-page-status]').textContent = `${{currentPage + 1}} / ${{pageCount}}`;
        pagination.querySelector('[data-page-action="previous"]').disabled = currentPage === 0;
        pagination.querySelector('[data-page-action="next"]').disabled = currentPage >= pageCount - 1;
      }}
    }}

    function applyTableFilters(tableId) {{
      const table = document.getElementById(tableId);
      if (!table) return;

      const filters = Array.from(document.querySelectorAll(`[data-filter-table="${{tableId}}"]`));
      const rows = tableRows.get(tableId) || [];
      const result = document.querySelector(`[data-filter-result="${{tableId}}"]`);
      const matchingRows = [];
      let visibleCount = 0;
      let visibleAmount = 0;

      rows.forEach((row) => {{
        const visible = filters.every((filter) => {{
          const attribute = `data-${{filter.dataset.filterName}}`;
          const groupedValues = filter.dataset.filterName === 'category'
            ? chartData.detailCategoryGroups[filter.value]
            : null;
          if (groupedValues) return groupedValues.includes(row.getAttribute(attribute));
          return !filter.value || row.getAttribute(attribute) === filter.value;
        }});
        if (visible) {{
          matchingRows.push(row);
          visibleCount += 1;
          visibleAmount += Number(row.dataset.amount);
        }}
      }});

      filteredTableRows.set(tableId, matchingRows);
      currentTablePages.set(tableId, 0);
      renderTableRows(tableId);

      const formattedAmount = new Intl.NumberFormat('ja-JP', {{
        style: 'currency',
        currency: 'JPY',
        maximumFractionDigits: 0,
      }}).format(visibleAmount);
      const countUnit = result.dataset.countUnit;
      result.textContent = `${{visibleCount.toLocaleString('ja-JP')}}${{countUnit}} / ${{formattedAmount}}`;
    }}

    function scheduleTableFilter(tableId) {{
      const pendingFrame = pendingFilterFrames.get(tableId);
      if (pendingFrame) cancelAnimationFrame(pendingFrame);
      pendingFilterFrames.set(tableId, requestAnimationFrame(() => {{
        applyTableFilters(tableId);
        pendingFilterFrames.delete(tableId);
      }}));
    }}

    document.querySelectorAll('[data-filter-table]').forEach((filter) => {{
      filter.addEventListener('change', () => scheduleTableFilter(filter.dataset.filterTable));
    }});

    document.querySelectorAll('[data-pagination]').forEach((pagination) => {{
      const tableId = pagination.dataset.pagination;
      pagination.querySelector('[data-page-action="previous"]').addEventListener('click', () => {{
        currentTablePages.set(tableId, (currentTablePages.get(tableId) || 0) - 1);
        renderTableRows(tableId);
      }});
      pagination.querySelector('[data-page-action="next"]').addEventListener('click', () => {{
        currentTablePages.set(tableId, (currentTablePages.get(tableId) || 0) + 1);
        renderTableRows(tableId);
      }});
      renderTableRows(tableId);
    }});
  </script>
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")
