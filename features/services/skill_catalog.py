from __future__ import annotations

from features.services.types import Skill


SKILL_CATALOG: dict[str, Skill] = {
    "problem_definition": Skill(
        skill_id="problem_definition",
        title="Problem tanimini kanita dayali yazma",
        category="quality",
        description="Musteri sikayetini parca, hata tipi, kapsam ve etkiyle netlestirme.",
    ),
    "containment_planning": Skill(
        skill_id="containment_planning",
        title="Containment ve stok ayirma planlama",
        category="quality",
        description="Acil onlem, stok kontrolu ve riskli parti izlenebilirligini kurma.",
    ),
    "root_cause_analysis": Skill(
        skill_id="root_cause_analysis",
        title="Kok neden analizi",
        category="quality",
        description="5 Why/Fishbone ile operator suclamadan sistemik kok neden bulma.",
    ),
    "corrective_action_design": Skill(
        skill_id="corrective_action_design",
        title="Kalici duzeltici aksiyon tasarimi",
        category="quality",
        description="Aksiyonu olculebilir, sorumlusu belli ve tekrar riskini azaltan sekilde tanimlama.",
    ),
    "effectiveness_verification": Skill(
        skill_id="effectiveness_verification",
        title="Etkinlik dogrulama",
        category="quality",
        description="Duzeltici aksiyonun ise yaradigini tarihli ve sayisal kanitla dogrulama.",
    ),
    "visual_evidence_capture": Skill(
        skill_id="visual_evidence_capture",
        title="Gorsel kanit yakalama",
        category="quality",
        description="Hata, etiket, olcum ve before/after kanitlarini okunabilir toplama.",
    ),
    "action_ownership": Skill(
        skill_id="action_ownership",
        title="Aksiyon sahipligi ve termin takibi",
        category="quality",
        description="Aksiyon sahibi, termin ve kapanis takibini izlenebilir tutma.",
    ),
}
