from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

try:
    from supabase import create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False


class RAGService:
    """Retrieval-Augmented Generation for Ford CSR / AIAG policy grounding.

    Uses Supabase pgvector for similarity search and NVIDIA nv-embedqa-e5-v5
    for embeddings. Falls back gracefully when not configured.

    Usage:
        rag = RAGService()
        chunks = rag.retrieve_policy("8D D3 containment timing requirements", k=4)
        # chunks: [{"source": "ford_csr_june_2025", "section": "§6.2", "content": "..."}]
    """

    def __init__(self) -> None:
        self._client = None
        self._nvidia = None
        self._ready = False
        if not _SUPABASE_AVAILABLE:
            log.warning("RAGService: supabase package not installed — RAG disabled.")
            return
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            log.warning("RAGService: SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set — RAG disabled.")
            return
        self._client = create_client(url, key)
        self._ready = True

    def _get_nvidia(self):
        if self._nvidia is None:
            from features.services.nvidia_client import NvidiaClient
            self._nvidia = NvidiaClient()
        return self._nvidia

    def is_ready(self) -> bool:
        return self._ready and bool(os.getenv("NVIDIA_API_KEY"))

    def retrieve_policy(
        self,
        query: str,
        *,
        org_id: str | None = None,
        source: str | None = None,
        k: int = 5,
        match_threshold: float = 0.65,
    ) -> list[dict[str, Any]]:
        """Return top-k policy chunks relevant to the query."""
        if not self.is_ready():
            return []
        nvidia = self._get_nvidia()
        embedding = nvidia.embed(query)
        if not embedding:
            log.warning("RAGService: embed() returned None for query=%r", query[:80])
            return []
        try:
            rpc_params: dict[str, Any] = {
                "query_embedding": embedding,
                "match_threshold": match_threshold,
                "match_count": k,
            }
            if org_id:
                rpc_params["filter_org_id"] = org_id
            if source:
                rpc_params["filter_source"] = source
            result = self._client.rpc("match_policy_chunks", rpc_params).execute()
            return result.data or []
        except Exception as exc:
            log.warning("RAGService: retrieve failed: %s", exc)
            return []

    def format_for_prompt(self, chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks as a policy block for injection into LLM prompt."""
        if not chunks:
            return ""
        lines = ["--- İlgili Standart / Politika Referansları ---"]
        for chunk in chunks:
            source = chunk.get("source", "")
            section = chunk.get("section", "")
            content = chunk.get("content", "")
            ref = f"[{source}]" + (f" {section}" if section else "")
            lines.append(f"{ref}: {content}")
        lines.append("--- Son ---")
        return "\n".join(lines)

    def ingest_document(
        self,
        content: str,
        source: str,
        *,
        section: str | None = None,
        org_id: str | None = None,
        chunk_size: int = 600,
        overlap: int = 100,
    ) -> int:
        """Chunk, embed and store a policy document. Returns number of chunks inserted."""
        if not self.is_ready():
            raise RuntimeError("RAGService not ready: check SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, NVIDIA_API_KEY.")
        chunks = _chunk_text(content, chunk_size=chunk_size, overlap=overlap)
        nvidia = self._get_nvidia()
        inserted = 0
        for chunk_text in chunks:
            embedding = nvidia.embed(chunk_text)
            if not embedding:
                continue
            record: dict[str, Any] = {
                "source": source,
                "section": section,
                "content": chunk_text,
                "embedding": embedding,
            }
            if org_id:
                record["org_id"] = org_id
            self._client.table("policy_chunks").insert(record).execute()
            inserted += 1
        log.info("RAGService: ingested %d chunks from source=%s", inserted, source)
        return inserted


def _chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
