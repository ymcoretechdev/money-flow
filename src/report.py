from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from utils import format_yen, ensure_parent


LAST_CATEGORY_POSITIONS = {"その他": 1, "未分類": 2}
INVESTMENT_CATEGORY = "投資"


def sort_category_summary(df: pd.DataFrame, leading_columns: list[str] | None = None) -> pd.DataFrame:
    leading_columns = leading_columns or []

    out = df.copy()
    out["_category_position"] = out["category"].map(LAST_CATEGORY_POSITIONS).fillna(0)
    out = out.sort_values(
        [*leading_columns, "_category_position", "amount"],
        ascending=[True] * len(leading_columns) + [True, False],
    )
    return out.drop(columns="_category_position").reset_index(drop=True)


def build_summaries(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if df.empty:
        empty = pd.DataFrame()
        return {
            "monthly": empty,
            "card_monthly": empty,
            "category_monthly": empty,
            "category_total": empty,
            "investment_monthly": empty,
        }

    work = df.copy()
    work["month"] = work["date"].dt.strftime("%Y-%m")
    spending = work[work["category"] != INVESTMENT_CATEGORY]
    investment = work[work["category"] == INVESTMENT_CATEGORY]

    monthly = spending.groupby("month", as_index=False)["amount"].sum()
    card_monthly = spending.groupby(["month", "card"], as_index=False)["amount"].sum()
    category_monthly = spending.groupby(["month", "category"], as_index=False)["amount"].sum()
    category_total = spending.groupby("category", as_index=False)["amount"].sum()
    investment_monthly = investment.groupby("month", as_index=False)["amount"].sum()

    return {
        "monthly": monthly,
        "card_monthly": card_monthly,
        "category_monthly": sort_category_summary(category_monthly, ["month"]),
        "category_total": sort_category_summary(category_total),
        "investment_monthly": investment_monthly,
    }


def yen_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "amount" in out.columns:
        out["amount"] = out["amount"].apply(format_yen)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def df_to_html_table(
    df: pd.DataFrame,
    table_id: str,
    row_attributes: dict[str, str | object] | None = None,
    empty_message: str = "データがありません。",
) -> str:
    if df.empty:
        return f"<p class='empty'>{html.escape(empty_message)}</p>"

    row_attributes = row_attributes or {}
    formatted = yen_table(df)
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in formatted.columns)
    rows = []

    for (_, raw_row), (_, display_row) in zip(df.iterrows(), formatted.iterrows()):
        attributes = [f'data-amount="{int(raw_row["amount"])}"']
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
    spending = df[df["category"] != INVESTMENT_CATEGORY] if not df.empty else df
    investment = df[df["category"] == INVESTMENT_CATEGORY] if not df.empty else df
    spending_total = int(spending["amount"].sum()) if not spending.empty else 0
    investment_total = int(investment["amount"].sum()) if not investment.empty else 0
    all_total = spending_total + investment_total
    count = len(df)

    detail = df.copy()
    if not detail.empty:
        detail = detail[["date", "card", "shop", "category", "amount", "source_file"]]
        detail = detail.sort_values("date", ascending=False)

    months = sorted(df["date"].dt.strftime("%Y-%m").unique(), reverse=True) if not df.empty else []
    years = sorted({month[:4] for month in months}, reverse=True)
    cards = sorted(df["card"].astype(str).unique()) if not df.empty else []
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

    html_text = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>カード明細レポート</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; background: #f7f8fb; color: #222; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; border-left: 6px solid #3367d6; padding-left: 10px; }}
    .summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }}
    .card {{ background: white; border-radius: 12px; padding: 18px 22px; box-shadow: 0 2px 10px rgba(0,0,0,.06); min-width: 180px; }}
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
    .empty {{ background: white; padding: 16px; border-radius: 8px; }}
    .note {{ color: #666; font-size: 13px; }}
    @media (max-width: 640px) {{ body {{ margin: 18px; }} .filter-fields, .filter-field {{ width: 100%; }} }}
  </style>
</head>
<body>
  <h1>カード明細レポート</h1>
  <p class="note">CSVを読み込んで自動生成したローカルHTMLレポートです。</p>

  <div class="summary">
    <div class="card"><div class="label">支出合計</div><div class="value">{format_yen(spending_total)}</div></div>
    <div class="card"><div class="label">投資合計</div><div class="value">{format_yen(investment_total)}</div></div>
    <div class="card"><div class="label">全明細件数</div><div class="value">{count:,}件</div></div>
  </div>

  <h2>月別集計</h2>
  {filter_toolbar('monthly-table', [('year', '年', years)], len(summaries['monthly']), spending_total)}
  {df_to_html_table(summaries['monthly'], 'monthly-table', {'year': lambda row: str(row['month'])[:4]})}

  <h2>投資集計</h2>
  {filter_toolbar('investment-monthly-table', [('year', '年', years)], len(summaries['investment_monthly']), investment_total)}
  {df_to_html_table(summaries['investment_monthly'], 'investment-monthly-table', {'year': lambda row: str(row['month'])[:4]}, '投資データがありません。')}

  <h2>月別・カード別集計</h2>
  {filter_toolbar('card-monthly-table', [('card', 'カード', cards)], len(summaries['card_monthly']), spending_total)}
  {df_to_html_table(summaries['card_monthly'], 'card-monthly-table', {'card': 'card'})}

  <h2>カテゴリ別合計</h2>
  {filter_toolbar('category-total-table', [('category', 'カテゴリ', spending_categories)], len(summaries['category_total']), spending_total)}
  {df_to_html_table(summaries['category_total'], 'category-total-table', {'category': 'category'})}

  <h2>月別・カテゴリ別集計</h2>
  {filter_toolbar('category-monthly-table', [('month', '月', months), ('category', 'カテゴリ', spending_categories)], len(summaries['category_monthly']), spending_total)}
  {df_to_html_table(summaries['category_monthly'], 'category-monthly-table', {'month': 'month', 'category': 'category'})}

  <h2>明細一覧</h2>
  {filter_toolbar('detail-table', [('month', '月', months), ('card', 'カード', cards), ('category', 'カテゴリ', categories)], count, all_total, '件', 100)}
  {df_to_html_table(detail, 'detail-table', {'month': lambda row: row['date'].strftime('%Y-%m'), 'card': 'card', 'category': 'category'})}
  <script>
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
