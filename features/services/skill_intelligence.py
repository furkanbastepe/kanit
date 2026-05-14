from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from statistics import mean
from typing import Any
from uuid import uuid4

from features.services.analyzer import CaseAnalyzer
from features.services.demo_data import demo_readiness_cases, demo_readiness_evidence
from features.services.evidence_graph import IncidentEvidenceGraphService
from features.services.inductive_miner import (
    InductiveSkillMiner,
    TrainingDeltaService,
    connected_worker_positioning,
)
from features.services.skill_catalog import SKILL_CATALOG
from features.services.skill_ontology import canonical_skill_id_for_issue, normalize_skill_label
from features.services.readiness_scoring import ReadinessScorer
from features.services.types import (
    AuditEvent,
    CopqImpactEstimate,
    EvidenceFile,
    IncidentAnalysis,
    LearningNode,
    LearningTask,
    MentorDecision,
    MentorReview,
    ReadinessScore,
    ShiftReadinessSnapshot,
    SkillGap,
    utc_now_iso,
)
from features.storage import CaseStore


ISSUE_TO_SKILL: dict[str, str] = {
    "missing_problem_statement": "problem_definition",
    "missing_containment_action": "containment_planning",
    "missing_root_cause": "root_cause_analysis",
    "missing_corrective_action": "corrective_action_design",
    "missing_preventive_action": "corrective_action_design",
    "missing_effectiveness_check": "effectiveness_verification",
    "missing_owner": "action_ownership",
    "missing_due_date": "action_ownership",
    "missing_defect_photo": "visual_evidence_capture",
    "missing_corrective_photo": "visual_evidence_capture",
}


class EvidenceToSkillService:
    def __init__(
        self,
        store: CaseStore | None = None,
        case_analyzer: CaseAnalyzer | None = None,
        webhook_dispatcher: "WebhookDispatcher | None" = None,
        graph_service: IncidentEvidenceGraphService | None = None,
        skill_miner: InductiveSkillMiner | None = None,
        training_delta_service: TrainingDeltaService | None = None,
        readiness_scorer: ReadinessScorer | None = None,
    ) -> None:
        self.store = store or CaseStore()
        self.case_analyzer = case_analyzer or CaseAnalyzer()
        self.webhooks = webhook_dispatcher or WebhookDispatcher.from_env()
        self.graph_service = graph_service or IncidentEvidenceGraphService()
        self.skill_miner = skill_miner or InductiveSkillMiner()
        self.training_delta_service = training_delta_service or TrainingDeltaService()
        self.readiness_scorer = readiness_scorer or ReadinessScorer()

    def analyze_incident(
        self,
        *,
        incident_type: str,
        case_text: str,
        evidence_files: list[EvidenceFile],
        employee_code: str | None = None,
        role_code: str | None = None,
        team_code: str | None = None,
        station_code: str | None = None,
    ) -> IncidentAnalysis:
        if incident_type != "quality_8d_capa":
            raise ValueError("Ilk surum yalnizca quality_8d_capa incident tipini destekler.")

        incident_id = f"incident_{uuid4().hex[:12]}"
        created_at = utc_now_iso()
        audit_events = [
            AuditEvent("incident.received", "Incident alindi.", created_at, {"incident_type": incident_type}),
        ]

        report = self.case_analyzer.analyze(case_text, evidence_files)
        audit_events.append(
            AuditEvent(
                "incident.case_analyzed",
                "8D/CAPA kanit analizi tamamlandi.",
                utc_now_iso(),
                {"case_id": report.case_id, "score": report.checklist.score},
            )
        )

        skill_gaps = self._map_skill_gaps(incident_id, report.checklist.issues)
        audit_events.append(
            AuditEvent(
                "skill_gap.detected",
                f"{len(skill_gaps)} beceri acigi bulundu.",
                utc_now_iso(),
                {"skill_ids": [gap.skill_id for gap in skill_gaps]},
            )
        )

        learning_nodes = [self._learning_node_for(gap) for gap in skill_gaps]
        learning_tasks = [
            self._learning_task_for(
                incident_id=incident_id,
                gap=gap,
                employee_code=employee_code,
                role_code=role_code,
                team_code=team_code,
                station_code=station_code,
                case_summary=report.document.raw_summary,
            )
            for gap in skill_gaps
        ]
        audit_events.append(
            AuditEvent(
                "learning_task.created",
                f"{len(learning_tasks)} ogrenme gorevi olusturuldu.",
                utc_now_iso(),
                {"task_ids": [task.task_id for task in learning_tasks]},
            )
        )
        if learning_tasks:
            audit_events.append(
                AuditEvent(
                    "mentor_review.requested",
                    "Mentor onayi bekleyen ogrenme gorevleri acildi.",
                    utc_now_iso(),
                    {"task_ids": [task.task_id for task in learning_tasks]},
                )
            )

        readiness = self._readiness_from_values(
            evidence_scores=[report.checklist.score],
            skill_ids=[gap.skill_id for gap in skill_gaps],
            approved_skill_ids=[],
        )
        incident = IncidentAnalysis(
            incident_id=incident_id,
            incident_type=incident_type,
            created_at=created_at,
            employee_code=employee_code,
            role_code=role_code,
            team_code=team_code,
            station_code=station_code,
            case_report=report,
            skill_gaps=skill_gaps,
            learning_nodes=learning_nodes,
            learning_tasks=learning_tasks,
            readiness_score=readiness,
            audit_events=audit_events,
        )

        graph = self.graph_service.build(incident)
        self.store.save_evidence_graph(graph)
        incident.audit_events.append(
            AuditEvent(
                "evidence_graph.created",
                "Incident evidence graph olusturuldu.",
                utc_now_iso(),
                {"node_count": len(graph.nodes), "edge_count": len(graph.edges)},
            )
        )
        self._dispatch_and_record(incident)
        self.store.save_incident(incident)
        return incident

    def employee_skill_profile(self, employee_code: str) -> dict[str, Any]:
        incidents = self.store.list_incidents_for_employee(employee_code)
        reviews = self.store.list_reviews_for_employee(employee_code)
        approved_skill_ids = {
            review["skill_id"]
            for review in reviews
            if review.get("decision") == MentorDecision.APPROVED.value
        }
        gaps = _flatten_gaps(incidents)
        scores = [_incident_score(incident) for incident in incidents]
        grouped = self._group_gaps(gaps, approved_skill_ids)
        readiness = self._readiness_from_values(
            evidence_scores=scores,
            skill_ids=[gap["skill_id"] for gap in gaps],
            approved_skill_ids=list(approved_skill_ids),
        )
        return {
            "employee_code": employee_code,
            "incident_count": len(incidents),
            "open_gap_count": readiness.open_gap_count,
            "readiness_score": _readiness_dict(readiness),
            "skill_gaps": grouped,
            "learning_tasks": self.store.list_tasks_for_employee(employee_code),
        }

    def team_learning_map(self, team_code: str) -> dict[str, Any]:
        incidents = self.store.list_incidents_for_team(team_code)
        gaps = _flatten_gaps(incidents)
        by_skill: dict[str, dict[str, Any]] = {}
        for gap in gaps:
            entry = by_skill.setdefault(
                gap["skill_id"],
                {
                    "skill_id": gap["skill_id"],
                    "title": gap["title"],
                    "incident_count": 0,
                    "employee_codes": set(),
                    "severity_counts": Counter(),
                },
            )
            entry["incident_count"] += 1
            if gap.get("employee_code"):
                entry["employee_codes"].add(gap["employee_code"])
            entry["severity_counts"][gap["severity"]] += 1

        top_skill_gaps = []
        for entry in by_skill.values():
            severity_counts = dict(entry["severity_counts"])
            top_skill_gaps.append(
                {
                    "skill_id": entry["skill_id"],
                    "title": entry["title"],
                    "incident_count": entry["incident_count"],
                    "employee_count": len(entry["employee_codes"]),
                    "severity_counts": severity_counts,
                }
            )
        top_skill_gaps.sort(key=lambda item: (-item["incident_count"], item["skill_id"]))
        employee_codes = {incident.get("employee_code") for incident in incidents if incident.get("employee_code")}
        return {
            "team_code": team_code,
            "incident_count": len(incidents),
            "employee_count": len(employee_codes),
            "top_skill_gaps": top_skill_gaps,
        }

    def create_mentor_review(
        self,
        *,
        task_id: str,
        employee_code: str,
        skill_id: str,
        reviewer_code: str,
        decision: str,
        comment: str | None = None,
    ) -> MentorReview:
        task = self.store.get_learning_task(task_id)
        if not task:
            raise ValueError("Ogrenme gorevi bulunamadi.")
        mentor_decision = MentorDecision(decision)
        review = MentorReview(
            review_id=f"review_{uuid4().hex[:12]}",
            task_id=task_id,
            employee_code=employee_code,
            skill_id=skill_id,
            reviewer_code=reviewer_code,
            decision=mentor_decision,
            comment=comment,
            created_at=utc_now_iso(),
        )
        self.store.save_mentor_review(review)
        return review

    def learning_task(self, task_id: str) -> dict[str, Any] | None:
        return self.store.get_learning_task(task_id)

    def evidence_graph(self, incident_id: str) -> dict[str, Any] | None:
        return self.store.get_evidence_graph(incident_id)

    def run_skill_miner(
        self,
        *,
        scope_type: str,
        scope_code: str,
        include_low_confidence: bool = False,
    ) -> list[dict[str, Any]]:
        incidents = self.store.list_incidents_for_scope(scope_type, scope_code)
        patterns = self.skill_miner.mine(
            incidents=incidents,
            scope_type=scope_type,
            scope_code=scope_code,
            include_low_confidence=include_low_confidence,
        )
        self.store.save_inductive_patterns(patterns)
        return [pattern.to_dict() for pattern in patterns]

    def inductive_patterns_for_team(self, team_code: str) -> list[dict[str, Any]]:
        stored = self.store.list_patterns_for_scope("team", team_code)
        if stored:
            return stored
        return self.run_skill_miner(scope_type="team", scope_code=team_code)

    def analyze_training_delta(
        self,
        *,
        skill_id: str,
        pattern_id: str | None,
        sop_reference: str | None,
        sop_text: str | None,
    ) -> dict[str, Any]:
        delta = self.training_delta_service.analyze(
            skill_id=skill_id,
            pattern_id=pattern_id,
            sop_reference=sop_reference,
            sop_text=sop_text,
        )
        self.store.save_training_delta(delta)
        return delta.to_dict()

    def connected_worker_positioning(self) -> dict[str, str]:
        return connected_worker_positioning()

    def shift_readiness(
        self,
        *,
        team_code: str,
        station_code: str | None,
        shift_code: str,
        operation_name: str | None,
        employee_codes: list[str] | None = None,
        role_codes: list[str] | None = None,
        lookback_incident_limit: int = 50,
    ) -> dict[str, Any]:
        incidents = self._filtered_incidents(
            team_code=team_code,
            station_code=station_code,
            employee_codes=employee_codes,
            role_codes=role_codes,
            limit=lookback_incident_limit,
        )
        gaps = _flatten_gaps(incidents)
        scores = [_incident_score(incident) for incident in incidents]
        scoped_employee_codes = employee_codes or _employee_codes_from_incidents(incidents)
        approved_skill_ids = self._approved_skill_ids(scoped_employee_codes)
        readiness_score = self._readiness_from_values(
            evidence_scores=scores,
            skill_ids=[gap["skill_id"] for gap in gaps],
            approved_skill_ids=list(approved_skill_ids),
        )
        risk_drivers = self._risk_drivers_from_gaps(gaps, incidents)
        score_breakdown = self.readiness_scorer.score(
            evidence_scores=scores,
            skill_ids=[gap["skill_id"] for gap in gaps],
            approved_skill_ids=list(approved_skill_ids),
            risk_drivers=risk_drivers,
        )
        readiness_score = ReadinessScore(
            score=score_breakdown["final_score"],
            status=(
                "ready"
                if score_breakdown["final_score"] >= 82 and readiness_score.open_gap_count == 0
                else "needs_practice"
                if readiness_score.open_gap_count
                else "watch"
            ),
            open_gap_count=readiness_score.open_gap_count,
            approved_skill_count=readiness_score.approved_skill_count,
            explanation=(
                f"{score_breakdown['formula']} ({score_breakdown['rule_version']}); "
                f"acik beceri {readiness_score.open_gap_count}."
            ),
        )
        risk_level = _risk_level(readiness_score.score, risk_drivers)
        recommended_actions = self._recommended_actions_from_drivers(risk_drivers, risk_level)
        evidence_trace = _evidence_trace_for_drivers(risk_drivers)
        integration_events = self._readiness_integration_events(
            risk_level=risk_level,
            team_code=team_code,
            station_code=station_code,
            shift_code=shift_code,
            risk_drivers=risk_drivers,
        )

        snapshot = ShiftReadinessSnapshot(
            readiness_id=f"ready_{uuid4().hex[:12]}",
            created_at=utc_now_iso(),
            team_code=team_code,
            station_code=station_code,
            shift_code=shift_code,
            operation_name=operation_name,
            employee_codes=scoped_employee_codes,
            incident_count=len(incidents),
            readiness_score=readiness_score,
            score_breakdown=score_breakdown,
            risk_level=risk_level,
            risk_drivers=risk_drivers,
            recommended_actions=recommended_actions,
            evidence_trace=evidence_trace,
            integration_events=integration_events,
            claims_boundary=(
                "Bu skor kisi performansini cezalandirmak icin degil, operasyon baslamadan once "
                "istasyon/takim/rol seviyesinde kanita dayali operational readiness riskini gorunur kilmak icindir."
            ),
        )
        payload = snapshot.to_dict()
        payload.update(
            {
                "scope_type": "station" if station_code else "team",
                "scope_code": station_code or team_code,
                "privacy_scope": "station_team_role_first",
                "measurement_boundary": (
                    "8D/CAPA metni dogrudan operator yetkinligi kanitlamaz; "
                    "evidence/process readiness ve station/team risk sinyali uretir."
                ),
                "pilot_boundary": "Gercek ROI ve maliyet kalibrasyonu yetkili 90 gunluk pilot verisi gerektirir.",
            }
        )
        self.store.save_shift_readiness(payload)
        return payload

    def pilot_roi_hypothesis(
        self,
        *,
        quality_engineers_in_scope: int,
        review_hours_saved_per_engineer_per_week: float,
        loaded_hourly_cost_try: float,
        incidents_per_month: int,
        repeated_evidence_gap_rate: float,
        mentor_closure_hours_before: float | None = None,
        mentor_closure_hours_after: float | None = None,
    ) -> dict[str, Any]:
        annual_review_time_value = int(
            round(
                quality_engineers_in_scope
                * review_hours_saved_per_engineer_per_week
                * loaded_hourly_cost_try
                * 52
            )
        )
        monthly_repeated_gap_exposure = round(incidents_per_month * repeated_evidence_gap_rate, 2)
        closure_delta = None
        if mentor_closure_hours_before is not None and mentor_closure_hours_after is not None:
            closure_delta = round(max(0.0, mentor_closure_hours_before - mentor_closure_hours_after), 2)

        return {
            "hypothesis_id": f"hyp_{uuid4().hex[:12]}",
            "created_at": utc_now_iso(),
            "currency": "TRY",
            "confidence": "pilot_assumption",
            "cost_model_source": "user_supplied_assumptions",
            "quality_engineers_in_scope": quality_engineers_in_scope,
            "review_hours_saved_per_engineer_per_week": review_hours_saved_per_engineer_per_week,
            "loaded_hourly_cost_try": loaded_hourly_cost_try,
            "incidents_per_month": incidents_per_month,
            "repeated_evidence_gap_rate": repeated_evidence_gap_rate,
            "monthly_repeated_gap_exposure": monthly_repeated_gap_exposure,
            "annual_review_time_value": annual_review_time_value,
            "mentor_closure_hours_before": mentor_closure_hours_before,
            "mentor_closure_hours_after": mentor_closure_hours_after,
            "mentor_closure_hours_delta": closure_delta,
            "formula": (
                "quality_engineers_in_scope * review_hours_saved_per_engineer_per_week "
                "* loaded_hourly_cost_try * 52"
            ),
            "claims_boundary": (
                "Bu hesap garanti tasarruf degildir; Ford veya Ford Otosan gercek maliyetleriyle "
                "kalibre edilmemistir. Yetkili pilot verisiyle dogrulanmasi gereken varsayimdir."
            ),
        }

    def gate_check(
        self,
        *,
        team_code: str,
        station_code: str,
        shift_code: str,
        operation_name: str | None = None,
        employee_code: str | None = None,
        acknowledged: bool = False,
    ) -> dict[str, Any]:
        readiness = self.shift_readiness(
            team_code=team_code,
            station_code=station_code,
            shift_code=shift_code,
            operation_name=operation_name,
            employee_codes=[employee_code] if employee_code else [],
        )
        score = int(readiness["readiness_score"]["score"])
        risk_drivers = readiness.get("risk_drivers", [])
        action = readiness.get("recommended_actions", [{}])[0]
        if readiness["risk_level"] == "unknown":
            gate_status = "UNKNOWN"
        elif score >= 82 and not risk_drivers:
            gate_status = "CLEARED"
        elif acknowledged:
            gate_status = "NEEDS_MENTOR_REVIEW"
        else:
            gate_status = "ACTION_REQUIRED"

        return {
            "gate_status": gate_status,
            "readiness_id": readiness["readiness_id"],
            "readiness_score": score,
            "risk_level": readiness["risk_level"],
            "team_code": team_code,
            "station_code": station_code,
            "shift_code": shift_code,
            "skill_id": action.get("skill_id"),
            "title": action.get("title") or "Standart vardiya oncesi kontrol",
            "reason": action.get("reason") or "Secilen kapsamda manuel review gerekli.",
            "micro_practice": {
                "prompt": "Bu istasyonda riski kapatmak icin hangi olculebilir kaniti mentor onayina sunarsin?",
                "expected_evidence": action.get("expected_evidence", ["Mentor onayi"]),
            },
            "mentor_required": gate_status in {"ACTION_REQUIRED", "NEEDS_MENTOR_REVIEW"},
            "privacy_scope": "station_team_role_first",
            "claims_boundary": (
                "Bu gate fiziksel erisim kontrolu degildir; kisi skorlamaz. "
                "Mentor onayli kocluk ve station/team readiness gorunurlugu icin demo durumudur."
            ),
        }

    def seed_readiness_demo(self) -> dict[str, Any]:
        team_code = "demo_supplier_quality"
        station_code = "station-final-inspection"
        shift_code = "A"
        operation_name = "Final inspection launch check"
        incident_ids = []
        aliases_seen = []
        employee_codes = []
        for item in demo_readiness_cases():
            employee_code = str(item["employee_code"])
            employee_codes.append(employee_code)
            alias_label = str(item["alias_label"])
            aliases_seen.append(normalize_skill_label(alias_label))
            incident = self.analyze_incident(
                incident_type="quality_8d_capa",
                case_text=str(item["case_text"]),
                evidence_files=demo_readiness_evidence(),
                employee_code=employee_code,
                role_code="quality_engineer",
                team_code=team_code,
                station_code=station_code,
            )
            incident_ids.append(incident.incident_id)
        readiness = self.shift_readiness(
            team_code=team_code,
            station_code=station_code,
            shift_code=shift_code,
            operation_name=operation_name,
            employee_codes=employee_codes,
        )
        canonical_skill_id = "effectiveness_verification"
        matching_incidents = [
            incident
            for incident in self.store.list_incidents_for_team(team_code)
            if any(gap.get("skill_id") == canonical_skill_id for gap in incident.get("skill_gaps", []))
        ]
        # Expose the first pending demo task_id so the frontend gate simulation can call /mentor-reviews
        demo_task_id = None
        demo_tasks = self.store.list_tasks_for_employee(employee_codes[0]) if employee_codes else []
        if demo_tasks:
            demo_task_id = demo_tasks[0].get("task_id")
        return {
            "demo_name": "quality_to_readiness_golden_path",
            "incident_ids": incident_ids,
            "readiness": readiness,
            "demo_task_id": demo_task_id,
            "demo_employee_code": employee_codes[0] if employee_codes else "demo-operator-01",
            "convergence_proof": {
                "canonical_skill_id": canonical_skill_id,
                "incident_count": len({incident["incident_id"] for incident in matching_incidents}),
                "aliases_seen": aliases_seen,
                "message": (
                    "Uc farkli ifade tek canonical beceri dugumune baglandi: "
                    f"{canonical_skill_id}."
                ),
            },
        }

    def estimate_copq_impact(
        self,
        *,
        scope_type: str,
        scope_code: str,
        cost_profile: dict[str, float],
        period_label: str | None = None,
    ) -> dict[str, Any]:
        incidents = self.store.list_incidents_for_scope(scope_type, scope_code)
        gaps = _flatten_gaps(incidents)
        drivers = self._risk_drivers_from_gaps(gaps, incidents)
        scrap_cost = _cost_profile_value(cost_profile, "scrap_cost_per_incident")
        rework_cost = _cost_profile_value(cost_profile, "rework_cost_per_incident")
        escape_cost = _cost_profile_value(cost_profile, "customer_escape_cost_per_incident")
        top_cost_drivers: list[dict[str, Any]] = []
        for driver in drivers:
            severity_multiplier = 1 + (driver["severity_counts"].get("high", 0) * 0.35)
            severity_multiplier += driver["severity_counts"].get("medium", 0) * 0.18
            evidence_multiplier = 1.35 if driver["average_evidence_score"] < 55 else 1.15
            escape_probability = 0.18 if driver["severity_counts"].get("high", 0) else 0.08
            exposure = driver["incident_count"] * (
                ((scrap_cost + rework_cost) * severity_multiplier * evidence_multiplier)
                + (escape_cost * escape_probability)
            )
            top_cost_drivers.append(
                {
                    "skill_id": driver["skill_id"],
                    "title": driver["title"],
                    "incident_count": driver["incident_count"],
                    "estimated_exposure_tl": int(round(exposure)),
                    "calculation": {
                        "scrap_cost_per_incident": scrap_cost,
                        "rework_cost_per_incident": rework_cost,
                        "customer_escape_cost_per_incident": escape_cost,
                        "severity_multiplier": round(severity_multiplier, 2),
                        "evidence_multiplier": evidence_multiplier,
                        "customer_escape_probability": escape_probability,
                    },
                    "why_this_gap": driver["why_this_gap"],
                }
            )
        top_cost_drivers.sort(key=lambda item: (-item["estimated_exposure_tl"], item["skill_id"]))
        estimated_exposure = sum(item["estimated_exposure_tl"] for item in top_cost_drivers)
        estimate = CopqImpactEstimate(
            impact_id=f"impact_{uuid4().hex[:12]}",
            created_at=utc_now_iso(),
            scope_type=scope_type,
            scope_code=scope_code,
            period_label=period_label,
            incident_count=len(incidents),
            cost_model_source="user_supplied_assumptions",
            cost_profile={
                "scrap_cost_per_incident": scrap_cost,
                "rework_cost_per_incident": rework_cost,
                "customer_escape_cost_per_incident": escape_cost,
            },
            estimated_exposure_tl=int(estimated_exposure),
            top_cost_drivers=top_cost_drivers[:5],
            explanation=(
                f"{period_label or 'secilen donem'} icin hesap, kullanicinin maliyet varsayimlarini "
                "tekrar eden beceri acigi, seviye ve kanit zayifligi sinyalleriyle carpistiran "
                "bir risk proxy'sidir."
            ),
            claims_boundary=(
                "Bu model scrap azalisi veya tasarruf garanti etmez; pilot onceligi ve kalite maliyeti "
                "tartismasi icin varsayim bazli bir karar destegi uretir."
            ),
        )
        self.store.save_copq_estimate(estimate)
        return estimate.to_dict()

    def readiness_export(self, readiness_id: str, *, target: str = "generic") -> dict[str, Any]:
        readiness = self.store.get_shift_readiness(readiness_id)
        if not readiness:
            raise KeyError(readiness_id)
        normalized_target = target.lower()
        supported = {"generic", "poka", "augmentir", "lms", "qms", "powerbi", "n8n"}
        if normalized_target not in supported:
            raise ValueError(f"Desteklenen target degerleri: {', '.join(sorted(supported))}.")
        skill_signals = [
            {
                "skill_id": driver["skill_id"],
                "title": driver["title"],
                "signal": driver["why_this_gap"],
                "confidence": driver["confidence"],
                "readiness_action": driver["recommended_action"],
                "source_incidents": [trace["incident_id"] for trace in driver["evidence_trace"]],
            }
            for driver in readiness.get("risk_drivers", [])
        ]
        payload = {
            "integration_contract": "skills_matrix_enrichment",
            "source_system": "kanit_readiness_engine",
            "target_story": _target_story(normalized_target),
            "readiness_summary": {
                "readiness_id": readiness["readiness_id"],
                "team_code": readiness["team_code"],
                "station_code": readiness.get("station_code"),
                "shift_code": readiness["shift_code"],
                "operation_name": readiness.get("operation_name"),
                "risk_level": readiness["risk_level"],
                "score": readiness["readiness_score"]["score"],
            },
            "skill_signals": skill_signals,
            "recommended_actions": readiness.get("recommended_actions", []),
            "claims_boundary": readiness.get("claims_boundary"),
        }
        return {
            "target": normalized_target,
            "created_at": utc_now_iso(),
            "payload": payload,
        }

    def _map_skill_gaps(self, incident_id: str, issues: list[Any]) -> list[SkillGap]:
        gaps: dict[str, SkillGap] = {}
        for issue in issues:
            skill_id = _skill_for_issue(issue.code)
            skill = SKILL_CATALOG[skill_id]
            existing = gaps.get(skill_id)
            if existing and _severity_weight(existing.severity) >= _severity_weight(issue.severity):
                continue
            gaps[skill_id] = SkillGap(
                skill_id=skill.skill_id,
                title=skill.title,
                severity=issue.severity,
                source_issue_code=issue.code,
                incident_id=incident_id,
                detail=issue.detail,
                recommended_action=issue.suggested_action,
                confidence=0.95,
            )
        return list(gaps.values())

    def _learning_node_for(self, gap: SkillGap) -> LearningNode:
        skill = SKILL_CATALOG[gap.skill_id]
        return LearningNode(
            node_id=f"node_{gap.skill_id}",
            skill_id=gap.skill_id,
            title=skill.title,
            why_it_matters=skill.description,
            practice_prompt=f"Bu vakadaki '{gap.title}' acigini kanita dayali olarak kapat.",
            success_criteria=gap.recommended_action,
        )

    def _learning_task_for(
        self,
        *,
        incident_id: str,
        gap: SkillGap,
        employee_code: str | None,
        role_code: str | None,
        team_code: str | None,
        station_code: str | None,
        case_summary: str,
    ) -> LearningTask:
        skill = SKILL_CATALOG[gap.skill_id]
        scenario = (
            f"Gercek vaka ozeti: {case_summary[:360]} "
            f"Gorev: {gap.detail} Bu acigi musteriye gonderimden once nasil kanitlarsin?"
        )
        return LearningTask(
            task_id=f"task_{uuid4().hex[:12]}",
            incident_id=incident_id,
            employee_code=employee_code,
            role_code=role_code,
            team_code=team_code,
            station_code=station_code,
            skill_id=gap.skill_id,
            title=f"{skill.title} mikro-senaryosu",
            scenario=scenario,
            expected_evidence=[
                "Kisa teknik aciklama",
                "Tarih/sorumlu/termin bilgisi",
                "Fotograf, olcum veya kayit gibi izlenebilir kanit",
            ],
            rubric=[
                "Problem veya aksiyon varsayimla degil kanitla aciklandi.",
                "Cevap sayisal/tarihsel dogrulama iceriyor.",
                "Musteriye gondermeden once insan onayi gerektigi belirtiliyor.",
            ],
            status="pending_mentor_review",
            created_at=utc_now_iso(),
        )

    def _group_gaps(self, gaps: list[dict[str, Any]], approved_skill_ids: set[str]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for gap in gaps:
            entry = grouped.setdefault(
                gap["skill_id"],
                {
                    "skill_id": gap["skill_id"],
                    "title": gap["title"],
                    "incident_count": 0,
                    "severity_counts": Counter(),
                    "status": "open",
                },
            )
            entry["incident_count"] += 1
            entry["severity_counts"][gap["severity"]] += 1
        result = []
        for skill_id, entry in grouped.items():
            result.append(
                {
                    "skill_id": skill_id,
                    "title": entry["title"],
                    "incident_count": entry["incident_count"],
                    "severity_counts": dict(entry["severity_counts"]),
                    "status": "approved" if skill_id in approved_skill_ids else "open",
                }
            )
        result.sort(key=lambda item: (-item["incident_count"], item["skill_id"]))
        return result

    def _readiness_from_values(
        self,
        *,
        evidence_scores: list[int],
        skill_ids: list[str],
        approved_skill_ids: list[str],
    ) -> ReadinessScore:
        unique_skill_ids = set(skill_ids)
        approved = set(approved_skill_ids)
        open_gap_count = len(unique_skill_ids - approved)
        approved_count = len(unique_skill_ids & approved)
        evidence_score = int(mean(evidence_scores)) if evidence_scores else 0
        score = max(0, min(100, evidence_score - (open_gap_count * 6) + (approved_count * 10)))
        status = "ready" if score >= 82 and open_gap_count == 0 else "needs_practice" if open_gap_count else "watch"
        explanation = (
            f"KANIT skoru {evidence_score}; acik beceri {open_gap_count}; "
            f"mentor onayli beceri {approved_count}."
        )
        return ReadinessScore(
            score=score,
            status=status,
            open_gap_count=open_gap_count,
            approved_skill_count=approved_count,
            explanation=explanation,
        )

    def _dispatch_and_record(self, incident: IncidentAnalysis) -> None:
        events = [
            ("incident.analyzed", {"incident_id": incident.incident_id, "score": incident.case_report.checklist.score}),
            ("skill_gap.detected", {"incident_id": incident.incident_id, "count": len(incident.skill_gaps)}),
            ("learning_task.created", {"incident_id": incident.incident_id, "count": len(incident.learning_tasks)}),
        ]
        if incident.learning_tasks:
            events.append(("mentor_review.requested", {"incident_id": incident.incident_id}))
        for event_type, payload in events:
            result = self.webhooks.dispatch(event_type, payload)
            if result:
                incident.audit_events.append(result)

    def _filtered_incidents(
        self,
        *,
        team_code: str,
        station_code: str | None,
        employee_codes: list[str] | None,
        role_codes: list[str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        incidents = self.store.list_incidents_for_team(team_code)
        if station_code:
            incidents = [incident for incident in incidents if incident.get("station_code") == station_code]
        if employee_codes:
            wanted = set(employee_codes)
            incidents = [incident for incident in incidents if incident.get("employee_code") in wanted]
        if role_codes:
            roles = set(role_codes)
            incidents = [incident for incident in incidents if incident.get("role_code") in roles]
        return incidents[: max(1, limit)]

    def _approved_skill_ids(self, employee_codes: list[str]) -> set[str]:
        approved: set[str] = set()
        for employee_code in employee_codes:
            reviews = self.store.list_reviews_for_employee(employee_code)
            for review in reviews:
                if review.get("decision") == MentorDecision.APPROVED.value:
                    approved.add(review["skill_id"])
        return approved

    def _risk_drivers_from_gaps(
        self,
        gaps: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        incidents_by_id = {incident["incident_id"]: incident for incident in incidents}
        grouped: dict[str, dict[str, Any]] = {}
        for gap in gaps:
            skill_id = gap["skill_id"]
            entry = grouped.setdefault(
                skill_id,
                {
                    "skill_id": skill_id,
                    "title": gap["title"],
                    "incident_ids": set(),
                    "issue_counts": Counter(),
                    "severity_counts": Counter(),
                    "employee_codes": set(),
                    "scores": [],
                    "evidence_trace": [],
                },
            )
            incident = incidents_by_id.get(gap["incident_id"], {})
            entry["incident_ids"].add(gap["incident_id"])
            entry["issue_counts"][gap["source_issue_code"]] += 1
            entry["severity_counts"][gap["severity"]] += 1
            if gap.get("employee_code"):
                entry["employee_codes"].add(gap["employee_code"])
            score = _incident_score(incident)
            entry["scores"].append(score)
            entry["evidence_trace"].append(
                {
                    "incident_id": gap["incident_id"],
                    "source_issue_code": gap["source_issue_code"],
                    "severity": gap["severity"],
                    "checklist_score": score,
                    "employee_code": gap.get("employee_code"),
                    "station_code": incident.get("station_code"),
                    "case_id": incident.get("case_report", {}).get("case_id"),
                }
            )

        drivers = []
        for skill_id, entry in grouped.items():
            incident_count = len(entry["incident_ids"])
            average_score = int(mean(entry["scores"])) if entry["scores"] else 0
            issue_counts = dict(entry["issue_counts"])
            severity_counts = dict(entry["severity_counts"])
            why = self.skill_miner.why_builder.build(
                incident_count=incident_count,
                issue_counts=issue_counts,
                average_evidence_score=average_score,
                severity_counts=severity_counts,
            )
            confidence = self.skill_miner._confidence(incident_count, entry["severity_counts"], average_score)
            drivers.append(
                {
                    "skill_id": skill_id,
                    "title": entry["title"],
                    "incident_count": incident_count,
                    "employee_count": len(entry["employee_codes"]),
                    "issue_counts": issue_counts,
                    "severity_counts": severity_counts,
                    "average_evidence_score": average_score,
                    "confidence": confidence,
                    "why_this_gap": why,
                    "recommended_action": (
                        f"{entry['title']} icin vardiya oncesi 5 dakikalik kanitli mikro-pratik "
                        "ve mentor kontrolu ac."
                    ),
                    "evidence_trace": entry["evidence_trace"][:5],
                }
            )
        drivers.sort(key=lambda item: (-item["confidence"], -item["incident_count"], item["skill_id"]))
        return drivers

    def _recommended_actions_from_drivers(
        self,
        risk_drivers: list[dict[str, Any]],
        risk_level: str,
    ) -> list[dict[str, Any]]:
        actions = []
        for driver in risk_drivers[:5]:
            actions.append(
                {
                    "action_type": "pre_shift_micro_practice",
                    "priority": "high" if risk_level in {"high", "critical"} else "medium",
                    "skill_id": driver["skill_id"],
                    "title": driver["title"],
                    "owner": "mentor_or_team_leader",
                    "expected_evidence": [
                        "Kisa vardiya oncesi uygulama cevabi",
                        "Istasyon veya parca uzerinde kanitli kontrol",
                        "Mentor onayi",
                    ],
                    "reason": driver["why_this_gap"],
                }
            )
        if not actions:
            actions.append(
                {
                    "action_type": "standard_pre_shift_check",
                    "priority": "low",
                    "skill_id": None,
                    "title": "Standart vardiya oncesi kontrol",
                    "owner": "team_leader",
                    "expected_evidence": ["Vardiya baslangic kontrol kaydi"],
                    "reason": "Secilen kapsamda tekrar eden beceri riski bulunmadi.",
                }
            )
        return actions

    def _readiness_integration_events(
        self,
        *,
        risk_level: str,
        team_code: str,
        station_code: str | None,
        shift_code: str,
        risk_drivers: list[dict[str, Any]],
    ) -> list[AuditEvent]:
        events = [
            AuditEvent(
                "supplier_readiness.updated",
                "Readiness skoru entegrasyon sistemleri icin guncellendi.",
                utc_now_iso(),
                {
                    "team_code": team_code,
                    "station_code": station_code,
                    "shift_code": shift_code,
                    "risk_level": risk_level,
                },
            )
        ]
        if risk_level in {"medium", "high", "critical"}:
            events.append(
                AuditEvent(
                    "readiness.risk_detected",
                    "Vardiya baslamadan once kanita dayali beceri riski bulundu.",
                    utc_now_iso(),
                    {
                        "team_code": team_code,
                        "station_code": station_code,
                        "shift_code": shift_code,
                        "driver_count": len(risk_drivers),
                    },
                )
            )
        delivery_events = []
        for event in events:
            result = self.webhooks.dispatch(event.event_type, event.metadata)
            if result:
                delivery_events.append(result)
        return events + delivery_events


class WebhookDispatcher:
    def __init__(self, webhook_url: str | None, timeout_seconds: float = 0.7, retries: int = 1) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    @classmethod
    def from_env(cls) -> "WebhookDispatcher":
        return cls(os.getenv("KANIT_WEBHOOK_URL"))

    def dispatch(self, event_type: str, payload: dict[str, Any]) -> AuditEvent | None:
        if not self.webhook_url:
            return None
        body = json.dumps({"event_type": event_type, "payload": payload}).encode("utf-8")
        last_error = ""
        for _attempt in range(self.retries + 1):
            request = urllib.request.Request(
                self.webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return AuditEvent(
                        "webhook.delivered",
                        "Webhook olayi gonderildi.",
                        utc_now_iso(),
                        {"event_type": event_type, "status": response.status},
                    )
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)[:240]
        return AuditEvent(
            "webhook.delivery_failed",
            "Webhook gonderimi basarisiz oldu; ana analiz korunuyor.",
            utc_now_iso(),
            {"event_type": event_type, "error": last_error},
        )


def _skill_for_issue(issue_code: str) -> str:
    return canonical_skill_id_for_issue(issue_code) or ISSUE_TO_SKILL.get(issue_code, "problem_definition")


def _severity_weight(severity: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(severity, 0)


def _flatten_gaps(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for incident in incidents:
        for gap in incident.get("skill_gaps", []):
            copied = dict(gap)
            copied["employee_code"] = incident.get("employee_code")
            copied["station_code"] = incident.get("station_code")
            gaps.append(copied)
    return gaps


def _incident_score(incident: dict[str, Any]) -> int:
    checklist = incident.get("case_report", {}).get("checklist", {})
    return int(checklist.get("score", 0))


def _employee_codes_from_incidents(incidents: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            incident["employee_code"]
            for incident in incidents
            if incident.get("employee_code")
        }
    )


def _risk_level(score: int, risk_drivers: list[dict[str, Any]]) -> str:
    if not risk_drivers and score == 0:
        return "unknown"
    high_signal_count = sum(1 for driver in risk_drivers if driver["severity_counts"].get("high", 0))
    repeated_signal_count = sum(1 for driver in risk_drivers if driver["incident_count"] >= 3)
    if score < 45 or (high_signal_count >= 3 and repeated_signal_count >= 2):
        return "critical"
    if score < 65 or high_signal_count or repeated_signal_count:
        return "high"
    if score < 82 or risk_drivers:
        return "medium"
    return "low"


def _evidence_trace_for_drivers(risk_drivers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for driver in risk_drivers:
        for item in driver.get("evidence_trace", []):
            copied = dict(item)
            copied["skill_id"] = driver["skill_id"]
            copied["title"] = driver["title"]
            trace.append(copied)
    return trace[:20]


def _cost_profile_value(cost_profile: dict[str, float], key: str) -> float:
    value = float(cost_profile.get(key, 0))
    if value < 0:
        raise ValueError(f"{key} negatif olamaz.")
    return value


def _target_story(target: str) -> str:
    stories = {
        "generic": "Her web, mobil veya CLI istemcisi icin stabil readiness ve skill-gap JSON kontrati.",
        "poka": "Poka skills matrix ve is talimati akislarini gercek kalite olaylarindan gelen skill sinyalleriyle besler.",
        "augmentir": "Augmentir workforce intelligence katmanina sahadan gelen evidence-based skill-risk sinyali yollar.",
        "lms": "LMS icin genel kurs atamasi yerine olay kaynakli mikro-ogrenme gorevi ve mentor kaniti uretir.",
        "qms": "QMS/CAPA kaydina beceri acigi, kanit zayifligi ve insan onayi gerektiren aksiyon bilgisini geri yazar.",
        "powerbi": "Power BI veya BI panolarina vardiya, istasyon ve beceri bazli operasyonel risk feed'i saglar.",
        "n8n": "n8n workflow'larinda mentor onayi, Teams bildirimi veya LMS gorevi acmak icin webhook payload'i saglar.",
    }
    return stories[target]


def _readiness_dict(score: ReadinessScore) -> dict[str, Any]:
    return {
        "score": score.score,
        "status": score.status,
        "open_gap_count": score.open_gap_count,
        "approved_skill_count": score.approved_skill_count,
        "explanation": score.explanation,
    }
