from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd


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
    text = unicodedata.normalize("NFKC", str(shop_name)).upper()

    for keyword, category in rules:
        normalized_keyword = unicodedata.normalize("NFKC", keyword).upper()
        if normalized_keyword in text:
            return category

    return "未分類"
