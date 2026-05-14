from __future__ import annotations

from uuid import uuid4

from features.services.approval_agent import ApprovalAgent
from features.services.checklist_agent import ChecklistAgent
from features.services.document_agent import DocumentAgent
from features.services.report_agent import ReportAgent
from features.services.types import AnalysisReport, ApprovalStatus, EvidenceFile, utc_now_iso
from features.services.vision_agent import VisionEvidenceAgent


class CaseAnalyzer:
    def __init__(
        self,
        document_agent: DocumentAgent | None = None,
        vision_agent: VisionEvidenceAgent | None = None,
        checklist_agent: ChecklistAgent | None = None,
        report_agent: ReportAgent | None = None,
        approval_agent: ApprovalAgent | None = None,
    ) -> None:
        self.document_agent = document_agent or DocumentAgent()
        self.vision_agent = vision_agent or VisionEvidenceAgent()
        self.checklist_agent = checklist_agent or ChecklistAgent()
        self.report_agent = report_agent or ReportAgent()
        self.approval_agent = approval_agent or ApprovalAgent()

    def analyze(self, case_text: str, evidence_files: list[EvidenceFile]) -> AnalysisReport:
        case_id = f"case_{uuid4().hex[:12]}"
        created_at = utc_now_iso()
        audit_trail = [
            f"{created_at} - Vaka alindi ve analiz baslatildi.",
            f"{utc_now_iso()} - Dokuman ajani vaka metnini inceledi.",
        ]

        document = self.document_agent.analyze(case_text)
        vision = self.vision_agent.analyze(evidence_files)
        audit_trail.append(f"{utc_now_iso()} - Gorsel kanit ajani {len(vision)} dosyayi kontrol etti.")

        checklist = self.checklist_agent.evaluate(document, vision)
        audit_trail.append(f"{utc_now_iso()} - Checklist ajani {checklist.score}/100 skor uretildi.")

        customer_response = self.report_agent.customer_response_draft(document, checklist)
        approval = self.approval_agent.request_approval(
            {
                "case_id": case_id,
                "score": checklist.score,
                "status": checklist.status.value,
                "issue_count": len(checklist.issues),
                "top_issues": [issue.title for issue in checklist.issues[:5]],
                "customer_response_draft": customer_response,
            }
        )
        audit_trail.append(
            f"{utc_now_iso()} - Insan onayi istendi; durum={approval.status.value}; notified={approval.notified}."
        )

        report = AnalysisReport(
            case_id=case_id,
            created_at=created_at,
            document=document,
            vision=vision,
            checklist=checklist,
            approval=approval,
            markdown_report="",
            audit_trail=audit_trail,
            customer_response_draft=customer_response,
        )
        report.markdown_report = self.report_agent.markdown(report)
        return report

    def apply_human_decision(
        self,
        report: dict,
        *,
        approved: bool,
        reviewer: str,
        comment: str | None = None,
    ) -> dict:
        approval = report.setdefault("approval", {})
        approval["status"] = ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
        approval["reviewer"] = reviewer
        approval["comment"] = comment
        approval["decided_at"] = utc_now_iso()
        report.setdefault("audit_trail", []).append(
            f"{utc_now_iso()} - Insan karari kaydedildi: {approval['status']} by {reviewer}."
        )
        if approved:
            report["final_state"] = "ready_for_customer_review"
        else:
            report["final_state"] = "needs_rework_before_customer_submission"
        markdown = report.get("markdown_report")
        if isinstance(markdown, str) and markdown:
            report["markdown_report"] = (
                markdown.replace(
                    "- Insan onayi: **pending_human_approval**",
                    f"- Insan onayi: **{approval['status']}**",
                )
                + "\n## Insan Karari\n\n"
                + f"- Karar: **{approval['status']}**\n"
                + f"- Reviewer: {reviewer}\n"
                + f"- Not: {comment or 'Yok'}\n"
            )
        return report
