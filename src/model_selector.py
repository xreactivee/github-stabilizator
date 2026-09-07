from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SELECTED_MODEL_PATH, load_settings  # noqa: E402

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

RPM_WEIGHT_RULES = [
    ("flash-lite", 30),
    ("flash", 15),
    ("pro", 3),
]
DEFAULT_RPM_WEIGHT = 8

UNSTABLE_MARKERS = ("exp", "preview", "thinking")


def rpm_weight(model_name: str) -> int:
    name = model_name.lower()
    for marker, weight in RPM_WEIGHT_RULES:
        if marker in name:
            return weight
    return DEFAULT_RPM_WEIGHT


def is_unstable(model_name: str) -> bool:
    name = model_name.lower()
    return any(marker in name for marker in UNSTABLE_MARKERS)


def list_models(api_key: str) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    page_token = None
    while True:
        params = {"key": api_key, "pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(f"{API_BASE}/models", params=params, timeout=30)
        if resp.status_code != 200:
            raise SystemExit(f"ListModels failed: {resp.status_code} {resp.text}")
        data = resp.json()
        models.extend(data.get("models", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return models


def pick_best_model(models: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        m
        for m in models
        if "generateContent" in m.get("supportedGenerationMethods", [])
        and "embed" not in m.get("name", "").lower()
    ]
    if not candidates:
        raise SystemExit("No usable generateContent models found for this API key.")

    def score(m: dict[str, Any]) -> tuple[int, int, int]:
        name = m.get("name", "")
        stable_bonus = 0 if is_unstable(name) else 1
        return (stable_bonus, rpm_weight(name), m.get("inputTokenLimit", 0))

    best = max(candidates, key=score)
    return best


def main() -> None:
    settings = load_settings()
    models = list_models(settings.gemini_api_key)

    rows = sorted(
        (
            (
                m.get("name", ""),
                m.get("inputTokenLimit", 0),
                m.get("outputTokenLimit", 0),
                rpm_weight(m.get("name", "")),
                is_unstable(m.get("name", "")),
            )
            for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ),
        key=lambda r: (r[4], -r[3], -r[1]),
    )
    print(f"{'model':45} {'input_ctx':>10} {'output_ctx':>10} {'rpm_weight':>10} {'unstable':>9}")
    for name, in_ctx, out_ctx, weight, unstable in rows:
        print(f"{name:45} {in_ctx:>10} {out_ctx:>10} {weight:>10} {str(unstable):>9}")

    best = pick_best_model(models)
    model_id = best["name"].removeprefix("models/")
    result = {
        "model": model_id,
        "inputTokenLimit": best.get("inputTokenLimit"),
        "outputTokenLimit": best.get("outputTokenLimit"),
        "rpm_weight": rpm_weight(best.get("name", "")),
    }
    SELECTED_MODEL_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nSelected model: {model_id} (input_ctx={result['inputTokenLimit']})")
    print(f"Written to {SELECTED_MODEL_PATH}")


if __name__ == "__main__":
    main()
