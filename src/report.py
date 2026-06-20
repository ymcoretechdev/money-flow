from __future__ import annotations

import html
from pathlib import Path
import pandas as pd

from utils import format_yen, ensure_parent


LAST_CATEGORY_POSITIONS = {"その他": 1, "未分類": 2}


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
        return {"monthly": empty, "card_monthly": empty, "category_monthly": empty, "category_total": empty}

    work = df.copy()
    work["month"] = work["date"].dt.strftime("%Y-%m")

    monthly = work.groupby("month", as_index=False)["amount"].sum()
    card_monthly = work.groupby(["month", "card"], as_index=False)["amount"].sum()
    category_monthly = work.groupby(["month", "category"], as_index=False)["amount"].sum()
    category_total = work.groupby("category", as_index=False)["amount"].sum()

    return {
        "monthly": monthly,
        "card_monthly": card_monthly,
        "category_monthly": sort_category_summary(category_monthly, ["month"]),
        "category_total": sort_category_summary(category_total),
    }


def yen_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "amount" in out.columns:
        out["amount"] = out["amount"].apply(format_yen)
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def df_to_html_table(df: pd.DataFrame, empty_message: str = "データがありません。") -> str:
    if df.empty:
        return f"<p class='empty'>{html.escape(empty_message)}</p>"
    return yen_table(df).to_html(index=False, escape=True, classes="data-table")


def generate_html_report(df: pd.DataFrame, output_path: Path) -> None:
    ensure_parent(output_path)
    summaries = build_summaries(df)
    total = int(df["amount"].sum()) if not df.empty else 0
    count = len(df)

    detail = df.copy()
    if not detail.empty:
        detail = detail[["date", "card", "shop", "category", "amount", "source_file"]]
        detail = detail.sort_values("date", ascending=False)

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
    .empty {{ background: white; padding: 16px; border-radius: 8px; }}
    .note {{ color: #666; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>カード明細レポート</h1>
  <p class="note">CSVを読み込んで自動生成したローカルHTMLレポートです。</p>

  <div class="summary">
    <div class="card"><div class="label">合計金額</div><div class="value">{format_yen(total)}</div></div>
    <div class="card"><div class="label">明細件数</div><div class="value">{count:,}件</div></div>
  </div>

  <h2>月別集計</h2>
  {df_to_html_table(summaries['monthly'])}

  <h2>月別・カード別集計</h2>
  {df_to_html_table(summaries['card_monthly'])}

  <h2>カテゴリ別合計</h2>
  {df_to_html_table(summaries['category_total'])}

  <h2>月別・カテゴリ別集計</h2>
  {df_to_html_table(summaries['category_monthly'])}

  <h2>明細一覧</h2>
  {df_to_html_table(detail)}
</body>
</html>
"""
    output_path.write_text(html_text, encoding="utf-8")
