from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def normalize_column_name(name: str) -> str:
    return str(name).strip().replace("\ufeff", "")


def parse_amount(value) -> int:
    """金額文字列をintへ変換する。例: '1,234円', '¥1,234', '-500'"""
    if value is None:
        return 0
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return 0
    text = text.replace(",", "")
    text = text.replace("円", "")
    text = text.replace("¥", "")
    text = text.replace("￥", "")
    text = text.replace(" ", "")
    match = re.search(r"-?\d+", text)
    if not match:
        return 0
    return int(match.group(0))


def format_yen(value: int | float) -> str:
    number = float(value)
    if number.is_integer():
        return f"¥{int(number):,}"
    return f"¥{number:,.1f}"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
