from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "reports"
SELECTED_MODEL_PATH = ROOT_DIR / "selected_model.json"

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    github_token: str
    gemini_api_key: str
    github_username: str | None


def load_settings() -> Settings:
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    github_username = os.environ.get("GITHUB_USERNAME", "").strip() or None

    missing = [
        name
        for name, value in (("GITHUB_TOKEN", github_token), ("GEMINI_API_KEY", gemini_api_key))
        if not value
    ]
    if missing:
        raise SystemExit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )

    return Settings(
        github_token=github_token,
        gemini_api_key=gemini_api_key,
        github_username=github_username,
    )


def load_selected_model() -> str:
    if not SELECTED_MODEL_PATH.exists():
        raise SystemExit(
            "No selected_model.json found. Run `python src/model_selector.py` first "
            "to pick a Gemini model."
        )
    data = json.loads(SELECTED_MODEL_PATH.read_text(encoding="utf-8"))
    model = data.get("model")
    if not model:
        raise SystemExit("selected_model.json is malformed (missing 'model' key).")
    return model
