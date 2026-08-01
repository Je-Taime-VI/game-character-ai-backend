from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen-plus"


class QwenClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or ""
        self.base_url = (
            base_url
            or os.getenv("QWEN_BASE_URL")
            or os.getenv("DASHSCOPE_BASE_URL")
            or DEFAULT_QWEN_BASE_URL
        ).rstrip("/")
        self.model = model or os.getenv("QWEN_MODEL") or DEFAULT_QWEN_MODEL
        self.timeout = timeout or int(os.getenv("QWEN_TIMEOUT", "120"))

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "Missing Qwen API key. Set DASHSCOPE_API_KEY or QWEN_API_KEY before using model_provider='qwen'."
            )

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or self.model,
                "messages": messages,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def generate_text(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload = self.chat(messages, model=model)
        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", "")).strip()
