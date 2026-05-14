from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from uuid import uuid4

from features.services.skill_catalog import SKILL_CATALOG
from features.services.types import InductivePattern, TrainingDelta, utc_now_iso


class WhyThisGapBuilder:
    def build(
        self,
        *,
        incident_count: int,
        issue_counts: dict[str, int],
        average_evidence_score: int,
        severity_counts: dict[str, int],
    ) -> str:
        top_issues = sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))
        issue_text = ", ".join(f"{count} {code}" for code, count in top_issues[:3])
        severity_text = ", ".join(f"{count} {severity}" for severity, count in sorted(severity_counts.items()))
        return (
            f"Bu beceri acigi {incident_count} olayda tekrar etti; "
            f"sinyaller: {issue_text}. Ortalama kanit skoru {average_evidence_score}/100. "
            f"Seviye dagilimi: {severity_text}."
        )


class InductiveSkillMiner:
    def __init__(self, why_builder: WhyThisGapBuilder | None = None) -> None:
        self.why_builder = why_builder or WhyThisGapBuilder()

    def mine(
        self,
        *,
        incidents: list[dict],
        scope_type: str,
        scope_code: str,
        include_low_confidence: bool = False,
    ) -> list[InductivePattern]:
        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "incident_ids": set(),
                "issue_counts": Counter(),
                "severity_counts": Counter(),
                "scores": [],
                "title": "",
            }
        )
        for incident in incidents:
            score = int(incident.get("case_report", {}).get("checklist", {}).get("score", 0))
            for gap in incident.get("skill_gaps", []):
                entry = grouped[gap["skill_id"]]
                entry["incident_ids"].add(incident["incident_id"])
                entry["issue_counts"][gap["source_issue_code"]] += 1
                entry["severity_counts"][gap["severity"]] += 1
                entry["scores"].append(score)
                entry["title"] = gap["title"]

        patterns = []
        for skill_id, entry in grouped.items():
            incident_count = len(entry["incident_ids"])
            if incident_count < 2 and not include_low_confidence:
                continue
            average_score = int(mean(entry["scores"])) if entry["scores"] else 0
            confidence = self._confidence(incident_count, entry["severity_counts"], average_score)
            if confidence < 0.45 and not include_low_confidence:
                continue
            issue_counts = dict(entry["issue_counts"])
            severity_counts = dict(entry["severity_counts"])
            why = self.why_builder.build(
                incident_count=incident_count,
                issue_counts=issue_counts,
                average_evidence_score=average_score,
                severity_counts=severity_counts,
            )
            title = entry["title"] or SKILL_CATALOG[skill_id].title
            patterns.append(
                InductivePattern(
                    pattern_id=f"pattern_{uuid4().hex[:12]}",
                    created_at=utc_now_iso(),
                    scope_type=scope_type,
                    scope_code=scope_code,
                    skill_id=skill_id,
                    title=title,
                    incident_count=incident_count,
                    issue_counts=issue_counts,
                    average_evidence_score=average_score,
                    severity_counts=severity_counts,
                    confidence=confidence,
                    why_this_gap=why,
                    recommendation=f"{title} icin mentor onayli mikro-egitim onceliklendirilmeli.",
                )
            )
        patterns.sort(key=lambda item: (-item.confidence, -item.incident_count, item.skill_id))
        return patterns

    def _confidence(self, incident_count: int, severity_counts: Counter, average_score: int) -> float:
        base = min(0.35 + (incident_count * 0.16), 0.85)
        if severity_counts.get("high", 0):
            base += 0.08
        if average_score < 70:
            base += 0.07
        return round(min(base, 0.95), 2)


class TrainingDeltaService:
    def analyze(
        self,
        *,
        skill_id: str,
        pattern_id: str | None,
        sop_reference: str | None,
        sop_text: str | None,
    ) -> TrainingDelta:
        skill = SKILL_CATALOG[skill_id]
        reference = sop_reference or "reference_missing"
        if not sop_text:
            missing_section = (
                f"{skill.title}: mevcut SOP veya egitim referansi yuklenmedigi icin "
                "bu beceriyi kanitlayan bolum eksik kabul edildi."
            )
            confidence = 0.62
        else:
            lower_text = sop_text.lower()
            keyword = skill.title.lower().split()[0]
            if keyword in lower_text or skill_id.replace("_", " ") in lower_text:
                missing_section = f"{skill.title}: mevcut referansta var, ancak vaka bazli kanit ornegi eklenmeli."
                confidence = 0.72
            else:
                missing_section = f"{skill.title}: mevcut referansta acik bir bolum bulunamadi."
                confidence = 0.78
        return TrainingDelta(
            delta_id=f"delta_{uuid4().hex[:12]}",
            created_at=utc_now_iso(),
            skill_id=skill_id,
            title=f"{skill.title} training delta",
            pattern_id=pattern_id,
            sop_reference=reference,
            missing_training_section=missing_section,
            micro_scenario=(
                f"Gercek bir 8D/CAPA kapanis dosyasinda {skill.title} becerisini "
                "hangi kanitlarla gosterecegini yaz ve mentor onayina sun."
            ),
            mentor_evidence_required=[
                "Vaka ile baglantili kisa teknik aciklama",
                "Tarih, sorumlu ve olculebilir sonuc",
                "Fotograf, olcum veya kayit gibi izlenebilir kanit",
            ],
            confidence=confidence,
        )


def connected_worker_positioning() -> dict[str, str]:
    return {
        "positioning": (
            "KANIT, Poka veya Augmentir'in yerine gecmez; connected-worker ve skills-matrix "
            "sistemlerini gercek kalite olaylarindan gelen kanitlarla besleyen evidence-to-skill "
            "intelligence katmanidir."
        ),
        "poka_story": (
            "Poka is talimatlari, egitim ve beceri matrisini yonetirken KANIT, 8D/CAPA "
            "olaylarindan hangi becerinin sahada eksik kaldigini kanitlar."
        ),
        "augmentir_story": (
            "Augmentir frontline operasyon ve beceri yonetimini dijitallestirirken KANIT, "
            "kalite olaylarini kullanarak bu beceri matrisine kanita dayali sinyal uretir."
        ),
    }
