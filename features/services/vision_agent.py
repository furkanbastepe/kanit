from __future__ import annotations

from typing import Any

from features.services.ai_client import build_ai_client
from features.services.nvidia_client import NvidiaClient
from features.services.types import EvidenceFile, VisionFinding


ROLE_REQUIREMENTS = {
    "defect_photo": ["defect visible", "part or area identifiable", "traceable label or context"],
    "corrective_photo": ["corrective action visible", "before/after change understandable", "verification context"],
    "measurement_photo": ["measurement value visible", "instrument or screen visible", "part reference visible"],
}


class VisionEvidenceAgent:
    def __init__(self, nvidia: NvidiaClient | Any | None = None) -> None:
        self.ai = nvidia or build_ai_client()
        self.nvidia = self.ai

    def analyze(self, evidence_files: list[EvidenceFile]) -> list[VisionFinding]:
        findings: list[VisionFinding] = []
        for evidence in evidence_files:
            model_observation = self.ai.vision(
                self._vision_prompt(evidence.evidence_role),
                evidence.data,
                evidence.content_type or "application/octet-stream",
            )
            if model_observation:
                findings.append(self._from_model_observation(evidence, model_observation))
            else:
                findings.append(self._heuristic_observation(evidence))
        return findings

    def _from_model_observation(self, evidence: EvidenceFile, observation: str) -> VisionFinding:
        lowered = observation.lower()
        requirements = ROLE_REQUIREMENTS.get(evidence.evidence_role, [])
        observed = [item for item in requirements if any(token in lowered for token in item.split())]
        missing = [item for item in requirements if item not in observed]
        confidence = 0.55 + min(0.4, len(observed) * 0.13)
        if any(word in lowered for word in ["unclear", "not visible", "cannot", "belirsiz", "gorunmuyor"]):
            confidence = min(confidence, 0.45)
        return VisionFinding(
            filename=evidence.filename,
            evidence_role=evidence.evidence_role,
            observed_items=observed or ["model produced visual observation"],
            missing_items=missing,
            confidence=round(confidence, 2),
            raw_observation=observation.strip()[:1200],
            source="nvidia",
        )

    def _heuristic_observation(self, evidence: EvidenceFile) -> VisionFinding:
        name = evidence.filename.lower()
        requirements = ROLE_REQUIREMENTS.get(evidence.evidence_role, [])
        observed: list[str] = []

        if any(token in name for token in ["defect", "hata", "crack", "capak", "scratch"]):
            observed.extend(["defect visible", "part or area identifiable"])
        if any(token in name for token in ["after", "corrective", "duzelt", "closed", "repair"]):
            observed.extend(["corrective action visible", "before/after change understandable"])
        if any(token in name for token in ["measure", "olcum", "gauge", "screen", "etiket", "label"]):
            observed.extend(["measurement value visible", "instrument or screen visible", "traceable label or context"])
            if evidence.evidence_role == "measurement_photo":
                observed.append("part reference visible")
            if evidence.evidence_role == "corrective_photo":
                observed.append("verification context")

        observed = sorted(set(observed))
        missing = [item for item in requirements if item not in observed]
        confidence = 0.72 if not missing else 0.38 if observed else 0.22
        return VisionFinding(
            filename=evidence.filename,
            evidence_role=evidence.evidence_role,
            observed_items=observed,
            missing_items=missing,
            confidence=confidence,
            raw_observation=(
                "Mock vision mode: NVIDIA_API_KEY yok veya vision cagrisi basarisiz. "
                "Dosya adina ve rolune gore deterministik kanit kontrolu yapildi."
            ),
            source="mock",
        )

    def _vision_prompt(self, role: str) -> str:
        return f"""
Bu gorsel bir otomotiv 8D/CAPA kanit dosyasinin parcasi.
Rol: {role}

Lutfen yalniz gordugun seylere dayanarak cevap ver:
- Hata veya parca kaniti gorunuyor mu?
- Duzeltici aksiyon kaniti gorunuyor mu?
- Etiket, olcum, tarih, parca referansi veya before/after baglami var mi?
- Musteriye gonderilecek 8D/CAPA kapanis kaniti icin eksik kalan seyler neler?

Kisa, maddeli ve Turkce yanit ver.
""".strip()
