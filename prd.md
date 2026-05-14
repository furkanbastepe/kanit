# PRD: KANIT

## Ürün Tanımı

KANIT, 8D/CAPA kalite dosyalarındaki tekrar eden kanıt eksiklerini operasyonel hazır oluş sinyaline çeviren web uygulaması ve API katmanıdır.

İlk sürüm `quality_8d_capa` vakalarıyla çalışır. Vaka metnini analiz eder, kanıt boşluklarını bulur, bunları sabit bir beceri/süreç sözlüğüne bağlar, readiness skorunu hesaplar ve mentor onaylı aksiyon açar.

## Temel Cümle

KANIT, tekrarlanan 8D/CAPA kanıt hatalarını mentor onaylı istasyon hazır oluş aksiyonlarına çevirir.

## Hedef Kullanıcılar

- Kalite mühendisi: kanıt zayıflıklarını hızlı ve tutarlı görmek ister.
- Supplier quality ekibi: tedarikçi dosyalarında tekrar eden eksikleri erken yakalamak ister.
- Mentor veya ekip lideri: sahada kısa, gerçek vakaya bağlı aksiyonla kapanış vermek ister.
- L&D/eğitim ekibi: eğitim ihtiyacını gerçek kalite vakalarından beslemek ister.
- Fabrika yönetimi: hangi takım veya istasyonda hangi kanıt boşluğu tekrar ediyor görmek ister.

## Çözülen Problem

Kalite sistemi dosyayı kapatır. Eğitim sistemi kurs atar. Saha sistemi işi yürütür.

Ama kapatılan 8D/CAPA dosyalarındaki tekrar eden kanıt zayıflığı çoğu zaman doğrudan readiness aksiyonuna dönüşmez.

KANIT bu boşluğu kapatır.

## İlk Sürüm Kapsamı

- 8D/CAPA metin analizi.
- Eksik kök neden, zayıf etkinlik doğrulama, eksik owner, eksik termin ve zayıf görsel kanıt tespiti.
- Kaynak metin izi.
- Sabit skill/process ontology.
- Türkçe ve İngilizce benzer ifadeleri canonical riske normalleştirme.
- Repeated gap tespiti.
- Rule-based readiness skoru.
- `score_breakdown`, `formula` ve `rule_version`.
- Mentor task üretimi.
- Mentor/reviewer onayı olmadan `CLEARED` durumuna geçmeme.
- Demo seed endpointi.
- QMS, LMS, connected worker, BI ve n8n için export payload.
- Audit trail.
- React tabanlı demo arayüzü.

## Kapsam Dışı

- Tam QMS ürünü.
- Tam LMS ürünü.
- Resmi Ford portal entegrasyonu.
- Gerçek çalışan adı zorunluluğu.
- Çalışan performans puanı.
- AI’ın tek başına yeterlilik kararı vermesi.
- Kalite sertifikasyonu veya IATF uygunluk garantisi.
- Kesin tasarruf garantisi.

## Güven Kuralları

- Sistem kişi suçlamaz.
- Varsayılan analiz istasyon, takım veya rol seviyesindedir.
- Bilinmeyen etiketler otomatik uydurulmaz.
- Readiness skoru AI yorumu değil, görünür kural motoru sonucudur.
- Mentor onayı olmadan kapanış verilmez.
- Demo gerçek Ford veya müşteri verisi kullanmaz.

## Kabul Kriterleri

- Eksik 8D/CAPA vakası en az bir evidence gap üretir.
- `Etkinlik kontrolü eksik`, `effectiveness check missing` ve `corrective action follow-up missing` aynı `effectiveness_verification` riskine düşer.
- Readiness response içinde skor, formül, breakdown ve rule version görünür.
- Tekrarlayan gap aynı istasyon/takım için risk artırır.
- Mentor görevi açılır.
- Mentor onayı olmadan status `CLEARED` olmaz.
- Unknown skill label insan incelemesine yönlenir.
- Export endpointleri dış sistemlere okunabilir payload verir.
- ROI çıktısı garanti değil, pilot hipotezi olarak sunulur.

## Pilot Kapsamı

İlk pilot küçük olmalıdır:

- Bir supplier quality veya 8D/CAPA review akışı.
- Tek defect family.
- 30-50 yetkili ve redakte edilmiş vaka.
- Tek kanıt ailesi: effectiveness verification, root cause quality veya corrective action follow-up.
- 90 gün ölçüm.

En önemli metrik:

> Quality/mentor reviewer sonrası false-positive rate.
