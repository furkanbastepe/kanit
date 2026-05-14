# Kullanıcı Akışı

## Ana Akış

1. Kalite mühendisi 8D/CAPA vaka metnini yükler.
2. KANIT dosyadaki kanıt boşluklarını çıkarır.
3. Eksikler görünür olur: kök neden, etkinlik doğrulama, aksiyon sahibi, termin veya görsel kanıt.
4. Her eksik sabit bir beceri/süreç riskine bağlanır.
5. Aynı risk aynı istasyon, takım veya rol çevresinde daha önce görülmüşse tekrar sinyali yükselir.
6. Readiness skoru açık formülle hesaplanır.
7. KANIT mentor için kısa bir mikro-pratik üretir.
8. Mentor veya kalite reviewer görevi inceler.
9. Onay gelmeden risk kapanmaz.
10. Yönetim ve L&D ekipleri çıktıyı eğitim/readiness sinyali olarak görür.

## Demo Akışı

Demo üç sentetik vaka üzerinden çalışır.

İlk vaka:

> Etkinlik kontrolü eksik.

İkinci vaka:

> Effectiveness check missing.

Üçüncü vaka:

> Corrective action follow-up gösterilmemiş.

KANIT bu üç ifadeyi aynı riske bağlar:

```text
effectiveness_verification
```

Sonra skor hesaplanır:

```text
100 - evidence_quality_gap - open_skill_gap - repeated_gap - mentor_pending = 32
```

Doğru çıktı:

> Final inspection istasyonunda tekrar eden etkinlik doğrulama kanıt riski var. Mentor onaylı mikro-pratik gerekiyor.

Yanlış çıktı:

> Bu operatör yetersiz.

KANIT ikinci cümleyi kurmaz.

## Mentor Mikro-Pratiği

Mentor görevi kısa ve gerçek vakaya bağlıdır:

> Düzeltici aksiyonun işe yaradığını gösteren tarihli, ölçülebilir sonuç kanıtını göster.

Bu görev genel eğitim değildir. Doğrudan dosyadaki kanıt boşluğundan doğar.

## Backend Akışı

```text
POST /incidents/analyze
-> evidence gap
-> canonical risk
-> learning task
-> readiness score
-> mentor review
```

Önemli endpointler:

- `POST /incidents/analyze`: 8D/CAPA vakasını analiz eder.
- `POST /demo/seed-readiness`: deterministik demo verisini üretir.
- `POST /shifts/readiness`: istasyon/takım readiness skorunu hesaplar.
- `POST /mentor-reviews`: mentor kararını kaydeder.
- `POST /gate/check`: mentor kapısı açık mı kapalı mı gösterir.
- `GET /exports/readiness/{readiness_id}`: dış sistemler için sinyal üretir.
