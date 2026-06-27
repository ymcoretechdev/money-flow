from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import normalize_column_name, parse_amount


ASSET_SNAPSHOT_COLUMNS = {
    "date": ["基準日", "日付", "date"],
    "savings": ["貯金額", "預金額", "現金預金", "savings"],
    "debt": ["借金額", "負債額", "debt"],
    "investment": ["投資残高", "証券口座残高", "investment"],
}


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {normalize_column_name(c): c for c in df.columns}
    for candidate in candidates:
        candidate = normalize_column_name(candidate)
        if candidate in normalized:
            return normalized[candidate]
    return None


def load_asset_snapshots(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=["date", "savings_amount", "debt_amount", "investment_balance"]
        )

    raw = pd.read_csv(path, encoding="utf-8-sig")
    raw.columns = [normalize_column_name(c) for c in raw.columns]

    date_col = find_column(raw, ASSET_SNAPSHOT_COLUMNS["date"])
    savings_col = find_column(raw, ASSET_SNAPSHOT_COLUMNS["savings"])
    debt_col = find_column(raw, ASSET_SNAPSHOT_COLUMNS["debt"])
    investment_col = find_column(raw, ASSET_SNAPSHOT_COLUMNS["investment"])
    if not all([date_col, savings_col, debt_col, investment_col]):
        raise ValueError(
            f"{path.name}: 基準日, 貯金額, 借金額, 投資残高 の列が必要です。"
        )

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[date_col], errors="coerce"),
            "savings_amount": raw[savings_col].apply(parse_amount),
            "debt_amount": raw[debt_col].apply(parse_amount),
            "investment_balance": raw[investment_col].apply(parse_amount),
        }
    )
    df = df.dropna(subset=["date"])
    return df.sort_values("date").reset_index(drop=True)
