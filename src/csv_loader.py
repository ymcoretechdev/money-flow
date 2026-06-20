from __future__ import annotations

from pathlib import Path
import pandas as pd

from utils import normalize_column_name, parse_amount


def read_csv_with_fallback(path: Path, encodings: list[str]) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            df = pd.read_csv(path, encoding=encoding)
            df.columns = [normalize_column_name(c) for c in df.columns]
            return df
        except Exception as e:
            last_error = e
    raise RuntimeError(f"CSVを読み込めませんでした: {path} / {last_error}")


def find_column(df: pd.DataFrame, candidates: list[str], label: str, path: Path) -> str:
    normalized = {normalize_column_name(c): c for c in df.columns}
    for candidate in candidates:
        candidate = normalize_column_name(candidate)
        if candidate in normalized:
            return normalized[candidate]
    raise ValueError(
        f"{path.name}: {label} 列が見つかりません。候補={candidates}, 実際の列={list(df.columns)}"
    )


def normalize_card_csv(path: Path, card_name: str, card_settings: dict, encodings: list[str]) -> pd.DataFrame:
    raw = read_csv_with_fallback(path, encodings)

    date_col = find_column(raw, card_settings["date_columns"], "日付", path)
    shop_col = find_column(raw, card_settings["shop_columns"], "利用先", path)
    amount_col = find_column(raw, card_settings["amount_columns"], "金額", path)

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[date_col], errors="coerce"),
        "card": card_name,
        "shop": raw[shop_col].astype(str).str.strip(),
        "amount": raw[amount_col].apply(parse_amount),
        "source_file": path.name,
    })

    df = df.dropna(subset=["date"])
    df = df[df["amount"] != 0]
    return df


def load_all_transactions(input_dir: Path, settings: dict) -> pd.DataFrame:
    encodings = settings.get("encodings_to_try", ["utf-8-sig", "cp932", "shift_jis"])
    frames: list[pd.DataFrame] = []

    card_map = {
        "rakuten": "楽天カード",
        "paypay": "PayPayカード",
    }

    for folder_name, card_name in card_map.items():
        folder = input_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(folder.glob("*.csv")):
            frames.append(normalize_card_csv(path, card_name, settings[folder_name], encodings))

    if not frames:
        return pd.DataFrame(columns=["date", "card", "shop", "amount", "source_file"])

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["date", "card", "shop"]).reset_index(drop=True)
    return df
