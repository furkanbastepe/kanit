from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from features.services.analyzer import CaseAnalyzer
from features.services.approval_agent import ApprovalAgent
from features.services.document_agent import DocumentAgent
from features.services.nvidia_client import NvidiaClient, NvidiaSettings
from features.services.report_agent import ReportAgent
from features.services.skill_ontology import normalize_skill_label, ontology_payload
from features.services.skill_intelligence import EvidenceToSkillService
from features.services.checklist_agent import ChecklistAgent
from features.services.demo_data import demo_evidence_for_sample
from features.services.vision_agent import VisionEvidenceAgent
from features.storage import CaseStore


def sample_text(name: str) -> str:
    return (Path("features/data/sample_cases") / f"{name}.txt").read_text(encoding="utf-8")


def mock_case_analyzer() -> CaseAnalyzer:
    nvidia = NvidiaClient(NvidiaSettings(api_key=None))
    return CaseAnalyzer(
        document_agent=DocumentAgent(nvidia),
        vision_agent=VisionEvidenceAgent(nvidia),
        checklist_agent=ChecklistAgent(),
        report_agent=ReportAgent(),
        approval_agent=ApprovalAgent(webhook_url=None),
    )


class EvidenceToSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "kanit-test.sqlite3"
        self.store = CaseStore(self.db_path)
        self.service = EvidenceToSkillService(
            store=self.store,
            case_analyzer=mock_case_analyzer(),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_missing_8d_case_creates_skill_gaps_and_learning_tasks(self) -> None:
        incident = self.service.analyze_incident(
            incident_type="quality_8d_capa",
            case_text=sample_text("01_missing_evidence"),
            evidence_files=demo_evidence_for_sample("01_missing_evidence"),
            employee_code="emp-qa-001",
            role_code="quality_engineer",
            team_code="supplier_quality",
        )

        skill_ids = {gap.skill_id for gap in incident.skill_gaps}
        task_titles = {task.title for task in incident.learning_tasks}

        self.assertIn("root_cause_analysis", skill_ids)
        self.assertIn("effectiveness_verification", skill_ids)
        self.assertTrue(any("Etkinlik" in title for title in task_titles))
        self.assertEqual(incident.employee_code, "emp-qa-001")
        self.assertGreaterEqual(len(incident.audit_events), 4)

    def test_employee_profile_groups_repeated_skill_gaps_without_real_name(self) -> None:
        for sample in ["01_missing_evidence", "02_conflicting_evidence"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text(sample),
                evidence_files=demo_evidence_for_sample(sample),
                employee_code="emp-qa-002",
                role_code="quality_engineer",
                team_code="supplier_quality",
            )

        profile = self.service.employee_skill_profile("emp-qa-002")

        self.assertEqual(profile["employee_code"], "emp-qa-002")
        self.assertNotIn("employee_name", profile)
        self.assertGreaterEqual(profile["open_gap_count"], 1)
        self.assertIn("readiness_score", profile)
        self.assertTrue(any(item["incident_count"] >= 1 for item in profile["skill_gaps"]))

    def test_mentor_review_is_required_before_skill_is_ready(self) -> None:
        incident = self.service.analyze_incident(
            incident_type="quality_8d_capa",
            case_text=sample_text("01_missing_evidence"),
            evidence_files=demo_evidence_for_sample("01_missing_evidence"),
            employee_code="emp-qa-003",
            role_code="quality_engineer",
            team_code="supplier_quality",
        )
        before = self.service.employee_skill_profile("emp-qa-003")
        task_id = incident.learning_tasks[0].task_id

        self.service.create_mentor_review(
            task_id=task_id,
            employee_code="emp-qa-003",
            skill_id=incident.learning_tasks[0].skill_id,
            reviewer_code="mentor-01",
            decision="approved",
            comment="Saha kaniti kontrol edildi.",
        )
        after = self.service.employee_skill_profile("emp-qa-003")

        self.assertLess(before["readiness_score"]["score"], 82)
        self.assertGreater(after["readiness_score"]["score"], before["readiness_score"]["score"])
        self.assertNotEqual(after["readiness_score"]["status"], "ready")

    def test_team_learning_map_merges_repeated_gaps(self) -> None:
        for employee in ["emp-qa-004", "emp-qa-005"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality",
            )

        learning_map = self.service.team_learning_map("supplier_quality")

        self.assertEqual(learning_map["team_code"], "supplier_quality")
        self.assertGreaterEqual(learning_map["incident_count"], 2)
        repeated = [item for item in learning_map["top_skill_gaps"] if item["skill_id"] == "effectiveness_verification"]
        self.assertTrue(repeated)
        self.assertGreaterEqual(repeated[0]["employee_count"], 2)

    def test_webhook_failure_is_recorded_but_does_not_break_analysis(self) -> None:
        os.environ["KANIT_WEBHOOK_URL"] = "http://127.0.0.1:1/unreachable"
        try:
            service = EvidenceToSkillService(
                store=self.store,
                case_analyzer=mock_case_analyzer(),
            )
            incident = service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("03_ready_for_review"),
                evidence_files=demo_evidence_for_sample("03_ready_for_review"),
                employee_code="emp-qa-006",
                role_code="quality_engineer",
                team_code="supplier_quality",
            )
        finally:
            os.environ.pop("KANIT_WEBHOOK_URL", None)

        self.assertEqual(incident.incident_type, "quality_8d_capa")
        self.assertTrue(
            any(event.event_type == "webhook.delivery_failed" for event in incident.audit_events)
        )

    def test_incident_accepts_station_code_and_creates_graph_snapshot(self) -> None:
        incident = self.service.analyze_incident(
            incident_type="quality_8d_capa",
            case_text=sample_text("01_missing_evidence"),
            evidence_files=demo_evidence_for_sample("01_missing_evidence"),
            employee_code="emp-qa-graph",
            role_code="quality_engineer",
            team_code="supplier_quality",
            station_code="station-final-inspection",
        )

        graph = self.service.evidence_graph(incident.incident_id)

        self.assertEqual(incident.station_code, "station-final-inspection")
        self.assertIsNotNone(graph)
        assert graph is not None
        self.assertTrue(any(node["node_type"] == "incident" for node in graph["nodes"]))
        self.assertTrue(any(node["node_type"] == "skill" for node in graph["nodes"]))
        self.assertTrue(any(edge["relation_type"] == "maps_to_skill" for edge in graph["edges"]))

    def test_station_scope_can_be_used_for_pattern_mining(self) -> None:
        for sample in ["01_missing_evidence", "01_missing_evidence", "02_conflicting_evidence"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text(sample),
                evidence_files=demo_evidence_for_sample(sample),
                employee_code="emp-qa-station",
                role_code="quality_engineer",
                team_code="supplier_quality",
                station_code="station-final-inspection",
            )

        patterns = self.service.run_skill_miner(
            scope_type="station",
            scope_code="station-final-inspection",
        )

        self.assertTrue(patterns)
        self.assertTrue(any(pattern["scope_type"] == "station" for pattern in patterns))

    def test_repeated_team_incidents_create_why_this_gap_pattern(self) -> None:
        for employee in ["emp-qa-a", "emp-qa-b", "emp-qa-c"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality",
                station_code="station-final-inspection",
            )

        patterns = self.service.run_skill_miner(scope_type="team", scope_code="supplier_quality")
        effectiveness = [item for item in patterns if item["skill_id"] == "effectiveness_verification"]

        self.assertTrue(effectiveness)
        self.assertGreaterEqual(effectiveness[0]["incident_count"], 3)
        self.assertIn("3 olayda", effectiveness[0]["why_this_gap"])
        self.assertIn("missing_effectiveness_check", effectiveness[0]["why_this_gap"])
        self.assertGreaterEqual(effectiveness[0]["confidence"], 0.7)

    def test_single_incident_does_not_create_strong_pattern(self) -> None:
        self.service.analyze_incident(
            incident_type="quality_8d_capa",
            case_text=sample_text("01_missing_evidence"),
            evidence_files=demo_evidence_for_sample("01_missing_evidence"),
            employee_code="emp-qa-single",
            role_code="quality_engineer",
            team_code="single_team",
            station_code="station-single",
        )

        patterns = self.service.run_skill_miner(scope_type="team", scope_code="single_team")

        self.assertEqual(patterns, [])

    def test_training_delta_requires_reference_or_declares_missing_reference(self) -> None:
        delta = self.service.analyze_training_delta(
            skill_id="effectiveness_verification",
            pattern_id=None,
            sop_reference=None,
            sop_text=None,
        )

        self.assertEqual(delta["sop_reference"], "reference_missing")
        self.assertIn("Etkinlik dogrulama", delta["missing_training_section"])
        self.assertTrue(delta["mentor_evidence_required"])

    def test_skill_normalizer_maps_aliases_to_canonical_skill(self) -> None:
        labels = [
            "etkinlik kontrolu eksik",
            "effectiveness check missing",
            "corrective action follow-up",
            "aksiyonun calistigi kanitlanmamis",
        ]

        normalized = [normalize_skill_label(label) for label in labels]

        self.assertTrue(all(item["status"] == "matched" for item in normalized))
        self.assertEqual({item["skill_id"] for item in normalized}, {"effectiveness_verification"})

        ontology = ontology_payload()
        effectiveness = [item for item in ontology["skills"] if item["skill_id"] == "effectiveness_verification"]
        self.assertTrue(effectiveness)
        self.assertIn("etkinlik kontrolu", effectiveness[0]["synonyms"])

    def test_skill_normalizer_routes_unknown_label_to_human_review(self) -> None:
        result = normalize_skill_label("operator motivation astrology risk")

        self.assertEqual(result["status"], "needs_human_review")
        self.assertIsNone(result["skill_id"])
        self.assertLess(result["confidence"], 0.5)

    def test_shift_readiness_turns_repeated_incidents_into_operational_risk(self) -> None:
        for employee in ["emp-shift-a", "emp-shift-b", "emp-shift-c"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality",
                station_code="station-final-inspection",
            )

        readiness = self.service.shift_readiness(
            team_code="supplier_quality",
            station_code="station-final-inspection",
            shift_code="A",
            operation_name="Final inspection launch check",
            employee_codes=["emp-shift-a", "emp-shift-b", "emp-shift-c"],
        )

        self.assertEqual(readiness["team_code"], "supplier_quality")
        self.assertEqual(readiness["station_code"], "station-final-inspection")
        self.assertEqual(readiness["shift_code"], "A")
        self.assertIn(readiness["risk_level"], {"medium", "high", "critical"})
        self.assertLess(readiness["readiness_score"]["score"], 82)
        self.assertTrue(readiness["risk_drivers"])
        self.assertIn("why_this_gap", readiness["risk_drivers"][0])
        self.assertTrue(readiness["risk_drivers"][0]["evidence_trace"])
        self.assertEqual(readiness["scope_type"], "station")
        self.assertEqual(readiness["scope_code"], "station-final-inspection")
        self.assertEqual(readiness["privacy_scope"], "station_team_role_first")
        self.assertIn("dogrudan operator yetkinligi", readiness["measurement_boundary"])
        self.assertNotIn("employee_name", readiness)

        export = self.service.readiness_export(readiness["readiness_id"], target="augmentir")

        self.assertEqual(export["target"], "augmentir")
        self.assertEqual(export["payload"]["integration_contract"], "skills_matrix_enrichment")
        self.assertTrue(export["payload"]["skill_signals"])

    def test_shift_readiness_exposes_formula_based_score_breakdown(self) -> None:
        for employee in ["emp-score-a", "emp-score-b", "emp-score-c"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality_score",
                station_code="station-final-inspection",
            )

        readiness = self.service.shift_readiness(
            team_code="supplier_quality_score",
            station_code="station-final-inspection",
            shift_code="A",
            operation_name="Final inspection launch check",
            employee_codes=["emp-score-a", "emp-score-b", "emp-score-c"],
        )

        breakdown = readiness["score_breakdown"]

        self.assertEqual(breakdown["rule_version"], "readiness_v1")
        self.assertEqual(breakdown["base_score"], 100)
        self.assertIn("formula", breakdown)
        self.assertTrue(breakdown["penalties"])
        self.assertTrue(
            any(item["code"] == "repeated_canonical_gap" for item in breakdown["penalties"])
        )
        self.assertEqual(readiness["readiness_score"]["score"], breakdown["final_score"])

    def test_shift_readiness_without_incidents_is_unknown_not_ready(self) -> None:
        readiness = self.service.shift_readiness(
            team_code="empty_team",
            station_code="station-empty",
            shift_code="A",
            operation_name="Final inspection launch check",
            employee_codes=[],
        )

        self.assertEqual(readiness["risk_level"], "unknown")
        self.assertEqual(readiness["readiness_score"]["score"], 0)
        self.assertTrue(
            any(item["code"] == "no_recent_incident_evidence" for item in readiness["score_breakdown"]["penalties"])
        )

    def test_copq_impact_is_user_assumption_based_risk_proxy_not_savings_claim(self) -> None:
        for employee in ["emp-cost-a", "emp-cost-b", "emp-cost-c"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality_cost",
                station_code="station-final-inspection",
            )

        estimate = self.service.estimate_copq_impact(
            scope_type="team",
            scope_code="supplier_quality_cost",
            cost_profile={
                "scrap_cost_per_incident": 12000,
                "rework_cost_per_incident": 4500,
                "customer_escape_cost_per_incident": 30000,
            },
            period_label="son 30 gun",
        )

        self.assertEqual(estimate["scope_type"], "team")
        self.assertEqual(estimate["cost_model_source"], "user_supplied_assumptions")
        self.assertGreater(estimate["estimated_exposure_tl"], 0)
        self.assertTrue(estimate["top_cost_drivers"])
        self.assertIn("garanti etmez", estimate["claims_boundary"])
        self.assertIn("varsayim", estimate["explanation"])

    def test_pilot_roi_hypothesis_is_assumption_labeled_not_ford_calibrated(self) -> None:
        hypothesis = self.service.pilot_roi_hypothesis(
            quality_engineers_in_scope=3,
            review_hours_saved_per_engineer_per_week=2,
            loaded_hourly_cost_try=900,
            incidents_per_month=40,
            repeated_evidence_gap_rate=0.25,
            mentor_closure_hours_before=48,
            mentor_closure_hours_after=18,
        )

        self.assertEqual(hypothesis["annual_review_time_value"], 280800)
        self.assertEqual(hypothesis["monthly_repeated_gap_exposure"], 10)
        self.assertEqual(hypothesis["mentor_closure_hours_delta"], 30)
        self.assertEqual(hypothesis["confidence"], "pilot_assumption")
        self.assertIn("kalibre edilmemistir", hypothesis["claims_boundary"])

    def test_gate_acknowledgement_does_not_clear_station_readiness(self) -> None:
        for employee in ["emp-gate-a", "emp-gate-b", "emp-gate-c"]:
            self.service.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=sample_text("01_missing_evidence"),
                evidence_files=demo_evidence_for_sample("01_missing_evidence"),
                employee_code=employee,
                role_code="quality_engineer",
                team_code="supplier_quality_gate",
                station_code="station-final-inspection",
            )

        gate = self.service.gate_check(
            team_code="supplier_quality_gate",
            station_code="station-final-inspection",
            shift_code="A",
            employee_code="emp-gate-a",
            acknowledged=True,
        )

        self.assertEqual(gate["gate_status"], "NEEDS_MENTOR_REVIEW")
        self.assertTrue(gate["mentor_required"])
        self.assertEqual(gate["privacy_scope"], "station_team_role_first")
        self.assertIn("kisi skorlamaz", gate["claims_boundary"])


if __name__ == "__main__":
    unittest.main()
