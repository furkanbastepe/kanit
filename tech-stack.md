# Teknoloji Seçimi

## Yaklaşım

KANIT backend-first kuruldu.

Çünkü ürünün asıl değeri güzel bir ekran değil. Asıl değer, kalite dosyasındaki kanıt boşluğunu güvenilir bir readiness sinyaline çevirmek.

Mimari basit tutuldu:

```text
FastAPI backend + SQLite demo verisi + React frontend + kural tabanlı readiness motoru
```

## Kullanılan Teknolojiler

- Python
- FastAPI
- SQLite
- React
- Vite
- REST API
- unittest
- FastAPI TestClient
- NVIDIA API canlı mod hazırlığı
- Ollama/local model hazırlığı
- Webhook/export payload yapısı

## Neden FastAPI?

KANIT birden fazla yere veri verebilmeli:

- Web arayüzü.
- QMS entegrasyonu.
- LMS entegrasyonu.
- Connected worker entegrasyonu.
- n8n otomasyonu.
- BI dashboardları.

FastAPI bu yüzden uygun. Hızlı, sade ve API-first çalışıyor.

## Neden SQLite?

Buildathon için hızlı ve yeterli.

Pilot büyürse storage katmanı Postgres’e taşınabilir. Bugünkü amaç büyük kurumsal dönüşüm değil; 30-50 vaka ile hipotezi ölçmek.

## Neden Kural Motoru?

Readiness skoru serbest AI yorumu olamaz.

KANIT’ta AI kanıt sinyalini çıkarır. Skor görünür kuralla hesaplanır.

Örnek:

```text
100 - evidence_quality_gap - open_skill_gap - repeated_gap - mentor_pending
```

Response içinde `score_breakdown`, `formula` ve `rule_version` döner. Bu fabrika güveni için kritiktir.

## AI Modları

Canlı mod:

```bash
export KANIT_AI_MODE=nvidia
export KANIT_ALLOW_MOCK=false
export KANIT_API_KEY="demo-local-key"
export NVIDIA_API_KEY="..."
```

Bu modda model yanıt vermezse sistem sessizce sahte sonuç üretmez. Hata döner.

Local model yolu da açık bırakıldı:

```text
Ollama/local model
```

Bu, hassas kalite verisiyle çalışılacak pilotlarda önemlidir.

## Entegrasyon Noktaları

- `GET /skills/ontology`: canonical risk sözlüğünü döndürür.
- `POST /skills/normalize`: farklı ifadeyi canonical riske bağlar.
- `POST /incidents/analyze`: 8D/CAPA vakasını analiz eder.
- `POST /shifts/readiness`: station/team readiness skoru üretir.
- `POST /mentor-reviews`: insan onayını kaydeder.
- `POST /pilot/roi-hypothesis`: pilot tasarruf varsayımını hesaplar.
- `GET /exports/readiness/{readiness_id}`: QMS, LMS, connected worker, BI veya n8n için payload verir.

## Güvenlik ve Veri

- Gerçek Ford veya müşteri verisi demo içinde kullanılmaz.
- Çalışan adı zorunlu değildir.
- `employee_code`, `role_code`, `team_code` ve `station_code` gibi yönlendirme kodları kullanılır.
- API anahtarı ortam değişkeniyle verilir.
- Mentor onayı olmadan readiness kapanmaz.
