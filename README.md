# KANIT

KANIT, 8D/CAPA kalite dosyalarındaki tekrar eden kanıt eksiklerini istasyon ve takım seviyesinde hazır oluş aksiyonuna çeviren bir AI uygulamasıdır.

Kısa anlatım:

> KANIT, kapanan kalite dosyalarındaki kanıt zayıflığını yakalar, aynı problemi tek bir beceri/süreç riskine bağlar ve mentor onayı olmadan kapatmaz.

## Problem

Kalite dosyaları kapanıyor. Ama dosyanın içindeki öğrenme sinyali çoğu zaman sistemde kalmıyor.

Bir raporda “etkinlik kontrolü eksik” yazıyor. Başka raporda “effectiveness check missing” yazıyor. Bir diğerinde “corrective action follow-up yok” deniyor.

Kelimeler değişiyor. Problem aynı kalıyor:

> Düzeltici aksiyonun gerçekten işe yaradığını gösteren kanıt zayıf.

Bu tekrar çoğu zaman Excel’de, e-postada, toplantıda veya kalite mühendisinin hafızasında kalıyor. KANIT bu tekrarı görünür hale getirir.

## Problem Gerçek Mi?

Evet. Ana problem gerçek ve verilerle destekleniyor.

- ASQ, 8D metodunun amacını problemi tanımlamak, kök nedeni bulmak, düzeltici aksiyon almak ve tekrarını önlemek olarak açıklar.
- WEF Future of Jobs 2025 raporunda işverenlerin %63’ü beceri açığını dönüşümün en büyük bariyeri olarak görür.
- Ford Otosan 2025 rapor verilerinde 25.002 çalışan, 2.615.735 çalışan-saat eğitim ve 132,69 milyon TL eğitim harcaması yer alır. Bu, yetkinlik ve hazır oluş yönetiminin büyük bir yatırım alanı olduğunu gösterir.
- Ford Otosan 2025 finansal notlarında toplam garanti gider karşılığı 4.775.854 bin TL seviyesindedir. Bu tutar KANIT’ın tasarrufu değildir; kalite ve satış sonrası risklerin finansal önemini gösterir.
- IATF/OEM kalite beklentileri, problem çözmede kök neden, aksiyon kanıtı ve etkinlik doğrulamasını kritik görür.

KANIT’ın dar hipotezi şudur:

> Kapatılan 8D/CAPA kayıtlarında tekrar eden kanıt zayıflıkları, istasyon/takım readiness aksiyonlarına dönüştürülebilir.

Bu hipotez 30-50 yetkili ve redakte edilmiş vaka ile 90 günde test edilmelidir.

## Çözüm

KANIT vaka metnini okur. Eksik kök neden, zayıf etkinlik doğrulama, belirsiz aksiyon sahibi, takip kanıtı eksikliği ve zayıf görsel kanıt gibi boşlukları çıkarır.

Sonra aynı anlama gelen ifadeleri tek riske bağlar:

```text
Etkinlik kontrolü eksik
effectiveness check missing
corrective action follow-up missing
Yapılan aksiyonun çalıştığı gösterilmemiş
```

Hepsi şu kanonik riske düşer:

```text
effectiveness_verification
```

Ürün akışı:

```text
8D/CAPA kanıt boşluğu
-> canonical skill/process risk
-> station/team readiness skoru
-> mentor onaylı mikro aksiyon
```

## Değer Önerisi

Kalite mühendisi için: tekrar eden kanıt eksiklerini daha hızlı ve tutarlı görür.

Supplier quality için: tedarikçi 8D/CAPA paketlerinde aynı eksik tekrar ediyor mu, daha erken yakalar.

Mentor için: genel eğitim yerine gerçek vakadan doğan kısa saha pratiği alır.

Yönetim için: kaç eğitim tamamlandı değil, hangi kanıt boşluğu tekrar ediyor görür.

L&D için: eğitim ihtiyacını anketten değil, gerçek kalite vakasından besler.

## Hedef Kitle

İlk hedef büyük kurumun tamamı değildir.

İlk hedef:

- Supplier Quality ekipleri.
- 8D/CAPA review ekipleri.
- Tek defect family.
- 30-50 redakte edilmiş vaka.

İkincil kullanıcılar:

- Üretim mentorları.
- Ekip liderleri.
- L&D ekipleri.
- Fabrika yönetimi.
- Tedarikçiler.

## Mevcut Çözüm Nasıl?

Bugünkü çözüm genelde parçalıdır:

- QMS, CAPA dosyasını yönetir.
- Excel veya Power BI geçmişi gösterir.
- LMS eğitim atar.
- Connected worker araçları işi sahaya taşır.
- Kalite mühendisi tekrar eden eksikleri manuel yorumlar.
- Mentor kapanışı sahada takip eder.

Bu sistemler değerlidir. KANIT onların yerine geçmez.

KANIT’ın işi daha dardır:

> Kapanan kalite dosyasındaki tekrar eden kanıt zayıflığını readiness sinyaline çevirmek.

## Rakipler ve Fark

| Alternatif | Ne yapar? | KANIT’ın farkı |
| --- | --- | --- |
| QMS/eQMS | CAPA, audit, doküman ve kalite süreçlerini yönetir | KANIT QMS değildir; QMS kayıtlarından kanıt/readiness sinyali çıkarır |
| LMS | Eğitim içerikleri ve tamamlama takibi yapar | KANIT eğitim vermez; hangi mikro-pratiğin gerektiğini kalite vakasından çıkarır |
| Connected worker | Saha işi, talimat ve beceri yönetimi sağlar | KANIT sahaya hangi kanıt kaynaklı aksiyonun gitmesi gerektiğini söyler |
| Excel/Power BI | Geçmiş veriyi raporlar | KANIT farklı ifadeleri aynı riske normalize eder ve mentor gate açar |
| ChatGPT/genel LLM | Tek dosyayı özetler | KANIT source span, ontology, rule_version, skor formülü ve insan onayıyla çalışır |

En net konum:

> KANIT bir QMS, LMS veya saha eğitim platformu değildir. KANIT, kalite hafızası ile operasyonel koçluk arasında kanıta dayalı hazır oluş katmanıdır.

## Maliyet Neden Azalabilir?

KANIT tasarruf garantisi vermez. Doğru iddia pilot hipotezidir.

Azalma beklenen alanlar:

- Tekrarlayan manuel 8D/CAPA incelemesi.
- Yanlış hedeflenmiş eğitim.
- Geç fark edilen etkinlik doğrulama eksikleri.
- Kapanış sonrası aynı kanıt hatasının tekrar aranması.
- QMS değiştirmeden pilot yapılabildiği için entegrasyon yükü.

Pilot hedefi:

> Kalite mühendisi başına haftada 2 saat inceleme zamanı tasarrufu ölçülmelidir. Kanıtlanmadan garanti gibi sunulmamalıdır.

## Bu Proje Olmazsa Ne Olur?

Dünya durmaz. Ama fırsat kaçar.

8D/CAPA dosyaları kapanır ve arşivlenir. Aynı kanıt eksikleri farklı kelimelerle tekrar eder. Eğitim ihtiyacı daha genel kalır. Mentor aksiyonları kalite verisine zayıf bağlanır. Yönetim, tekrar eden kanıt boşluğunu geç görür.

KANIT’ın önlediği kayıp budur:

> Kapanmış her kalite dosyasındaki öğrenme sinyalinin sessizce kaybolması.

## Demo Akışı

1. Kullanıcı sentetik 8D/CAPA vakasını yükler.
2. KANIT kanıt boşluğunu çıkarır.
3. Farklı ifadeleri aynı canonical riske bağlar.
4. Readiness skorunu açık formülle hesaplar.
5. Mentor için mikro-pratik üretir.
6. Mentor onayı gelmeden durum `CLEARED` olmaz.

Örnek skor:

```text
100 - evidence_quality_gap - open_skill_gap - repeated_gap - mentor_pending = 32
```

## Canlı Demo

Yayın Linki: **Teslimden önce gerçek Lovable/Netlify linki eklenecek.**  
Demo Video: **Teslimden önce gerçek Loom/YouTube linki eklenecek.**

Bu iki link buildathon teslimi için zorunludur.

## Kullanılan Teknolojiler

- Python
- FastAPI
- SQLite
- React
- Vite
- REST API
- Rule-based readiness scoring
- NVIDIA API canlı mod hazırlığı
- Ollama/local model yolu
- Webhook/export payload

## Nasıl Çalıştırılır?

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn features.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Test:

```bash
.venv/bin/python -m unittest tests.test_evidence_to_skill tests.test_incident_api tests.test_services
cd frontend
npm run build
```

Örnek API:

```bash
curl -X POST http://127.0.0.1:8000/incidents/analyze \
  -H "X-Kanit-API-Key: demo-local-key" \
  -F "incident_type=quality_8d_capa" \
  -F "employee_code=task-route-001" \
  -F "role_code=quality_engineer" \
  -F "team_code=supplier_quality" \
  -F "station_code=station-final-inspection" \
  -F "case_text=$(cat features/data/sample_cases/01_missing_evidence.txt)"
```

## Güven Sınırları

- Demo gerçek Ford veya müşteri verisi kullanmaz.
- Sistem kişi suçlamaz.
- Varsayılan analiz istasyon, takım ve rol seviyesindedir.
- AI tek başına readiness kapatamaz.
- Bilinmeyen etiketler insana yönlenir.
- ROI çıktısı yalnızca pilot hipotezidir.

## Kaynaklar

- [ASQ, Eight Disciplines 8D](https://asq.org/quality-resources/eight-disciplines-8d)
- [World Economic Forum, Future of Jobs Report 2025](https://www.weforum.org/publications/the-future-of-jobs-report-2025/)
- [Ford Otosan Faaliyet Raporları](https://www.fordotosan.com.tr/tr/yatirimcilar/finansal-raporlar/faaliyet-raporlari)
