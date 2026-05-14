from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TrafficLight(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class ApprovalStatus(str, Enum):
    PENDING = "pending_human_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class MentorDecision(str, Enum):
    APPROVED = "approved"
    NEEDS_PRACTICE = "needs_practice"
    REJECTED = "rejected"


@dataclass(slots=True)
class EvidenceFile:
    filename: str
    content_type: str
    data: bytes
    evidence_role: str


@dataclass(slots=True)
class DocumentFindings:
    problem_statement: str | None = None
    containment_action: str | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    effectiveness_check: str | None = None
    owner: str | None = None
    due_date: str | None = None
    raw_summary: str = ""
    extracted_sections: dict[str, str] = field(default_factory=dict)
    source: str = "heuristic"
    # Per-field extraction metadata for audit trail and technical trust
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_extraction_mode: dict[str, str] = field(default_factory=dict)
    field_source_spans: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class VisionFinding:
    filename: str
    evidence_role: str
    observed_items: list[str]
    missing_items: list[str]
    confidence: float
    raw_observation: str
    source: str = "heuristic"


@dataclass(slots=True)
class ChecklistIssue:
    code: str
    severity: str
    title: str
    detail: str
    suggested_action: str


@dataclass(slots=True)
class ChecklistResult:
    score: int
    status: TrafficLight
    issues: list[ChecklistIssue]
    strengths: list[str]


@dataclass(slots=True)
class ApprovalResult:
    status: ApprovalStatus
    reviewer: str | None = None
    comment: str | None = None
    external_workflow_id: str | None = None
    notified: bool = False
    decided_at: str | None = None


@dataclass(slots=True)
class AnalysisReport:
    case_id: str
    created_at: str
    document: DocumentFindings
    vision: list[VisionFinding]
    checklist: ChecklistResult
    approval: ApprovalResult
    markdown_report: str
    audit_trail: list[str]
    customer_response_draft: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Skill:
    skill_id: str
    title: str
    category: str
    description: str


@dataclass(slots=True)
class SkillGap:
    skill_id: str
    title: str
    severity: str
    source_issue_code: str
    incident_id: str
    detail: str
    recommended_action: str
    confidence: float = 1.0


@dataclass(slots=True)
class LearningNode:
    node_id: str
    skill_id: str
    title: str
    why_it_matters: str
    practice_prompt: str
    success_criteria: str


@dataclass(slots=True)
class LearningTask:
    task_id: str
    incident_id: str
    employee_code: str | None
    role_code: str | None
    team_code: str | None
    station_code: str | None
    skill_id: str
    title: str
    scenario: str
    expected_evidence: list[str]
    rubric: list[str]
    status: str
    created_at: str


@dataclass(slots=True)
class MentorReview:
    review_id: str
    task_id: str
    employee_code: str
    skill_id: str
    reviewer_code: str
    decision: MentorDecision
    comment: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReadinessScore:
    score: int
    status: str
    open_gap_count: int
    approved_skill_count: int
    explanation: str


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    message: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceGraphNode:
    node_id: str
    node_type: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceGraphEdge:
    edge_id: str
    incident_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceGraphSnapshot:
    incident_id: str
    created_at: str
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InductivePattern:
    pattern_id: str
    created_at: str
    scope_type: str
    scope_code: str
    skill_id: str
    title: str
    incident_count: int
    issue_counts: dict[str, int]
    average_evidence_score: int
    severity_counts: dict[str, int]
    confidence: float
    why_this_gap: str
    recommendation: str
    status: str = "suggested"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrainingDelta:
    delta_id: str
    created_at: str
    skill_id: str
    title: str
    pattern_id: str | None
    sop_reference: str | None
    missing_training_section: str
    micro_scenario: str
    mentor_evidence_required: list[str]
    confidence: float
    source: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ShiftReadinessSnapshot:
    readiness_id: str
    created_at: str
    team_code: str
    station_code: str | None
    shift_code: str
    operation_name: str | None
    employee_codes: list[str]
    incident_count: int
    readiness_score: ReadinessScore
    score_breakdown: dict[str, Any]
    risk_level: str
    risk_drivers: list[dict[str, Any]]
    recommended_actions: list[dict[str, Any]]
    evidence_trace: list[dict[str, Any]]
    integration_events: list[AuditEvent]
    claims_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CopqImpactEstimate:
    impact_id: str
    created_at: str
    scope_type: str
    scope_code: str
    period_label: str | None
    incident_count: int
    cost_model_source: str
    cost_profile: dict[str, float]
    estimated_exposure_tl: int
    top_cost_drivers: list[dict[str, Any]]
    explanation: str
    claims_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class IncidentAnalysis:
    incident_id: str
    incident_type: str
    created_at: str
    employee_code: str | None
    role_code: str | None
    team_code: str | None
    station_code: str | None
    case_report: AnalysisReport
    skill_gaps: list[SkillGap]
    learning_nodes: list[LearningNode]
    learning_tasks: list[LearningTask]
    readiness_score: ReadinessScore
    audit_events: list[AuditEvent]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
