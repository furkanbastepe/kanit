from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
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


DEFAULT_DB_PATH = Path("kanit.sqlite3")


class CaseStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("KANIT_DB_PATH", DEFAULT_DB_PATH))
        self._ensure_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    report_markdown TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    incident_type TEXT NOT NULL,
                    employee_code TEXT,
                    role_code TEXT,
                    team_code TEXT,
                    station_code TEXT,
                    source_case_id TEXT NOT NULL,
                    evidence_score INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_tasks (
                    task_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    employee_code TEXT,
                    role_code TEXT,
                    team_code TEXT,
                    station_code TEXT,
                    skill_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mentor_reviews (
                    review_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    employee_code TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    reviewer_code TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "incidents", "station_code", "TEXT")
            self._ensure_column(connection, "learning_tasks", "station_code", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_graphs (
                    incident_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inductive_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_code TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS training_deltas (
                    delta_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    pattern_id TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shift_readiness (
                    readiness_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    team_code TEXT NOT NULL,
                    station_code TEXT,
                    shift_code TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    readiness_score INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS copq_estimates (
                    impact_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_code TEXT NOT NULL,
                    estimated_exposure_tl INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row[1] for row in rows}
        if column_name not in existing:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def save(self, report: AnalysisReport) -> None:
        payload = report.to_dict()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO cases
                (case_id, created_at, status, score, payload_json, report_markdown)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report.case_id,
                    report.created_at,
                    report.approval.status.value,
                    report.checklist.score,
                    json.dumps(payload, ensure_ascii=False),
                    report.markdown_report,
                ),
            )

    def save_payload(self, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO cases
                (case_id, created_at, status, score, payload_json, report_markdown)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["case_id"],
                    payload["created_at"],
                    payload.get("approval", {}).get("status", "unknown"),
                    int(payload.get("checklist", {}).get("score", 0)),
                    json.dumps(payload, ensure_ascii=False),
                    payload.get("markdown_report", ""),
                ),
            )

    def get(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def report_markdown(self, case_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_markdown FROM cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        return row[0] if row else None

    def list_cases(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT case_id, created_at, status, score FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [
            {"case_id": row[0], "created_at": row[1], "status": row[2], "score": row[3]}
            for row in rows
        ]

    def save_incident(self, incident: IncidentAnalysis) -> None:
        self.save(incident.case_report)
        payload = incident.to_dict()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO incidents
                (incident_id, created_at, incident_type, employee_code, role_code, team_code,
                 station_code, source_case_id, evidence_score, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.incident_id,
                    incident.created_at,
                    incident.incident_type,
                    incident.employee_code,
                    incident.role_code,
                    incident.team_code,
                    incident.station_code,
                    incident.case_report.case_id,
                    incident.case_report.checklist.score,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            for task in incident.learning_tasks:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO learning_tasks
                    (task_id, incident_id, created_at, employee_code, role_code, team_code, station_code,
                     skill_id, status, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.incident_id,
                        task.created_at,
                        task.employee_code,
                        task.role_code,
                        task.team_code,
                        task.station_code,
                        task.skill_id,
                        task.status,
                        json.dumps(asdict_or_dict(task), ensure_ascii=False),
                    ),
                )

    def save_evidence_graph(self, graph: EvidenceGraphSnapshot) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence_graphs
                (incident_id, created_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (
                    graph.incident_id,
                    graph.created_at,
                    json.dumps(graph.to_dict(), ensure_ascii=False),
                ),
            )

    def get_evidence_graph(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM evidence_graphs WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def list_incidents_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM incidents
                WHERE employee_code = ?
                ORDER BY created_at DESC
                """,
                (employee_code,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_incidents_for_team(self, team_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM incidents
                WHERE team_code = ?
                ORDER BY created_at DESC
                """,
                (team_code,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

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
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json FROM incidents
                WHERE {column} = ?
                ORDER BY created_at DESC
                """,
                (scope_code,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_inductive_patterns(self, patterns: list[InductivePattern]) -> None:
        with self._connect() as connection:
            for pattern in patterns:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO inductive_patterns
                    (pattern_id, created_at, scope_type, scope_code, skill_id, confidence, status, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pattern.pattern_id,
                        pattern.created_at,
                        pattern.scope_type,
                        pattern.scope_code,
                        pattern.skill_id,
                        pattern.confidence,
                        pattern.status,
                        json.dumps(pattern.to_dict(), ensure_ascii=False),
                    ),
                )

    def list_patterns_for_scope(self, scope_type: str, scope_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM inductive_patterns
                WHERE scope_type = ? AND scope_code = ?
                ORDER BY confidence DESC, created_at DESC
                """,
                (scope_type, scope_code),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_training_delta(self, delta: TrainingDelta) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO training_deltas
                (delta_id, created_at, skill_id, pattern_id, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    delta.delta_id,
                    delta.created_at,
                    delta.skill_id,
                    delta.pattern_id,
                    json.dumps(delta.to_dict(), ensure_ascii=False),
                ),
            )

    def save_shift_readiness(self, readiness: ShiftReadinessSnapshot | dict[str, Any]) -> None:
        payload = readiness if isinstance(readiness, dict) else readiness.to_dict()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO shift_readiness
                (readiness_id, created_at, team_code, station_code, shift_code,
                 risk_level, readiness_score, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["readiness_id"],
                    payload["created_at"],
                    payload["team_code"],
                    payload.get("station_code"),
                    payload["shift_code"],
                    payload["risk_level"],
                    int(payload.get("readiness_score", {}).get("score", 0)),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_shift_readiness(self, readiness_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM shift_readiness WHERE readiness_id = ?",
                (readiness_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_copq_estimate(self, estimate: CopqImpactEstimate | dict[str, Any]) -> None:
        payload = estimate if isinstance(estimate, dict) else estimate.to_dict()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO copq_estimates
                (impact_id, created_at, scope_type, scope_code, estimated_exposure_tl, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["impact_id"],
                    payload["created_at"],
                    payload["scope_type"],
                    payload["scope_code"],
                    int(payload["estimated_exposure_tl"]),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )

    def get_learning_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM learning_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_tasks_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM learning_tasks
                WHERE employee_code = ?
                ORDER BY created_at DESC
                """,
                (employee_code,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_mentor_review(self, review: MentorReview) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO mentor_reviews
                (review_id, task_id, created_at, employee_code, skill_id,
                 reviewer_code, decision, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.task_id,
                    review.created_at,
                    review.employee_code,
                    review.skill_id,
                    review.reviewer_code,
                    review.decision.value,
                    json.dumps(review.to_dict(), ensure_ascii=False),
                ),
            )

    def list_reviews_for_employee(self, employee_code: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM mentor_reviews
                WHERE employee_code = ?
                ORDER BY created_at DESC
                """,
                (employee_code,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]


def asdict_or_dict(value: LearningTask | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        "task_id": value.task_id,
        "incident_id": value.incident_id,
        "employee_code": value.employee_code,
        "role_code": value.role_code,
        "team_code": value.team_code,
        "station_code": value.station_code,
        "skill_id": value.skill_id,
        "title": value.title,
        "scenario": value.scenario,
        "expected_evidence": value.expected_evidence,
        "rubric": value.rubric,
        "status": value.status,
        "created_at": value.created_at,
    }
