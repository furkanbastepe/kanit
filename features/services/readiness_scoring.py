from __future__ import annotations

from statistics import mean
from typing import Any


RULE_VERSION = "readiness_v1"
TARGET_EVIDENCE_SCORE = 82


class ReadinessScorer:
    def score(
        self,
        *,
        evidence_scores: list[int],
        skill_ids: list[str],
        approved_skill_ids: list[str],
        risk_drivers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        unique_skill_ids = set(skill_ids)
        approved = set(approved_skill_ids)
        open_skill_ids = sorted(unique_skill_ids - approved)
        approved_count = len(unique_skill_ids & approved)
        evidence_score = int(mean(evidence_scores)) if evidence_scores else 0

        penalties = []
        if not evidence_scores:
            penalties.append(
                {
                    "code": "no_recent_incident_evidence",
                    "label": "Secilen kapsamda readiness hesaplayacak olay verisi yok",
                    "points": 100,
                    "evidence": {"incident_count": 0},
                }
            )
        elif evidence_score < TARGET_EVIDENCE_SCORE:
            penalties.append(
                {
                    "code": "evidence_quality_gap",
                    "label": "KANIT skoru hedefin altinda",
                    "points": min(40, TARGET_EVIDENCE_SCORE - evidence_score),
                    "evidence": {
                        "average_evidence_score": evidence_score,
                        "target": TARGET_EVIDENCE_SCORE,
                    },
                }
            )
        if open_skill_ids:
            penalties.append(
                {
                    "code": "open_canonical_skill_gap",
                    "label": "Mentor onayi olmayan canonical beceri acigi",
                    "points": min(30, len(open_skill_ids) * 6),
                    "evidence": {"skill_ids": open_skill_ids},
                }
            )
        repeated_drivers = [
            driver for driver in risk_drivers
            if driver.get("incident_count", 0) >= 2
        ]
        if repeated_drivers:
            total_repeated_penalty = min(
                30,
                sum((driver["incident_count"] - 1) * 10 for driver in repeated_drivers),
            )
            penalties.append(
                {
                    "code": "repeated_canonical_gap",
                    "label": "Ayni canonical beceri acigi birden fazla olayda tekrar etti",
                    "points": total_repeated_penalty,
                    "evidence": [
                        {
                            "skill_id": driver["skill_id"],
                            "incident_count": driver["incident_count"],
                            "why_this_gap": driver["why_this_gap"],
                        }
                        for driver in repeated_drivers[:5]
                    ],
                }
            )
        if open_skill_ids:
            penalties.append(
                {
                    "code": "mentor_approval_pending",
                    "label": "Mentor onayi bekleyen beceri",
                    "points": min(10, len(open_skill_ids) * 2),
                    "evidence": {"open_skill_count": len(open_skill_ids)},
                }
            )

        bonuses = []
        if approved_count:
            bonuses.append(
                {
                    "code": "mentor_approved_skill",
                    "label": "Mentor onayli beceri",
                    "points": min(20, approved_count * 10),
                    "evidence": {"approved_skill_count": approved_count},
                }
            )

        total_penalty = sum(item["points"] for item in penalties)
        total_bonus = sum(item["points"] for item in bonuses)
        final_score = max(0, min(100, 100 - total_penalty + total_bonus))
        formula = self._formula(total_penalty=total_penalty, total_bonus=total_bonus, final_score=final_score)
        return {
            "rule_version": RULE_VERSION,
            "base_score": 100,
            "final_score": final_score,
            "formula": formula,
            "penalties": penalties,
            "bonuses": bonuses,
            "inputs": {
                "evidence_scores": evidence_scores,
                "average_evidence_score": evidence_score,
                "unique_skill_ids": sorted(unique_skill_ids),
                "approved_skill_ids": sorted(approved),
                "open_skill_ids": open_skill_ids,
            },
        }

    def _formula(self, *, total_penalty: int, total_bonus: int, final_score: int) -> str:
        if total_bonus:
            return f"100 - {total_penalty} + {total_bonus} = {final_score}"
        return f"100 - {total_penalty} = {final_score}"
