from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

import certifi

from features.services.ai_client import AIProviderError, bool_from_env

log = logging.getLogger(__name__)

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_NVIDIA_TEXT_MODEL = "meta/llama-3.3-70b-instruct"
DEFAULT_NVIDIA_VISION_MODEL = "nvidia/llama-nemotron-nano-vl-8b"
DEFAULT_NVIDIA_OCR_MODEL = "nvidia/nemo-asr-ocr-v2"
DEFAULT_NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"


@dataclass(slots=True)
class NvidiaSettings:
    api_key: str | None
    mode: str = "mock"
    base_url: str = DEFAULT_NVIDIA_BASE_URL
    text_model: str = DEFAULT_NVIDIA_TEXT_MODEL
    vision_model: str = DEFAULT_NVIDIA_VISION_MODEL
    ocr_model: str = DEFAULT_NVIDIA_OCR_MODEL
    embed_model: str = DEFAULT_NVIDIA_EMBED_MODEL
    timeout_seconds: int = 60
    max_tokens: int = 1024
    allow_mock: bool = True

    @classmethod
    def from_env(cls) -> "NvidiaSettings":
        mode = os.getenv("KANIT_AI_MODE", "mock").strip().lower()
        default_allow_mock = mode != "nvidia"
        return cls(
            api_key=os.getenv("NVIDIA_API_KEY"),
            mode=mode,
            base_url=os.getenv("NVIDIA_BASE_URL", DEFAULT_NVIDIA_BASE_URL),
            text_model=os.getenv("NVIDIA_TEXT_MODEL", DEFAULT_NVIDIA_TEXT_MODEL),
            vision_model=os.getenv("NVIDIA_VISION_MODEL", DEFAULT_NVIDIA_VISION_MODEL),
            ocr_model=os.getenv("NVIDIA_OCR_MODEL", DEFAULT_NVIDIA_OCR_MODEL),
            embed_model=os.getenv("NVIDIA_EMBED_MODEL", DEFAULT_NVIDIA_EMBED_MODEL),
            timeout_seconds=int(os.getenv("NVIDIA_TIMEOUT_SECONDS", "60")),
            max_tokens=int(os.getenv("NVIDIA_MAX_TOKENS", "1024")),
            allow_mock=bool_from_env("KANIT_ALLOW_MOCK", default_allow_mock),
        )


class NvidiaClient:
    """OpenAI-compatible NVIDIA NIM client; strict mode raises instead of mocking."""

    def __init__(self, settings: NvidiaSettings | None = None) -> None:
        self.settings = settings or NvidiaSettings.from_env()
        self.mode = "nvidia" if self.settings.mode == "nvidia" else "mock"
        self.allow_mock = self.settings.allow_mock

    @property
    def enabled(self) -> bool:
        return bool(self.settings.api_key)

    def chat(self, prompt: str, *, model: str | None = None) -> str | None:
        if not self.enabled:
            self._raise_or_fallback("NVIDIA_API_KEY ortam degiskeni bulunamadi.")
            return None
        payload = {
            "model": model or self.settings.text_model,
            "messages": [
                {"role": "system", "content": "You are a precise automotive quality assistant. Return concise Turkish output."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": self.settings.max_tokens,
        }
        return self._post_chat(payload)

    def chat_json(self, prompt: str, *, model: str | None = None) -> dict | None:
        """Structured extraction — forces JSON output via response_format."""
        if not self.enabled:
            self._raise_or_fallback("NVIDIA_API_KEY ortam degiskeni bulunamadi.")
            return None
        payload = {
            "model": model or self.settings.text_model,
            "messages": [
                {"role": "system", "content": "You are a precise automotive quality assistant. Always respond with valid JSON only, no prose."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": self.settings.max_tokens,
            "response_format": {"type": "json_object"},
        }
        raw = self._post_chat(payload)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._raise_or_fallback("chat_json: JSON parse basarisiz.")
            return None

    def embed(self, text: str, *, model: str | None = None) -> list[float] | None:
        """Returns embedding vector for use with pgvector RAG."""
        if not self.enabled:
            self._raise_or_fallback("NVIDIA_API_KEY ortam degiskeni bulunamadi.")
            return None
        url = self.settings.base_url.rstrip("/") + "/embeddings"
        payload = {
            "model": model or self.settings.embed_model,
            "input": [text],
            "input_type": "query",
            "encoding_format": "float",
            "truncate": "END",
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds, context=context) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            self._raise_or_fallback(f"Embed API cagrisi basarisiz: {exc.__class__.__name__}")
            return None
        data_items = body.get("data") or []
        if not data_items:
            self._raise_or_fallback("Embed API bos data dondurdu.")
            return None
        return data_items[0].get("embedding")

    def vision(self, prompt: str, image_bytes: bytes, content_type: str) -> str | None:
        if not self.enabled:
            self._raise_or_fallback("NVIDIA_API_KEY ortam degiskeni bulunamadi.")
            return None
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.settings.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": self.settings.max_tokens,
        }
        return self._post_chat(payload)

    def _post_chat(self, payload: dict) -> str | None:
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds, context=context) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            self._raise_or_fallback(f"NVIDIA API HTTP {exc.code}: {body}")
            return None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            self._raise_or_fallback(f"NVIDIA API cagrisi basarisiz: URLError: {reason}")
            return None
        except (TimeoutError, json.JSONDecodeError) as exc:
            self._raise_or_fallback(f"NVIDIA API cagrisi basarisiz: {exc.__class__.__name__}")
            return None
        choices = body.get("choices") or []
        if not choices:
            self._raise_or_fallback("NVIDIA API bos choices dondurdu.")
            return None
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            self._raise_or_fallback("NVIDIA API beklenen text content dondurmedi.")
            return None
        return content if isinstance(content, str) else None

    def _raise_or_fallback(self, message: str) -> None:
        if not self.allow_mock:
            raise AIProviderError(message)
        # Fix 4b: log when silently falling back to mock so it's never invisible.
        log.warning("KANIT mock fallback (allow_mock=True): %s", message)
