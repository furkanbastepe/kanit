from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


ONTOLOGY_VERSION = "skills_v1"


@dataclass(frozen=True, slots=True)
class SkillOntologyEntry:
    skill_id: str
    title_tr: str
    title_en: str
    category: str
    definition: str
    synonyms: tuple[str, ...]
    allowed_issue_codes: tuple[str, ...]
    severity_weight: int
    required_evidence: tuple[str, ...]
    mentor_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["synonyms"] = list(self.synonyms)
        payload["allowed_issue_codes"] = list(self.allowed_issue_codes)
        payload["required_evidence"] = list(self.required_evidence)
        payload["mentor_criteria"] = list(self.mentor_criteria)
        return payload


SKILL_ONTOLOGY: dict[str, SkillOntologyEntry] = {
    "problem_definition": SkillOntologyEntry(
        skill_id="problem_definition",
        title_tr="Problem tanimini kanita dayali yazma",
        title_en="Evidence-based problem definition",
        category="quality",
        definition="Clarify the customer concern with part, defect, scope, and impact.",
        synonyms=(
            "problem tanimi",
            "problem definition",
            "complaint definition",
            "uygunsuzluk tanimi",
            "d2 problem",
        ),
        allowed_issue_codes=("missing_problem_statement",),
        severity_weight=2,
        required_evidence=("part_or_process_context", "defect_description", "scope"),
        mentor_criteria=("Problem scope is concrete.", "Customer impact is not guessed."),
    ),
    "containment_planning": SkillOntologyEntry(
        skill_id="containment_planning",
        title_tr="Containment ve stok ayirma planlama",
        title_en="Containment and stock segregation planning",
        category="quality",
        definition="Define immediate containment, stock control, and traceability.",
        synonyms=(
            "containment",
            "gecici onlem",
            "stok ayirma",
            "interim containment",
            "d3 containment",
        ),
        allowed_issue_codes=("missing_containment_action",),
        severity_weight=2,
        required_evidence=("containment_action", "affected_stock", "date_or_owner"),
        mentor_criteria=("Containment can be audited.", "Risky stock is traceable."),
    ),
    "root_cause_analysis": SkillOntologyEntry(
        skill_id="root_cause_analysis",
        title_tr="Kok neden analizi",
        title_en="Root cause analysis",
        category="quality",
        definition="Find a systemic root cause without blaming the operator.",
        synonyms=(
            "kok neden",
            "root cause",
            "5 why",
            "5 neden",
            "fishbone",
            "root cause depth",
        ),
        allowed_issue_codes=("missing_root_cause",),
        severity_weight=3,
        required_evidence=("5_why_or_fishbone", "technical_cause", "system_cause"),
        mentor_criteria=("Root cause reaches process/system level.", "Evidence supports the cause."),
    ),
    "corrective_action_design": SkillOntologyEntry(
        skill_id="corrective_action_design",
        title_tr="Kalici duzeltici aksiyon tasarimi",
        title_en="Permanent corrective action design",
        category="quality",
        definition="Define measurable permanent action that reduces recurrence risk.",
        synonyms=(
            "corrective action",
            "duzeltici aksiyon",
            "kalici aksiyon",
            "permanent corrective action",
            "d5 action",
            "d6 action",
        ),
        allowed_issue_codes=("missing_corrective_action", "missing_preventive_action"),
        severity_weight=3,
        required_evidence=("action_description", "owner", "due_date"),
        mentor_criteria=("Action is measurable.", "Action addresses the root cause."),
    ),
    "effectiveness_verification": SkillOntologyEntry(
        skill_id="effectiveness_verification",
        title_tr="Etkinlik dogrulama",
        title_en="Effectiveness verification",
        category="quality",
        definition="Verify that the corrective action worked with dated and measurable evidence.",
        synonyms=(
            "etkinlik kontrolu",
            "etkinlik dogrulama",
            "aksiyonun calistigi kanitlanmamis",
            "dogrulama eksik",
            "effectiveness",
            "effectiveness check",
            "effectiveness check missing",
            "verification missing",
            "corrective action follow-up",
            "action follow up",
            "follow-up evidence missing",
        ),
        allowed_issue_codes=("missing_effectiveness_check",),
        severity_weight=3,
        required_evidence=("dated_verification", "measured_result", "before_after_or_record"),
        mentor_criteria=("Verification uses data.", "Result proves the action worked."),
    ),
    "visual_evidence_capture": SkillOntologyEntry(
        skill_id="visual_evidence_capture",
        title_tr="Gorsel kanit yakalama",
        title_en="Visual evidence capture",
        category="quality",
        definition="Collect readable defect, label, measurement, and before/after evidence.",
        synonyms=(
            "gorsel kanit",
            "fotograf eksik",
            "before after evidence",
            "corrective evidence documentation",
            "measurement photo",
            "defect photo",
        ),
        allowed_issue_codes=(
            "missing_defect_photo",
            "missing_corrective_photo",
            "weak_visual_evidence_defect_photo",
            "weak_visual_evidence_corrective_photo",
            "weak_visual_evidence_measurement_photo",
        ),
        severity_weight=3,
        required_evidence=("defect_photo", "corrective_photo", "label_or_measurement"),
        mentor_criteria=("Evidence is readable.", "Evidence links to the same part/process."),
    ),
    "action_ownership": SkillOntologyEntry(
        skill_id="action_ownership",
        title_tr="Aksiyon sahipligi ve termin takibi",
        title_en="Action ownership and due-date tracking",
        category="quality",
        definition="Keep owner, due date, and closure status traceable.",
        synonyms=(
            "aksiyon sahibi",
            "termin takibi",
            "owner missing",
            "due date missing",
            "action owner",
            "deadline",
        ),
        allowed_issue_codes=("missing_owner", "missing_due_date"),
        severity_weight=2,
        required_evidence=("owner", "due_date", "closure_status"),
        mentor_criteria=("Owner is named.", "Due date is traceable."),
    ),
}


def ontology_payload() -> dict[str, Any]:
    return {
        "ontology_version": ONTOLOGY_VERSION,
        "skills": [entry.to_dict() for entry in SKILL_ONTOLOGY.values()],
    }


def normalize_skill_label(label: str) -> dict[str, Any]:
    normalized = _normalize_text(label)
    if not normalized:
        return _human_review(label, "empty_label")

    alias_index = _alias_index()
    if normalized in alias_index:
        skill_id = alias_index[normalized]
        return _matched(label, skill_id, 1.0, "exact_alias")

    for alias, skill_id in alias_index.items():
        if alias in normalized or normalized in alias:
            return _matched(label, skill_id, 0.86, "partial_alias")

    return _human_review(label, "no_canonical_alias")


def canonical_skill_id_for_issue(issue_code: str) -> str | None:
    if issue_code.startswith("weak_visual_evidence_"):
        return "visual_evidence_capture"
    for entry in SKILL_ONTOLOGY.values():
        if issue_code in entry.allowed_issue_codes:
            return entry.skill_id
    return None


def _matched(label: str, skill_id: str, confidence: float, match_type: str) -> dict[str, Any]:
    entry = SKILL_ONTOLOGY[skill_id]
    return {
        "status": "matched",
        "input": label,
        "skill_id": skill_id,
        "title_tr": entry.title_tr,
        "title_en": entry.title_en,
        "confidence": confidence,
        "match_type": match_type,
        "ontology_version": ONTOLOGY_VERSION,
    }


def _human_review(label: str, reason: str) -> dict[str, Any]:
    return {
        "status": "needs_human_review",
        "input": label,
        "skill_id": None,
        "title_tr": None,
        "title_en": None,
        "confidence": 0.0,
        "match_type": reason,
        "ontology_version": ONTOLOGY_VERSION,
    }


def _alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for entry in SKILL_ONTOLOGY.values():
        values = (
            entry.skill_id,
            entry.title_tr,
            entry.title_en,
            entry.definition,
            *entry.synonyms,
            *entry.allowed_issue_codes,
        )
        for value in values:
            index[_normalize_text(value)] = entry.skill_id
    return index


def _normalize_text(value: str) -> str:
    translated = value.translate(str.maketrans("çğıöşüÇĞİÖŞÜıİ", "cgiosuCGIOSUiI"))
    lowered = translated.lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()
