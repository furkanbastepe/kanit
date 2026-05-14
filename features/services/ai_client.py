from __future__ import annotations

import os
from typing import Protocol


class AIProviderError(RuntimeError):
    """Raised when a required live AI provider cannot produce a response."""


class AIClient(Protocol):
    mode: str
    allow_mock: bool

    @property
    def enabled(self) -> bool:
        ...

    def chat(self, prompt: str, *, model: str | None = None) -> str | None:
        ...

    def vision(self, prompt: str, image_bytes: bytes, content_type: str) -> str | None:
        ...


def bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_ai_client() -> AIClient:
    mode = os.getenv("KANIT_AI_MODE", "mock").strip().lower()
    if mode == "ollama":
        from features.services.ollama_client import OllamaClient

        return OllamaClient.from_env()
    from features.services.nvidia_client import NvidiaClient, NvidiaSettings

    return NvidiaClient(NvidiaSettings.from_env())

