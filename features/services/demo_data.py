from __future__ import annotations

from features.services.types import EvidenceFile


def demo_evidence_for_sample(sample: str) -> list[EvidenceFile]:
    if sample == "01_missing_evidence":
        return [
            EvidenceFile(
                filename="defect_capak_photo.jpg",
                content_type="image/jpeg",
                data=b"mock image bytes - defect burr",
                evidence_role="defect_photo",
            )
        ]
    if sample == "02_conflicting_evidence":
        return [
            EvidenceFile(
                filename="defect_scratch_photo.jpg",
                content_type="image/jpeg",
                data=b"mock image bytes - defect scratch",
                evidence_role="defect_photo",
            ),
            EvidenceFile(
                filename="unrelated_after_photo.jpg",
                content_type="image/jpeg",
                data=b"mock image bytes - unclear",
                evidence_role="corrective_photo",
            ),
        ]
    return [
        EvidenceFile(
            filename="defect_label_measure_photo.jpg",
            content_type="image/jpeg",
            data=b"mock image bytes - defect label measurement",
            evidence_role="defect_photo",
        ),
        EvidenceFile(
            filename="after_corrective_measure_label_photo.jpg",
            content_type="image/jpeg",
            data=b"mock image bytes - after corrective measurement label",
            evidence_role="corrective_photo",
        ),
        EvidenceFile(
            filename="measurement_gauge_screen_label_photo.jpg",
            content_type="image/jpeg",
            data=b"mock image bytes - gauge screen label",
            evidence_role="measurement_photo",
        ),
    ]


def demo_readiness_cases() -> list[dict[str, object]]:
    return [
        {
            "employee_code": "demo-operator-01",
            "alias_label": "etkinlik kontrolu eksik",
            "case_text": """
Problem: Final inspection istasyonunda sol braket capakli cikti.
Containment: Supheli lot ayrildi ve 40 parca tekrar kontrol edildi.
Kok neden: Aparat sikma yuzeyinde temizlik standardi uygulanmamis.
Duzeltici aksiyon: Aparat temizleme frekansi vardiya basina alindi.
Sorumlu: Kalite Muhendisi
Termin: 2026-05-20
Not: Kapanis kaniti henuz dosyada yok.
""".strip(),
        },
        {
            "employee_code": "demo-operator-02",
            "alias_label": "effectiveness check missing",
            "case_text": """
Problem: Customer complaint for paint scratch on trim part.
Containment: Warehouse stock blocked and suspect serial range tagged.
Root cause: Handling tray separator was worn and allowed part-to-part contact.
Corrective action: Separator material changed and tray inspection added.
Owner: Supplier Quality
Due date: 2026-05-21
Note: Closure evidence is not in the pack yet.
""".strip(),
        },
        {
            "employee_code": "demo-operator-03",
            "alias_label": "corrective action follow-up",
            "case_text": """
Uygunsuzluk: Montaj sonrasi etiket okunabilirligi dusuk.
Gecici onlem: Etkilenen parti ayrildi, sevk oncesi %100 kontrol acildi.
Kok neden: Yazici sicaklik ayari vardiya degisiminde standardize edilmemis.
Kalici aksiyon: Yazici ayar kontrolu baslatma listesine eklendi.
Sorumlu: Hat Lideri
Termin: 2026-05-22
Not: Kapanis kaydi ve saha kaniti bekleniyor.
""".strip(),
        },
    ]


def demo_readiness_evidence() -> list[EvidenceFile]:
    return [
        EvidenceFile(
            filename="demo_defect_photo.jpg",
            content_type="image/jpeg",
            data=b"demo image bytes - defect label",
            evidence_role="defect_photo",
        )
    ]
