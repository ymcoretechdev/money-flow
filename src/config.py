import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
INPUT_DIR = ROOT_DIR / "input"
ARCHIVE_DIR = ROOT_DIR / "archive"
OUTPUT_DIR = ROOT_DIR / "output"
LOG_DIR = ROOT_DIR / "logs"

SETTINGS_PATH = CONFIG_DIR / "settings.json"
CATEGORY_RULES_PATH = CONFIG_DIR / "category_rules.csv"


def load_settings() -> dict:
    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
