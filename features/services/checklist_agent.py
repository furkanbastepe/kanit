from __future__ import annotations

from features.services.types import (
    ChecklistIssue,
    ChecklistResult,
    DocumentFindings,
    TrafficLight,
    VisionFinding,
)


class ChecklistAgent:
    """Deterministic Ford/IATF-inspired 8D/CAPA evidence linting."""

    def evaluate(self, document: DocumentFindings, vision: list[VisionFinding]) -> ChecklistResult:
        issues: list[ChecklistIssue] = []
        strengths: list[str] = []

        required_fields = [
            ("problem_statement", "Problem tanimi", "Musteri sikayeti/uygunsuzluk net tarif edilmeli."),
            ("containment_action", "Containment", "24 saat icinde gecici onlem veya stok kontrolu izlenebilir olmali."),
            ("root_cause", "Kok neden", "5 Why veya teknik kok neden kaniti olmadan CAPA zayif kalir."),
            ("corrective_action", "Kalici aksiyon", "Kalici duzeltici aksiyon acik ve dogrulanabilir olmali."),
            ("effectiveness_check", "Etkinlik dogrulama", "Aksiyonun ise yaradigini gosteren tarihli dogrulama gerekir."),
            ("owner", "Sorumlu", "Aksiyon sahibi belli olmali."),
            ("due_date", "Termin", "Kapanis tarihi/termin izlenebilir olmali."),
        ]

        for field_name, title, detail in required_fields:
            value = getattr(document, field_name)
            if value:
                strengths.append(f"{title} alani bulundu.")
            else:
                issues.append(
                    ChecklistIssue(
                        code=f"missing_{field_name}",
                        severity="high" if field_name in {"root_cause", "corrective_action", "effectiveness_check"} else "medium",
                        title=f"Eksik alan: {title}",
                        detail=detail,
                        suggested_action=f"8D/CAPA dosyasina '{title}' alanini kanitla birlikte ekle.",
                    )
                )

        roles = {item.evidence_role: item for item in vision}
        if "defect_photo" not in roles:
            issues.append(
                ChecklistIssue(
                    code="missing_defect_photo",
                    severity="high",
                    title="Hata fotografi yok",
                    detail="Kapanis dosyasi, baslangic uygunsuzlugunu gosteren izlenebilir kanit icermiyor.",
                    suggested_action="Hata/uygunsuzluk fotografini parca etiketi veya lot bilgisiyle yukle.",
                )
            )
        if "corrective_photo" not in roles:
            issues.append(
                ChecklistIssue(
                    code="missing_corrective_photo",
                    severity="high",
                    title="Duzeltici aksiyon kanit fotografi yok",
                    detail="Kalici aksiyonun uygulandigini gosteren before/after veya saha kaniti eksik.",
                    suggested_action="Duzeltme sonrasi fotograf, olcum veya kontrol kaydi ekle.",
                )
            )

        for finding in vision:
            if finding.confidence < 0.5:
                issues.append(
                    ChecklistIssue(
                        code=f"weak_visual_evidence_{finding.evidence_role}",
                        severity="medium",
                        title=f"Zayif gorsel kanit: {finding.filename}",
                        detail="Gorsel kanitin rolunu destekleyen izlenebilir ogeler yeterince belirgin degil.",
                        suggested_action="Daha net fotograf, etiket, tarih, olcum veya before/after baglami ekle.",
                    )
                )
            else:
                strengths.append(f"{finding.filename} icin gorsel kanit okunabilir gorunuyor.")

        score = self._score(issues, strengths)
        status = TrafficLight.GREEN if score >= 82 else TrafficLight.YELLOW if score >= 55 else TrafficLight.RED
        return ChecklistResult(score=score, status=status, issues=issues, strengths=strengths[:8])

    def _score(self, issues: list[ChecklistIssue], strengths: list[str]) -> int:
        score = 100
        for issue in issues:
            score -= 18 if issue.severity == "high" else 10 if issue.severity == "medium" else 5
        score += min(8, len(strengths))
        return max(0, min(100, score))

