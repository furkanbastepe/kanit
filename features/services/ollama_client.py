from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from features.services.ai_client import AIProviderError

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TEXT_MODEL = "llama3.1"
DEFAULT_OLLAMA_VISION_MODEL = "llava"


@dataclass(slots=True)
class OllamaSettings:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    text_model: str = DEFAULT_OLLAMA_TEXT_MODEL
    vision_model: str = DEFAULT_OLLAMA_VISION_MODEL
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "OllamaSettings":
        return cls(
            base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            text_model=os.getenv("OLLAMA_TEXT_MODEL", DEFAULT_OLLAMA_TEXT_MODEL),
            vision_model=os.getenv("OLLAMA_VISION_MODEL", DEFAULT_OLLAMA_VISION_MODEL),
            timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        )


class OllamaClient:
    """Local Ollama client kept behind the same chat/vision interface."""

    mode = "ollama"
    allow_mock = False

    def __init__(self, settings: OllamaSettings | None = None) -> None:
        self.settings = settings or OllamaSettings.from_env()

    @classmethod
    def from_env(cls) -> "OllamaClient":
        return cls(OllamaSettings.from_env())

    @property
    def enabled(self) -> bool:
        return True

    def chat(self, prompt: str, *, model: str | None = None) -> str | None:
        return self._chat(
            model=model or self.settings.text_model,
            messages=[{"role": "user", "content": prompt}],
        )

    def vision(self, prompt: str, image_bytes: bytes, content_type: str) -> str | None:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return self._chat(
            model=self.settings.vision_model,
            messages=[{"role": "user", "content": prompt, "images": [encoded]}],
        )

    def _chat(self, *, model: str, messages: list[dict]) -> str:
        payload = {"model": model, "messages": messages, "stream": False}
        request = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"Ollama cagrisi basarisiz: {exc.__class__.__name__}") from exc
        message = body.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise AIProviderError("Ollama beklenen text content dondurmedi.")
        return content
