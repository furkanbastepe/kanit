from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("KANIT_DB_PATH", str(Path(tempfile.gettempdir()) / "kanit-api-import.sqlite3"))

from features import main
from features.services.analyzer import CaseAnalyzer
from features.services.approval_agent import ApprovalAgent
from features.services.checklist_agent import ChecklistAgent
from features.services.document_agent import DocumentAgent
from features.services.nvidia_client import NvidiaClient, NvidiaSettings
from features.services.report_agent import ReportAgent
from features.services.skill_intelligence import EvidenceToSkillService
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


class IncidentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        store = CaseStore(Path(self.tempdir.name) / "api-test.sqlite3")
        analyzer = mock_case_analyzer()
        main.store = store
        main.analyzer = analyzer
        main.skill_service = EvidenceToSkillService(store=store, case_analyzer=analyzer)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_incident_api_exposes_skill_profile_task_and_mentor_review_flow(self) -> None:
        response = self.client.post(
            "/incidents/analyze",
            data={
                "incident_type": "quality_8d_capa",
                "case_text": sample_text("01_missing_evidence"),
                "employee_code": "emp-api-001",
                "role_code": "quality_engineer",
                "team_code": "supplier_quality",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["employee_code"], "emp-api-001")
        self.assertTrue(payload["skill_gaps"])
        self.assertTrue(payload["learning_tasks"])
        self.assertIn("readiness_score", payload)

        task_id = payload["learning_tasks"][0]["task_id"]
        task_response = self.client.get(f"/learning-tasks/{task_id}")
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.json()["task_id"], task_id)

        review_response = self.client.post(
            "/mentor-reviews",
            json={
                "task_id": task_id,
                "employee_code": "emp-api-001",
                "skill_id": payload["learning_tasks"][0]["skill_id"],
                "reviewer_code": "mentor-api",
                "decision": "approved",
                "comment": "Kanita dayali aciklama yeterli.",
            },
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertEqual(review_response.json()["decision"], "approved")

        profile_response = self.client.get("/employees/emp-api-001/skill-profile")
        self.assertEqual(profile_response.status_code, 200)
        profile = profile_response.json()
        self.assertEqual(profile["employee_code"], "emp-api-001")
        self.assertGreaterEqual(profile["readiness_score"]["approved_skill_count"], 1)

        team_response = self.client.get("/teams/supplier_quality/learning-map")
        self.assertEqual(team_response.status_code, 200)
        self.assertEqual(team_response.json()["team_code"], "supplier_quality")

    def test_api_key_is_required_when_configured(self) -> None:
        import os

        os.environ["KANIT_API_KEY"] = "test-key"
        try:
            unauthorized = self.client.get("/employees/emp-api-001/skill-profile")
            authorized = self.client.get(
                "/employees/emp-api-001/skill-profile",
                headers={"X-KANIT-API-Key": "test-key"},
            )
        finally:
            os.environ.pop("KANIT_API_KEY", None)

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)

    def test_upload_size_limit_returns_413(self) -> None:
        import os

        os.environ["KANIT_MAX_UPLOAD_BYTES"] = "10"
        try:
            response = self.client.post(
                "/incidents/analyze",
                data={
                    "incident_type": "quality_8d_capa",
                    "case_text": "Problem: test",
                    "employee_code": "emp-api-002",
                },
                files={
                    "defect_photo": ("large.jpg", b"12345678901", "image/jpeg"),
                },
            )
        finally:
            os.environ.pop("KANIT_MAX_UPLOAD_BYTES", None)

        self.assertEqual(response.status_code, 413)

    def test_inductive_graph_miner_training_delta_and_positioning_endpoints(self) -> None:
        incident_ids = []
        for employee in ["emp-api-a", "emp-api-b", "emp-api-c"]:
            response = self.client.post(
                "/incidents/analyze",
                data={
                    "incident_type": "quality_8d_capa",
                    "case_text": sample_text("01_missing_evidence"),
                    "employee_code": employee,
                    "role_code": "quality_engineer",
                    "team_code": "supplier_quality",
                    "station_code": "station-final-inspection",
                },
            )
            self.assertEqual(response.status_code, 200)
            incident_ids.append(response.json()["incident_id"])

        graph_response = self.client.get(f"/incidents/{incident_ids[0]}/evidence-graph")
        self.assertEqual(graph_response.status_code, 200)
        self.assertTrue(graph_response.json()["nodes"])

        miner_response = self.client.post(
            "/skill-miner/run",
            json={"scope_type": "team", "scope_code": "supplier_quality"},
        )
        self.assertEqual(miner_response.status_code, 200)
        patterns = miner_response.json()["patterns"]
        self.assertTrue(patterns)
        self.assertIn("why_this_gap", patterns[0])

        team_patterns = self.client.get("/teams/supplier_quality/inductive-patterns")
        self.assertEqual(team_patterns.status_code, 200)
        self.assertTrue(team_patterns.json()["patterns"])

        delta_response = self.client.post(
            "/training-delta/analyze",
            json={
                "skill_id": patterns[0]["skill_id"],
                "pattern_id": patterns[0]["pattern_id"],
            },
        )
        self.assertEqual(delta_response.status_code, 200)
        self.assertEqual(delta_response.json()["sop_reference"], "reference_missing")

        positioning = self.client.get("/integrations/connected-worker-positioning")
        self.assertEqual(positioning.status_code, 200)
        self.assertIn("yerine gecmez", positioning.json()["positioning"])

    def test_shift_readiness_copq_and_export_api_flow(self) -> None:
        for employee in ["emp-api-shift-a", "emp-api-shift-b", "emp-api-shift-c"]:
            response = self.client.post(
                "/incidents/analyze",
                data={
                    "incident_type": "quality_8d_capa",
                    "case_text": sample_text("01_missing_evidence"),
                    "employee_code": employee,
                    "role_code": "quality_engineer",
                    "team_code": "supplier_quality_shift",
                    "station_code": "station-final-inspection",
                },
            )
            self.assertEqual(response.status_code, 200)

        readiness_response = self.client.post(
            "/shifts/readiness",
            json={
                "team_code": "supplier_quality_shift",
                "station_code": "station-final-inspection",
                "shift_code": "A",
                "operation_name": "Final inspection launch check",
                "employee_codes": ["emp-api-shift-a", "emp-api-shift-b", "emp-api-shift-c"],
            },
        )
        self.assertEqual(readiness_response.status_code, 200)
        readiness = readiness_response.json()
        self.assertTrue(readiness["risk_drivers"])
        self.assertIn("readiness.risk_detected", [event["event_type"] for event in readiness["integration_events"]])

        copq_response = self.client.post(
            "/risk/copq-impact",
            json={
                "scope_type": "team",
                "scope_code": "supplier_quality_shift",
                "period_label": "son 30 gun",
                "cost_profile": {
                    "scrap_cost_per_incident": 12000,
                    "rework_cost_per_incident": 4500,
                    "customer_escape_cost_per_incident": 30000,
                },
            },
        )
        self.assertEqual(copq_response.status_code, 200)
        self.assertEqual(copq_response.json()["cost_model_source"], "user_supplied_assumptions")

        roi_response = self.client.post(
            "/pilot/roi-hypothesis",
            json={
                "quality_engineers_in_scope": 3,
                "review_hours_saved_per_engineer_per_week": 2,
                "loaded_hourly_cost_try": 900,
                "incidents_per_month": 40,
                "repeated_evidence_gap_rate": 0.25,
                "mentor_closure_hours_before": 48,
                "mentor_closure_hours_after": 24,
            },
        )
        self.assertEqual(roi_response.status_code, 200)
        roi = roi_response.json()
        self.assertEqual(roi["annual_review_time_value"], 280800)
        self.assertEqual(roi["monthly_repeated_gap_exposure"], 10)
        self.assertEqual(roi["confidence"], "pilot_assumption")
        self.assertIn("garanti tasarruf degildir", roi["claims_boundary"])

        gate_response = self.client.post(
            "/gate/check",
            json={
                "team_code": "supplier_quality_shift",
                "station_code": "station-final-inspection",
                "shift_code": "A",
                "employee_code": "emp-api-shift-a",
                "acknowledged": True,
            },
        )
        self.assertEqual(gate_response.status_code, 200)
        gate = gate_response.json()
        self.assertEqual(gate["gate_status"], "NEEDS_MENTOR_REVIEW")
        self.assertTrue(gate["mentor_required"])
        self.assertEqual(gate["privacy_scope"], "station_team_role_first")
        self.assertIn("fiziksel erisim kontrolu degildir", gate["claims_boundary"])

        export_response = self.client.get(f"/exports/readiness/{readiness['readiness_id']}?target=poka")
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response.json()["payload"]["integration_contract"], "skills_matrix_enrichment")

    def test_skill_ontology_and_normalization_api(self) -> None:
        ontology_response = self.client.get("/skills/ontology")
        self.assertEqual(ontology_response.status_code, 200)
        ontology = ontology_response.json()
        self.assertTrue(
            any(item["skill_id"] == "effectiveness_verification" for item in ontology["skills"])
        )

        normalize_response = self.client.post(
            "/skills/normalize",
            json={"label": "corrective action follow-up"},
        )
        self.assertEqual(normalize_response.status_code, 200)
        self.assertEqual(normalize_response.json()["skill_id"], "effectiveness_verification")

    def test_demo_seed_readiness_creates_three_incidents_and_convergence_proof(self) -> None:
        response = self.client.post("/demo/seed-readiness")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["incident_ids"]), 3)
        self.assertEqual(payload["readiness"]["team_code"], "demo_supplier_quality")
        self.assertEqual(
            payload["convergence_proof"]["canonical_skill_id"],
            "effectiveness_verification",
        )
        self.assertEqual(payload["convergence_proof"]["incident_count"], 3)
        self.assertTrue(payload["convergence_proof"]["aliases_seen"])
        self.assertIn("score_breakdown", payload["readiness"])


if __name__ == "__main__":
    unittest.main()
