from __future__ import annotations

import json
import os
from typing import Any

from features.services.types import (
    AnalysisReport,
    CopqImpactEstimate,
    EvidenceGraphSnapshot,
    IncidentAnalysis,
    InductivePattern,
    LearningTask,
    MentorReview,
    ShiftReadinessSnapshot,
    TrainingDelta,
)

try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False


def _get_client() -> "SupabaseClient":
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY ortam degiskenleri gereklidir."
        )
    return create_client(url, key)


class CaseStore:
    """Supabase-backed implementation of CaseStore.

    Interface-compatible with features/storage.py (SQLite version).
    Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY env vars to activate.
    org_id is optional; when provided, all queries are scoped to that org.
    """

    def __init__(self, db_path=None, org_id: str | None = None) -> None:
        if not _SUPABASE_AVAILABLE:
            raise ImportError(
                "supabase package is not installed. Run: pip install supabase>=2.0.0"
            )
        self._client = _get_client()
        self.org_id = org_id or os.getenv("KANIT_ORG_ID")

    def _scope(self, query):
        """Apply org_id filter when available."""
        if self.org_id:
            return query.eq("org_id", self.org_id)
        return query

    def _with_org(self, record: dict) -> dict:
        if self.org_id:
            record["org_id"] = self.org_id
        return record

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    def save(self, report: AnalysisReport) -> None:
        payload = report.to_dict()
        record = self._with_org({
            "case_id": report.case_id,
            "created_at": report.created_at,
            "status": report.approval.status.value,
            "score": report.checklist.score,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "report_markdown": report.markdown_report,
        })
        self._client.table("cases").upsert(record).execute()

    def save_payload(self, payload: dict[str, Any]) -> None:
        record = self._with_org({
            "case_id": payload["case_id"],
            "created_at": payload["created_at"],
            "status": payload.get("approval", {}).get("status", "unknown"),
            "score": int(payload.get("checklist", {}).get("score", 0)),
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "report_markdown": payload.get("markdown_report", ""),
        })
        self._client.table("cases").upsert(record).execute()

    def get(self, case_id: str) -> dict[str, Any] | None:
        q = self._scope(self._client.table("cases").select("payload_json").eq("case_id", case_id))
        result = q.execute()
        if not result.data:
            return None
        return json.loads(result.data[0]["payload_json"])

    def report_markdown(self, case_id: str) -> str | None:
        q = self._scope(self._client.table("cases").select("report_markdown").eq("case_id", case_id))
        result = q.execute()
        if not result.data:
            return None
        return result.data[0]["report_markdown"]

    def list_cases(self) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("cases")
            .select("case_id,created_at,status,score")
            .order("created_at", desc=True)
        )
        result = q.execute()
        return result.data or []

    # ------------------------------------------------------------------
    # Incidents + Learning Tasks
    # ------------------------------------------------------------------

    def save_incident(self, incident: IncidentAnalysis) -> None:
        self.save(incident.case_report)
        payload = incident.to_dict()
        record = self._with_org({
            "incident_id": incident.incident_id,
            "created_at": incident.created_at,
            "incident_type": incident.incident_type,
            "employee_code": incident.employee_code,
            "role_code": incident.role_code,
            "team_code": incident.team_code,
            "station_code": incident.station_code,
            "source_case_id": incident.case_report.case_id,
            "evidence_score": incident.case_report.checklist.score,
            "payload_json": json.dumps(payload, ensure_ascii=False),
        })
        self._client.table("incidents").upsert(record).execute()
        for task in incident.learning_tasks:
            self._save_learning_task_obj(task)

    def _save_learning_task_obj(self, task: LearningTask) -> None:
        from features.storage import asdict_or_dict
        record = self._with_org({
            "task_id": task.task_id,
            "incident_id": task.incident_id,
            "created_at": task.created_at,
            "employee_code": task.employee_code,
            "role_code": task.role_code,
            "team_code": task.team_code,
            "station_code": task.station_code,
            "skill_id": task.skill_id,
            "status": task.status,
            "payload_json": json.dumps(asdict_or_dict(task), ensure_ascii=False),
        })
        self._client.table("learning_tasks").upsert(record).execute()

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        q = self._scope(self._client.table("incidents").select("payload_json").eq("incident_id", incident_id))
        result = q.execute()
        if not result.data:
            return None
        return json.loads(result.data[0]["payload_json"])

    def list_incidents_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("incidents")
            .select("payload_json")
            .eq("employee_code", employee_code)
            .order("created_at", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]

    def list_incidents_for_team(self, team_code: str) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("incidents")
            .select("payload_json")
            .eq("team_code", team_code)
            .order("created_at", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]

    def list_incidents_for_scope(self, scope_type: str, scope_code: str) -> list[dict[str, Any]]:
        columns = {
            "employee": "employee_code",
            "role": "role_code",
            "team": "team_code",
            "station": "station_code",
        }
        column = columns.get(scope_type)
        if not column:
            raise ValueError("Desteklenen scope_type: employee, role, team, station.")
        q = self._scope(
            self._client.table("incidents")
            .select("payload_json")
            .eq(column, scope_code)
            .order("created_at", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]

    # ------------------------------------------------------------------
    # Evidence Graphs
    # ------------------------------------------------------------------

    def save_evidence_graph(self, graph: EvidenceGraphSnapshot) -> None:
        record = self._with_org({
            "incident_id": graph.incident_id,
            "created_at": graph.created_at,
            "payload_json": json.dumps(graph.to_dict(), ensure_ascii=False),
        })
        self._client.table("evidence_graphs").upsert(record).execute()

    def get_evidence_graph(self, incident_id: str) -> dict[str, Any] | None:
        q = self._scope(
            self._client.table("evidence_graphs").select("payload_json").eq("incident_id", incident_id)
        )
        result = q.execute()
        if not result.data:
            return None
        return json.loads(result.data[0]["payload_json"])

    # ------------------------------------------------------------------
    # Inductive Patterns
    # ------------------------------------------------------------------

    def save_inductive_patterns(self, patterns: list[InductivePattern]) -> None:
        for pattern in patterns:
            record = self._with_org({
                "pattern_id": pattern.pattern_id,
                "created_at": pattern.created_at,
                "scope_type": pattern.scope_type,
                "scope_code": pattern.scope_code,
                "skill_id": pattern.skill_id,
                "confidence": pattern.confidence,
                "status": pattern.status,
                "payload_json": json.dumps(pattern.to_dict(), ensure_ascii=False),
            })
            self._client.table("inductive_patterns").upsert(record).execute()

    def list_patterns_for_scope(self, scope_type: str, scope_code: str) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("inductive_patterns")
            .select("payload_json")
            .eq("scope_type", scope_type)
            .eq("scope_code", scope_code)
            .order("confidence", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]

    # ------------------------------------------------------------------
    # Training Deltas
    # ------------------------------------------------------------------

    def save_training_delta(self, delta: TrainingDelta) -> None:
        record = self._with_org({
            "delta_id": delta.delta_id,
            "created_at": delta.created_at,
            "skill_id": delta.skill_id,
            "pattern_id": delta.pattern_id,
            "payload_json": json.dumps(delta.to_dict(), ensure_ascii=False),
        })
        self._client.table("training_deltas").upsert(record).execute()

    # ------------------------------------------------------------------
    # Shift Readiness
    # ------------------------------------------------------------------

    def save_shift_readiness(self, readiness: ShiftReadinessSnapshot | dict[str, Any]) -> None:
        payload = readiness if isinstance(readiness, dict) else readiness.to_dict()
        record = self._with_org({
            "readiness_id": payload["readiness_id"],
            "created_at": payload["created_at"],
            "team_code": payload["team_code"],
            "station_code": payload.get("station_code"),
            "shift_code": payload["shift_code"],
            "risk_level": payload["risk_level"],
            "readiness_score": int(payload.get("readiness_score", {}).get("score", 0)),
            "payload_json": json.dumps(payload, ensure_ascii=False),
        })
        self._client.table("shift_readiness").upsert(record).execute()

    def get_shift_readiness(self, readiness_id: str) -> dict[str, Any] | None:
        q = self._scope(
            self._client.table("shift_readiness").select("payload_json").eq("readiness_id", readiness_id)
        )
        result = q.execute()
        if not result.data:
            return None
        return json.loads(result.data[0]["payload_json"])

    # ------------------------------------------------------------------
    # COPQ Estimates
    # ------------------------------------------------------------------

    def save_copq_estimate(self, estimate: CopqImpactEstimate | dict[str, Any]) -> None:
        payload = estimate if isinstance(estimate, dict) else estimate.to_dict()
        record = self._with_org({
            "impact_id": payload["impact_id"],
            "created_at": payload["created_at"],
            "scope_type": payload["scope_type"],
            "scope_code": payload["scope_code"],
            "estimated_exposure_tl": int(payload["estimated_exposure_tl"]),
            "payload_json": json.dumps(payload, ensure_ascii=False),
        })
        self._client.table("copq_estimates").upsert(record).execute()

    # ------------------------------------------------------------------
    # Learning Tasks
    # ------------------------------------------------------------------

    def get_learning_task(self, task_id: str) -> dict[str, Any] | None:
        q = self._scope(
            self._client.table("learning_tasks").select("payload_json").eq("task_id", task_id)
        )
        result = q.execute()
        if not result.data:
            return None
        return json.loads(result.data[0]["payload_json"])

    def list_tasks_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("learning_tasks")
            .select("payload_json")
            .eq("employee_code", employee_code)
            .order("created_at", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]

    # ------------------------------------------------------------------
    # Mentor Reviews
    # ------------------------------------------------------------------

    def save_mentor_review(self, review: MentorReview) -> None:
        record = self._with_org({
            "review_id": review.review_id,
            "task_id": review.task_id,
            "created_at": review.created_at,
            "employee_code": review.employee_code,
            "skill_id": review.skill_id,
            "reviewer_code": review.reviewer_code,
            "decision": review.decision.value,
            "payload_json": json.dumps(review.to_dict(), ensure_ascii=False),
        })
        self._client.table("mentor_reviews").upsert(record).execute()

    def list_reviews_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        q = self._scope(
            self._client.table("mentor_reviews")
            .select("payload_json")
            .eq("employee_code", employee_code)
            .order("created_at", desc=True)
        )
        result = q.execute()
        return [json.loads(r["payload_json"]) for r in (result.data or [])]
