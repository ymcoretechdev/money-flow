from __future__ import annotations

from pathlib import Path
import pandas as pd

from utils import normalize_column_name, parse_amount


OWNER_LABELS = {
    "husband": "夫",
    "wife": "妻",
    "common": "共通",
}


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


def normalize_transaction_csv(
    path: Path,
    payment_source: str,
    transaction_type: str,
    owner: str,
    source_settings: dict,
    encodings: list[str],
) -> pd.DataFrame:
    raw = read_csv_with_fallback(path, encodings)

    date_col = find_column(raw, source_settings["date_columns"], "日付", path)
    shop_col = find_column(raw, source_settings["shop_columns"], "利用先", path)
    amount_col = find_column(raw, source_settings["amount_columns"], "金額", path)

    df = pd.DataFrame({
        "date": pd.to_datetime(raw[date_col], errors="coerce"),
        "transaction_type": transaction_type,
        "owner": owner,
        "payment_source": payment_source,
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

    for transaction_type in ["expense", "income"]:
        transaction_root = input_dir / transaction_type
        transaction_root.mkdir(parents=True, exist_ok=True)

        for path in sorted(transaction_root.rglob("*.csv")):
            relative_path = path.relative_to(transaction_root)
            owner_key = relative_path.parts[0] if len(relative_path.parts) > 1 else "common"
            owner = OWNER_LABELS.get(owner_key.lower(), owner_key)
            directory_names = {part.lower() for part in relative_path.parts[1:-1]}

            if transaction_type == "income":
                payment_source = "手動入力"
                settings_key = "income"
            elif "rakuten" in directory_names:
                payment_source = "楽天カード"
                settings_key = "rakuten"
            elif "paypay" in directory_names:
                payment_source = "PayPayカード"
                settings_key = "paypay"
            else:
                payment_source = "口座引き落とし"
                settings_key = "manual"

            frames.append(
                normalize_transaction_csv(
                    path,
                    payment_source,
                    transaction_type,
                    owner,
                    settings[settings_key],
                    encodings,
                )
            )

    if not frames:
        return pd.DataFrame(
            columns=[
                "date",
                "transaction_type",
                "owner",
                "payment_source",
                "shop",
                "amount",
                "source_file",
            ]
        )

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(
        ["date", "transaction_type", "owner", "payment_source", "shop"]
    ).reset_index(drop=True)
    return df
