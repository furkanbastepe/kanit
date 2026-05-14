from __future__ import annotations

import unittest
from pathlib import Path

from features.services.analyzer import CaseAnalyzer
from features.services.approval_agent import ApprovalAgent
from features.services.checklist_agent import ChecklistAgent
from features.services.demo_data import demo_evidence_for_sample
from features.services.document_agent import DocumentAgent
from features.services.nvidia_client import NvidiaClient, NvidiaSettings
from features.services.report_agent import ReportAgent
from features.services.types import ApprovalStatus, TrafficLight
from features.services.vision_agent import VisionEvidenceAgent


def sample_text(name: str) -> str:
    return (Path("features/data/sample_cases") / f"{name}.txt").read_text(encoding="utf-8")


def mock_analyzer() -> CaseAnalyzer:
    nvidia = NvidiaClient(NvidiaSettings(api_key=None))
    return CaseAnalyzer(
        document_agent=DocumentAgent(nvidia),
        vision_agent=VisionEvidenceAgent(nvidia),
        checklist_agent=ChecklistAgent(),
        report_agent=ReportAgent(),
        approval_agent=ApprovalAgent(webhook_url=None),
    )


class KanitServiceTests(unittest.TestCase):
    def test_nvidia_settings_from_env_uses_string_defaults(self) -> None:
        settings = NvidiaSettings.from_env()
        self.assertIsInstance(settings.base_url, str)
        self.assertTrue(settings.base_url.startswith("https://"))

    def test_document_agent_extracts_single_line_labeled_fields(self) -> None:
        text = (
            "Problem: Braket capak. Containment: Stok ayrildi. "
            "Kok neden: Kesici takim asinmasi. Duzeltici aksiyon: Takim degisti. "
            "Etkinlik dogrulama: 100 parca temiz. Sorumlu: Kalite Muhendisi. Termin: 2026-05-20"
        )
        doc = DocumentAgent(NvidiaClient(NvidiaSettings(api_key=None))).analyze(text)

        self.assertEqual(doc.problem_statement, "Braket capak")
        self.assertEqual(doc.containment_action, "Stok ayrildi")
        self.assertEqual(doc.root_cause, "Kesici takim asinmasi")
        self.assertEqual(doc.corrective_action, "Takim degisti")
        self.assertEqual(doc.effectiveness_check, "100 parca temiz")
        self.assertEqual(doc.owner, "Kalite Muhendisi")
        self.assertEqual(doc.due_date, "2026-05-20")

    def test_missing_evidence_case_is_red_and_pending_approval(self) -> None:
        report = mock_analyzer().analyze(
            sample_text("01_missing_evidence"),
            demo_evidence_for_sample("01_missing_evidence"),
        )

        issue_codes = {issue.code for issue in report.checklist.issues}
        self.assertEqual(report.checklist.status, TrafficLight.RED)
        self.assertLess(report.checklist.score, 55)
        self.assertIn("missing_root_cause", issue_codes)
        self.assertIn("missing_effectiveness_check", issue_codes)
        self.assertIn("missing_corrective_photo", issue_codes)
        self.assertEqual(report.approval.status, ApprovalStatus.PENDING)

    def test_ready_case_is_green_but_not_auto_approved(self) -> None:
        report = mock_analyzer().analyze(
            sample_text("03_ready_for_review"),
            demo_evidence_for_sample("03_ready_for_review"),
        )

        self.assertEqual(report.checklist.status, TrafficLight.GREEN)
        self.assertGreaterEqual(report.checklist.score, 82)
        self.assertEqual(report.approval.status, ApprovalStatus.PENDING)
        self.assertIn("Insan onayi", report.markdown_report)

    def test_human_decision_changes_final_state(self) -> None:
        analyzer = mock_analyzer()
        report = analyzer.analyze(sample_text("03_ready_for_review"), demo_evidence_for_sample("03_ready_for_review"))
        updated = analyzer.apply_human_decision(
            report.to_dict(),
            approved=True,
            reviewer="Kalite Sorumlusu",
            comment="Demo onayi",
        )

        self.assertEqual(updated["approval"]["status"], ApprovalStatus.APPROVED.value)
        self.assertEqual(updated["final_state"], "ready_for_customer_review")
        self.assertIn("**approved**", updated["markdown_report"])


if __name__ == "__main__":
    unittest.main()
