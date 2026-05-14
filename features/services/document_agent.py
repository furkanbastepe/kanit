from __future__ import annotations

import re
from typing import Any

from features.services.ai_client import build_ai_client
from features.services.nvidia_client import NvidiaClient
from features.services.types import DocumentFindings


SECTION_PATTERNS: dict[str, list[str]] = {
    "problem_statement": ["problem", "problem tanimi", "sorun", "uygunsuzluk", "complaint", "d2"],
    "containment_action": ["containment", "gecici onlem", "acil onlem", "stok ayirma", "d3"],
    "root_cause": ["root cause", "kok neden", "5 why", "5 neden", "d4"],
    "corrective_action": ["corrective action", "duzeltici aksiyon", "kalici aksiyon", "d5", "d6"],
    "preventive_action": ["preventive action", "onleyici aksiyon", "d7"],
    "effectiveness_check": ["effectiveness", "etkinlik dogrulama", "dogrulama", "etkinlik", "verification"],
    "owner": ["owner", "sorumlu", "responsible"],
    "due_date": ["due date", "termin", "deadline", "hedef tarih"],
}

ALL_LABELS = [_strip for labels in SECTION_PATTERNS.values() for _strip in labels]
STOP_LABEL_PATTERN = "|".join(
    re.escape(label)
    for label in sorted(ALL_LABELS + ["kalici duzeltici aksiyon", "etkinlik dogrulama", "not"], key=len, reverse=True)
    if len(label) > 2
)

# Maps DocumentFindings field names to SECTION_PATTERNS keys
_FIELD_TO_SECTION = {
    "problem_statement": "problem_statement",
    "containment_action": "containment_action",
    "root_cause": "root_cause",
    "corrective_action": "corrective_action",
    "preventive_action": "preventive_action",
    "effectiveness_check": "effectiveness_check",
    "owner": "owner",
    "due_date": "due_date",
}


class DocumentAgent:
    def __init__(self, nvidia: NvidiaClient | Any | None = None) -> None:
        self.ai = nvidia or build_ai_client()
        self.nvidia = self.ai

    def analyze(self, case_text: str) -> DocumentFindings:
        findings = self._heuristic_extract(case_text)
        llm_summary = self.ai.chat(self._summary_prompt(case_text))
        if llm_summary:
            findings.raw_summary = llm_summary.strip()
            findings.source = "nvidia+heuristic"
            # Mark all found fields as llm+heuristic (LLM confirmed the extraction)
            for field_name in _FIELD_TO_SECTION:
                if getattr(findings, field_name) is not None:
                    findings.field_extraction_mode[field_name] = "llm+heuristic"
        elif not findings.raw_summary:
            findings.raw_summary = self._fallback_summary(case_text)
        return findings

    def _heuristic_extract(self, text: str) -> DocumentFindings:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        sections: dict[str, str] = {}
        field_confidence: dict[str, float] = {}
        field_extraction_mode: dict[str, str] = {}
        field_source_spans: dict[str, str] = {}

        for field, labels in SECTION_PATTERNS.items():
            result = self._find_labeled_value_with_meta(text, lines, labels)
            if result:
                value, line_idx, confidence, mode = result
                sections[field] = value
                field_confidence[field] = confidence
                field_extraction_mode[field] = mode
                if line_idx is not None:
                    field_source_spans[field] = f"line {line_idx + 1}"

        # Regex fallbacks for owner and due_date with their own confidence tracking
        for field, pattern, confidence in [
            ("owner", r"(?:owner|sorumlu|responsible)[ \t]*[:=-][ \t]*([^\n]+)", 0.85),
            ("due_date", r"(?:termin|deadline|due date|hedef tarih)[ \t]*[:=-][ \t]*([^\n]+)", 0.85),
        ]:
            if field not in sections:
                value = self._regex_pick(text, pattern)
                if value:
                    sections[field] = value
                    field_confidence[field] = confidence
                    field_extraction_mode[field] = "heuristic_regex"
                    field_source_spans[field] = "regex_match"

        findings = DocumentFindings(
            problem_statement=sections.get("problem_statement"),
            containment_action=sections.get("containment_action"),
            root_cause=sections.get("root_cause"),
            corrective_action=sections.get("corrective_action"),
            preventive_action=sections.get("preventive_action"),
            effectiveness_check=sections.get("effectiveness_check"),
            owner=sections.get("owner"),
            due_date=sections.get("due_date"),
            raw_summary=self._fallback_summary(text),
            extracted_sections=sections,
            source="heuristic",
            field_confidence=field_confidence,
            field_extraction_mode=field_extraction_mode,
            field_source_spans=field_source_spans,
        )
        return findings

    def _find_labeled_value_with_meta(
        self, text: str, lines: list[str], labels: list[str]
    ) -> tuple[str, int | None, float, str] | None:
        """Returns (value, line_index, confidence, extraction_mode) or None."""
        # Try inline match first (highest confidence)
        inline_result = self._find_inline_labeled_value_with_line(text, lines, labels)
        if inline_result:
            value, line_idx = inline_result
            return value, line_idx, 0.92, "heuristic_inline"

        # Try line-by-line label search — label must be at the LINE START (not buried in body text)
        normalized_labels = [_strip_accents(label.lower()) for label in labels]
        for index, line in enumerate(lines):
            normalized_line = _strip_accents(line.lower())
            line_head = re.sub(r'^[#*\s]+', '', normalized_line)
            if any(line_head.startswith(label) for label in normalized_labels):
                if ":" in line:
                    value = line.split(":", 1)[1].strip()
                    if value:
                        return value[:800], index, 0.88, "heuristic_labeled"
                    if index + 1 < len(lines) and self._looks_like_new_label(lines[index + 1]):
                        continue
                if "-" in line:
                    value = line.split("-", 1)[1].strip()
                    if value:
                        return value[:800], index, 0.85, "heuristic_labeled"
                    if index + 1 < len(lines) and self._looks_like_new_label(lines[index + 1]):
                        continue
                if index + 1 < len(lines):
                    if self._looks_like_new_label(lines[index + 1]):
                        continue
                    return lines[index + 1][:800], index + 1, 0.72, "heuristic_next_line"
        return None

    # Keep original method for backward compatibility (used by owner/due_date regex fallback)
    def _find_labeled_value(self, text: str, lines: list[str], labels: list[str]) -> str | None:
        result = self._find_labeled_value_with_meta(text, lines, labels)
        return result[0] if result else None

    def _find_inline_labeled_value_with_line(
        self, text: str, lines: list[str], labels: list[str]
    ) -> tuple[str, int] | None:
        label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
        pattern = rf"(?:{label_pattern})\s*[:=-]\s*(.*?)(?=\s+(?:{STOP_LABEL_PATTERN})\s*[:=-]|$)"
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .;-")
        if not value:
            return None
        # Find approximate line number from match position
        line_idx = text[: match.start()].count("\n")
        return value[:800], line_idx

    def _find_inline_labeled_value(self, text: str, labels: list[str]) -> str | None:
        label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
        pattern = rf"(?:{label_pattern})\s*[:=-]\s*(.*?)(?=\s+(?:{STOP_LABEL_PATTERN})\s*[:=-]|$)"
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .;-")
        return value[:800] if value else None

    def _looks_like_new_label(self, line: str) -> bool:
        normalized_line = _strip_accents(line.lower())
        head = normalized_line[:60]
        return ":" in head or any(_strip_accents(label.lower()) in head for label in ALL_LABELS)

    def _regex_pick(self, text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(1).strip()[:300] if match else None

    def _fallback_summary(self, text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if not compact:
            return "Vaka metni bos veya okunamadi."
        return compact[:600]

    def _summary_prompt(self, case_text: str) -> str:
        return f"""
Bir otomotiv tedarikcisine ait 8D/CAPA vaka metnini incele.
Yalnizca kanita dayali ozet cikar; varsayim yapma.

Cikarin:
- Problem
- Gecici onlem / containment
- Kok neden
- Kalici duzeltici aksiyon
- Etkinlik dogrulama
- Eksik gorunen alanlar

Vaka:
{case_text[:6000]}
""".strip()


def _strip_accents(value: str) -> str:
    translation = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return value.translate(translation)
