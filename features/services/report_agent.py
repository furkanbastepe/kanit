from __future__ import annotations

from features.services.types import AnalysisReport, ApprovalStatus, ChecklistResult, DocumentFindings, VisionFinding


class ReportAgent:
    def customer_response_draft(self, document: DocumentFindings, checklist: ChecklistResult) -> str:
        missing = ", ".join(issue.title for issue in checklist.issues[:5]) or "kritik eksik gorunmuyor"
        root_cause = document.root_cause or "[kok neden eklenecek]"
        action = document.corrective_action or "[kalici aksiyon eklenecek]"
        verification = document.effectiveness_check or "[etkinlik dogrulama kaniti eklenecek]"
        return (
            "Sayin musteri kalite ekibi,\n\n"
            f"Ilgili uygunsuzluk icin kok neden: {root_cause}. "
            f"Kalici duzeltici aksiyon: {action}. "
            f"Etkinlik dogrulama: {verification}. "
            f"Dosya on kontrol skoru {checklist.score}/100. "
            f"Gonderim oncesi dikkat edilmesi gereken alanlar: {missing}.\n\n"
            "Bu taslak insan onayi alinmadan nihai musteri cevabi olarak kullanilmamalidir."
        )

    def markdown(self, report: AnalysisReport) -> str:
        doc = report.document
        lines = [
            f"# KANIT 8D/CAPA KANIT Kontrol Raporu",
            "",
            f"- Vaka ID: `{report.case_id}`",
            f"- Olusturma zamani: `{report.created_at}`",
            f"- Skor: **{report.checklist.score}/100**",
            f"- Durum: **{report.checklist.status.value.upper()}**",
            f"- Insan onayi: **{report.approval.status.value}**",
            "",
            "## Vaka Ozeti",
            "",
            doc.raw_summary or "Ozet uretilemedi.",
            "",
            "## Cikarilan 8D/CAPA Alanlari",
            "",
            f"- Problem: {doc.problem_statement or 'Eksik'}",
            f"- Containment: {doc.containment_action or 'Eksik'}",
            f"- Kok neden: {doc.root_cause or 'Eksik'}",
            f"- Kalici aksiyon: {doc.corrective_action or 'Eksik'}",
            f"- Onleyici aksiyon: {doc.preventive_action or 'Eksik'}",
            f"- Etkinlik dogrulama: {doc.effectiveness_check or 'Eksik'}",
            f"- Sorumlu: {doc.owner or 'Eksik'}",
            f"- Termin: {doc.due_date or 'Eksik'}",
            "",
            "## Gorsel KANIT Analizi",
            "",
        ]
        if report.vision:
            for finding in report.vision:
                lines.extend(
                    [
                        f"### {finding.filename}",
                        f"- Rol: `{finding.evidence_role}`",
                        f"- Guven: `{finding.confidence}`",
                        f"- Gozlenenler: {', '.join(finding.observed_items) or 'Yok'}",
                        f"- Eksikler: {', '.join(finding.missing_items) or 'Kritik eksik yok'}",
                        f"- Kaynak: `{finding.source}`",
                        "",
                    ]
                )
        else:
            lines.extend(["Gorsel kanit yuklenmedi.", ""])

        lines.extend(
            [
                "## Gonderim Oncesi Eksikler",
                "",
            ]
        )
        if report.checklist.issues:
            for issue in report.checklist.issues:
                lines.append(f"- **[{issue.severity}] {issue.title}:** {issue.detail} Aksiyon: {issue.suggested_action}")
        else:
            lines.append("- Kritik eksik bulunmadi; yine de kalite sorumlusu onayi gereklidir.")

        lines.extend(
            [
                "",
                "## Musteri Cevap Taslagi",
                "",
                report.customer_response_draft,
                "",
                "## Audit Trail",
                "",
            ]
        )
        lines.extend(f"- {entry}" for entry in report.audit_trail)
        return "\n".join(lines).strip() + "\n"


def initial_approval_text(status: ApprovalStatus) -> str:
    if status == ApprovalStatus.PENDING:
        return "Kapanis raporu henuz insan onayindan gecmedi."
    if status == ApprovalStatus.APPROVED:
        return "Kapanis raporu kalite sorumlusu tarafindan onaylandi."
    return "Kapanis raporu kalite sorumlusu tarafindan reddedildi."

