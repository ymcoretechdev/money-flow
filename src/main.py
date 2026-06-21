from __future__ import annotations

import shutil
import webbrowser
from pathlib import Path

from category import load_category_rules, categorize
from config import (
    ARCHIVE_DIR,
    CATEGORY_RULES_PATH,
    INPUT_DIR,
    LOCAL_CATEGORY_RULES_PATH,
    ROOT_DIR,
    load_settings,
)
from csv_loader import load_all_transactions
from report import generate_html_report
from utils import ensure_parent, timestamp


def archive_csv_files() -> None:
    for card in ["rakuten", "paypay"]:
        for src_dir in (INPUT_DIR / "expense").glob(f"*/{card}"):
            owner = src_dir.parent.name
            dst_dir = ARCHIVE_DIR / "expense" / owner / card
            dst_dir.mkdir(parents=True, exist_ok=True)
            for path in src_dir.glob("*.csv"):
                dst = dst_dir / f"{path.stem}_{timestamp()}{path.suffix}"
                shutil.move(str(path), str(dst))


def main() -> None:
    settings = load_settings()

    df = load_all_transactions(INPUT_DIR, settings)
    rules = load_category_rules(LOCAL_CATEGORY_RULES_PATH)
    rules.extend(load_category_rules(CATEGORY_RULES_PATH))

    if not df.empty:
        expense_mask = df["transaction_type"] == "expense"
        df.loc[expense_mask, "category"] = df.loc[expense_mask, "shop"].apply(
            lambda shop: categorize(shop, rules)
        )
        df.loc[~expense_mask, "category"] = "収入"

    output_csv = ROOT_DIR / settings.get("output_csv", "output/merged_transactions.csv")
    output_html = ROOT_DIR / settings.get("output_html", "output/report.html")

    ensure_parent(output_csv)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    generate_html_report(df, output_html)

    if settings.get("archive_after_import", False):
        archive_csv_files()

    print("完了しました。")
    print(f"HTMLレポート: {output_html}")
    print(f"統合CSV: {output_csv}")

    if settings.get("open_report_after_generation", True):
        webbrowser.open(output_html.resolve().as_uri())


if __name__ == "__main__":
    main()
