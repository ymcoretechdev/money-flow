from __future__ import annotations

import pandas as pd
from pathlib import Path


def load_category_rules(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []

    df = pd.read_csv(path)
    if "keyword" not in df.columns or "category" not in df.columns:
        raise ValueError("category_rules.csv には keyword, category 列が必要です。")

    rules = []
    for _, row in df.iterrows():
        keyword = str(row["keyword"]).strip()
        category = str(row["category"]).strip()
        if keyword:
            rules.append((keyword, category))
    return rules


def categorize(shop_name: str, rules: list[tuple[str, str]]) -> str:
    text = str(shop_name)
    upper_text = text.upper()

    for keyword, category in rules:
        if keyword in text or keyword.upper() in upper_text:
            return category

    return "未分類"
