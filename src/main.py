from __future__ import annotations

import shutil
from pathlib import Path

from category import load_category_rules, categorize
from config import INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, CATEGORY_RULES_PATH, load_settings, ROOT_DIR
from csv_loader import load_all_transactions
from report import generate_html_report
from utils import ensure_parent, timestamp


def archive_csv_files() -> None:
    for card in ["rakuten", "paypay"]:
        src_dir = INPUT_DIR / card
        dst_dir = ARCHIVE_DIR / card
        dst_dir.mkdir(parents=True, exist_ok=True)
        for path in src_dir.glob("*.csv"):
            dst = dst_dir / f"{path.stem}_{timestamp()}{path.suffix}"
            shutil.move(str(path), str(dst))


def main() -> None:
    settings = load_settings()

    df = load_all_transactions(INPUT_DIR, settings)
    rules = load_category_rules(CATEGORY_RULES_PATH)

    if not df.empty:
        df["category"] = df["shop"].apply(lambda shop: categorize(shop, rules))

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


if __name__ == "__main__":
    main()
