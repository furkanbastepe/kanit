from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log"}
PDF_EXTENSIONS = {".pdf"}


def bytes_to_text(filename: str, data: bytes) -> str:
    """Best-effort text extraction without heavyweight dependencies."""
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return data.decode("utf-8", errors="replace")
    if suffix in PDF_EXTENSIONS:
        return pdf_bytes_to_text(filename, data)

    decoded = data.decode("utf-8", errors="ignore")
    printable = re.sub(r"[^\x09\x0a\x0d\x20-\x7e]", " ", decoded)
    printable = re.sub(r"\s+", " ", printable).strip()
    digest = hashlib.sha256(data).hexdigest()[:16]
    if printable:
        return (
            f"[Best-effort text extracted from {filename}; sha256={digest}; "
            f"size={len(data)} bytes]\n{printable[:5000]}"
        )
    return f"[Binary file {filename}; sha256={digest}; size={len(data)} bytes; no readable text extracted]"


def pdf_bytes_to_text(filename: str, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:16]
    try:
        from pypdf import PdfReader
    except ImportError:
        return (
            f"[PDF text extraction unavailable for {filename}; install pypdf; "
            f"sha256={digest}; size={len(data)} bytes]"
        )

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for index, page in enumerate(reader.pages[:12], start=1):
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                pages.append(f"[page {index}] {text}")
        extracted = "\n".join(pages).strip()
    except Exception as exc:  # pypdf raises several parser-specific exceptions.
        return (
            f"[PDF text extraction failed for {filename}: {exc.__class__.__name__}; "
            f"sha256={digest}; size={len(data)} bytes]"
        )

    if extracted:
        return (
            f"[PDF text extracted from {filename}; sha256={digest}; "
            f"pages_read={min(len(reader.pages), 12)}]\n{extracted[:12000]}"
        )
    return f"[PDF file {filename}; sha256={digest}; size={len(data)} bytes; no readable text extracted]"


def normalize_case_text(*parts: str | None) -> str:
    content = "\n\n".join(part.strip() for part in parts if part and part.strip())
    return content.strip()
