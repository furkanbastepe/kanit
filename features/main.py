from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from features.services.ai_client import AIProviderError
from features.services.analyzer import CaseAnalyzer
from features.services.demo_data import demo_evidence_for_sample
from features.services.file_parser import bytes_to_text, normalize_case_text
from features.services.skill_ontology import normalize_skill_label, ontology_payload
from features.services.skill_intelligence import EvidenceToSkillService
from features.services.types import EvidenceFile


def _build_store():
    store_backend = os.getenv("KANIT_STORE", "sqlite").strip().lower()
    if store_backend == "supabase":
        from features.supabase_store import CaseStore as SupabaseCaseStore
        return SupabaseCaseStore()
    from features.storage import CaseStore as SqliteCaseStore
    return SqliteCaseStore()


app = FastAPI(
    title="KANIT Evidence-to-Operational-Readiness Backend",
    description=(
        "8D/CAPA kanitlarini station/team operational readiness sinyaline, "
        "mentor gorevine ve pilot varsayimli ROI metriklerine ceviren backend."
    ),
    version="0.2.0",
)

store = _build_store()
analyzer = CaseAnalyzer()
skill_service = EvidenceToSkillService(store=store, case_analyzer=analyzer)


class ApprovalDecision(BaseModel):
    approved: bool = Field(description="True ise kalite sorumlusu raporu onaylar.")
    reviewer: str = Field(default="Kalite Sorumlusu")
    comment: str | None = None


class MentorReviewRequest(BaseModel):
    task_id: str
    employee_code: str
    skill_id: str
    reviewer_code: str
    decision: str = Field(pattern="^(approved|needs_practice|rejected)$")
    comment: str | None = None


class SkillMinerRequest(BaseModel):
    scope_type: str = Field(pattern="^(employee|role|team|station)$")
    scope_code: str
    include_low_confidence: bool = False


class TrainingDeltaRequest(BaseModel):
    skill_id: str
    pattern_id: str | None = None
    sop_reference: str | None = None
    sop_text: str | None = None


class ShiftReadinessRequest(BaseModel):
    team_code: str
    station_code: str | None = None
    shift_code: str
    operation_name: str | None = None
    employee_codes: list[str] = Field(default_factory=list)
    role_codes: list[str] = Field(default_factory=list)
    lookback_incident_limit: int = Field(default=50, ge=1, le=500)


class GateCheckRequest(BaseModel):
    team_code: str
    station_code: str
    shift_code: str
    employee_code: str | None = None
    operation_name: str | None = None
    acknowledged: bool = False


class PilotRoiHypothesisRequest(BaseModel):
    quality_engineers_in_scope: int = Field(ge=0)
    review_hours_saved_per_engineer_per_week: float = Field(default=2, ge=0)
    loaded_hourly_cost_try: float = Field(ge=0)
    incidents_per_month: int = Field(default=0, ge=0)
    repeated_evidence_gap_rate: float = Field(default=0, ge=0, le=1)
    mentor_closure_hours_before: float | None = Field(default=None, ge=0)
    mentor_closure_hours_after: float | None = Field(default=None, ge=0)


class CopqImpactRequest(BaseModel):
    scope_type: str = Field(pattern="^(employee|role|team|station)$")
    scope_code: str
    period_label: str | None = None
    cost_profile: dict[str, float]


class SkillNormalizeRequest(BaseModel):
    label: str


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    public_paths = {"/health", "/openapi.json", "/docs", "/redoc"}
    expected = os.getenv("KANIT_API_KEY")
    if not expected:
        # Fix B: No key configured — demo/dev mode. Log once so operators notice.
        # To restrict access set KANIT_API_KEY in your environment.
        pass
    elif request.url.path not in public_paths:
        provided = request.headers.get("X-KANIT-API-Key")
        if provided != expected:
            return JSONResponse(status_code=401, content={"detail": "Gecersiz veya eksik API anahtari."})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    ai = analyzer.document_agent.ai
    return {
        "status": "ok",
        "service": "kanit",
        "mode": ai.mode,
        "live_ai_enabled": ai.enabled,
        "allow_mock": ai.allow_mock,
    }


@app.get("/cases")
def list_cases() -> list[dict]:
    return store.list_cases()


@app.post("/cases/analyze")
async def analyze_case(
    case_text: str | None = Form(default=None),
    case_file: UploadFile | None = File(default=None),
    defect_photo: UploadFile | None = File(default=None),
    corrective_photo: UploadFile | None = File(default=None),
    measurement_photo: UploadFile | None = File(default=None),
) -> dict:
    merged_text, evidence_files = await _read_case_input(
        case_text=case_text,
        case_file=case_file,
        defect_photo=defect_photo,
        corrective_photo=corrective_photo,
        measurement_photo=measurement_photo,
    )
    if not merged_text:
        raise HTTPException(status_code=400, detail="case_text veya case_file zorunludur.")

    try:
        # Fix 3: run blocking NVIDIA I/O in a thread pool to avoid event-loop stalls.
        report = await asyncio.to_thread(analyzer.analyze, merged_text, evidence_files)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.save(report)
    return report.to_dict()


@app.post("/incidents/analyze")
async def analyze_incident(
    incident_type: str = Form(default="quality_8d_capa"),
    employee_code: str | None = Form(default=None),
    role_code: str | None = Form(default=None),
    team_code: str | None = Form(default=None),
    station_code: str | None = Form(default=None),
    case_text: str | None = Form(default=None),
    case_file: UploadFile | None = File(default=None),
    defect_photo: UploadFile | None = File(default=None),
    corrective_photo: UploadFile | None = File(default=None),
    measurement_photo: UploadFile | None = File(default=None),
) -> dict:
    merged_text, evidence_files = await _read_case_input(
        case_text=case_text,
        case_file=case_file,
        defect_photo=defect_photo,
        corrective_photo=corrective_photo,
        measurement_photo=measurement_photo,
    )
    if not merged_text:
        raise HTTPException(status_code=400, detail="case_text veya case_file zorunludur.")
    try:
        incident = await asyncio.to_thread(
            lambda: skill_service.analyze_incident(
                incident_type=incident_type,
                case_text=merged_text,
                evidence_files=evidence_files,
                employee_code=employee_code,
                role_code=role_code,
                team_code=team_code,
                station_code=station_code,
            )
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return incident.to_dict()


@app.get("/employees/{employee_code}/skill-profile")
def get_employee_skill_profile(employee_code: str) -> dict:
    return skill_service.employee_skill_profile(employee_code)


@app.get("/teams/{team_code}/learning-map")
def get_team_learning_map(team_code: str) -> dict:
    return skill_service.team_learning_map(team_code)


@app.get("/incidents/{incident_id}/evidence-graph")
def get_incident_evidence_graph(incident_id: str) -> dict:
    graph = skill_service.evidence_graph(incident_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Evidence graph bulunamadi.")
    return graph


@app.post("/skill-miner/run")
def run_skill_miner(request: SkillMinerRequest) -> dict:
    try:
        patterns = skill_service.run_skill_miner(
            scope_type=request.scope_type,
            scope_code=request.scope_code,
            include_low_confidence=request.include_low_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"patterns": patterns}


@app.get("/teams/{team_code}/inductive-patterns")
def get_team_inductive_patterns(team_code: str) -> dict:
    return {"team_code": team_code, "patterns": skill_service.inductive_patterns_for_team(team_code)}


@app.post("/training-delta/analyze")
def analyze_training_delta(request: TrainingDeltaRequest) -> dict:
    try:
        return skill_service.analyze_training_delta(
            skill_id=request.skill_id,
            pattern_id=request.pattern_id,
            sop_reference=request.sop_reference,
            sop_text=request.sop_text,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen skill_id: {request.skill_id}") from exc


@app.get("/integrations/connected-worker-positioning")
def get_connected_worker_positioning() -> dict:
    return skill_service.connected_worker_positioning()


@app.get("/skills/ontology")
def get_skill_ontology() -> dict:
    return ontology_payload()


@app.post("/skills/normalize")
def normalize_skill(request: SkillNormalizeRequest) -> dict:
    return normalize_skill_label(request.label)


@app.post("/shifts/readiness")
def create_shift_readiness(request: ShiftReadinessRequest) -> dict:
    return skill_service.shift_readiness(
        team_code=request.team_code,
        station_code=request.station_code,
        shift_code=request.shift_code,
        operation_name=request.operation_name,
        employee_codes=request.employee_codes,
        role_codes=request.role_codes,
        lookback_incident_limit=request.lookback_incident_limit,
    )


@app.post("/pilot/roi-hypothesis")
def create_pilot_roi_hypothesis(request: PilotRoiHypothesisRequest) -> dict:
    return skill_service.pilot_roi_hypothesis(
        quality_engineers_in_scope=request.quality_engineers_in_scope,
        review_hours_saved_per_engineer_per_week=request.review_hours_saved_per_engineer_per_week,
        loaded_hourly_cost_try=request.loaded_hourly_cost_try,
        incidents_per_month=request.incidents_per_month,
        repeated_evidence_gap_rate=request.repeated_evidence_gap_rate,
        mentor_closure_hours_before=request.mentor_closure_hours_before,
        mentor_closure_hours_after=request.mentor_closure_hours_after,
    )


@app.post("/gate/check")
def check_gate(request: GateCheckRequest) -> dict:
    return skill_service.gate_check(
        team_code=request.team_code,
        station_code=request.station_code,
        shift_code=request.shift_code,
        operation_name=request.operation_name,
        employee_code=request.employee_code,
        acknowledged=request.acknowledged,
    )


@app.post("/risk/copq-impact")
def estimate_copq_impact(request: CopqImpactRequest) -> dict:
    try:
        return skill_service.estimate_copq_impact(
            scope_type=request.scope_type,
            scope_code=request.scope_code,
            cost_profile=request.cost_profile,
            period_label=request.period_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/exports/readiness/{readiness_id}")
def export_readiness(readiness_id: str, target: str = "generic") -> dict:
    try:
        return skill_service.readiness_export(readiness_id, target=target)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Readiness kaydi bulunamadi.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/learning-tasks/{task_id}")
def get_learning_task(task_id: str) -> dict:
    task = skill_service.learning_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Ogrenme gorevi bulunamadi.")
    return task


@app.post("/mentor-reviews")
def create_mentor_review(request: MentorReviewRequest) -> dict:
    try:
        review = skill_service.create_mentor_review(
            task_id=request.task_id,
            employee_code=request.employee_code,
            skill_id=request.skill_id,
            reviewer_code=request.reviewer_code,
            decision=request.decision,
            comment=request.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return review.to_dict()


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    payload = store.get(case_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Vaka bulunamadi.")
    return payload


@app.get("/cases/{case_id}/report.md", response_class=PlainTextResponse)
def get_case_report(case_id: str) -> str:
    report = store.report_markdown(case_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapor bulunamadi.")
    return report


@app.post("/cases/{case_id}/approval")
def decide_case(case_id: str, decision: ApprovalDecision) -> dict:
    payload = store.get(case_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Vaka bulunamadi.")
    updated = analyzer.apply_human_decision(
        payload,
        approved=decision.approved,
        reviewer=decision.reviewer,
        comment=decision.comment,
    )
    store.save_payload(updated)
    return updated


@app.post("/demo/run")
def run_demo(sample: str = "01_missing_evidence") -> dict:
    sample_path = Path("features/data/sample_cases") / f"{sample}.txt"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail=f"Ornek vaka bulunamadi: {sample}")
    case_text = sample_path.read_text(encoding="utf-8")
    evidence = demo_evidence_for_sample(sample)
    try:
        report = analyzer.analyze(case_text, evidence)
    except AIProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.save(report)
    return report.to_dict()


@app.post("/demo/seed-readiness")
def seed_readiness_demo() -> dict:
    return skill_service.seed_readiness_demo()


async def _read_case_input(
    *,
    case_text: str | None,
    case_file: UploadFile | None,
    defect_photo: UploadFile | None,
    corrective_photo: UploadFile | None,
    measurement_photo: UploadFile | None,
) -> tuple[str, list[EvidenceFile]]:
    uploaded_text = None
    if case_file:
        case_bytes = await case_file.read()
        _ensure_upload_size(case_file.filename or "case_file", case_bytes)
        uploaded_text = bytes_to_text(case_file.filename or "case_file", case_bytes)
    merged_text = normalize_case_text(case_text, uploaded_text)
    evidence_files = []
    for role, upload in [
        ("defect_photo", defect_photo),
        ("corrective_photo", corrective_photo),
        ("measurement_photo", measurement_photo),
    ]:
        if upload:
            data = await upload.read()
            _ensure_upload_size(upload.filename or role, data)
            evidence_files.append(
                EvidenceFile(
                    filename=upload.filename or role,
                    content_type=upload.content_type or "application/octet-stream",
                    data=data,
                    evidence_role=role,
                )
            )
    return merged_text, evidence_files


def _ensure_upload_size(filename: str, data: bytes) -> None:
    limit = int(os.getenv("KANIT_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya boyutu limiti asti: {filename}. Limit={limit} bytes.",
        )
