from __future__ import annotations

import json
import time
from typing import Any

import requests

from taxonomy import build_prompt

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

REQUIRED_KEYS = {"category", "description", "topics", "readme_markdown", "notes"}


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str, model: str, min_interval_seconds: float = 4.0):
        self._api_key = api_key
        self._model = model
        self._min_interval = min_interval_seconds
        self._last_call = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def generate_repo_metadata(
        self, context: dict[str, Any], category_override: str | None = None
    ) -> dict[str, Any]:
        prompt = build_prompt(context, category_override)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.4,
            },
        }
        url = f"{API_BASE}/models/{self._model}:generateContent"

        for attempt in range(5):
            self._throttle()
            self._last_call = time.monotonic()
            resp = requests.post(url, params={"key": self._api_key}, json=body, timeout=120)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                raise GeminiError(
                    f"generateContent failed for {context.get('name')}: "
                    f"{resp.status_code} {resp.text}"
                )
            data = resp.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as exc:
                raise GeminiError(f"Unexpected Gemini response shape: {data}") from exc

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise GeminiError(f"Gemini did not return valid JSON: {text[:500]}") from exc

            missing = REQUIRED_KEYS - parsed.keys()
            if missing:
                raise GeminiError(f"Gemini response missing keys {missing}: {parsed}")
            return parsed

        raise GeminiError(f"Rate limited repeatedly generating metadata for {context.get('name')}")
