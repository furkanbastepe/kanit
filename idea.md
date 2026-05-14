# Fikir: KANIT

## Problem

Şirketler 8D/CAPA kalite dosyalarını kapatıyor. Ama dosyanın içindeki tekrar eden kanıt zayıflığı çoğu zaman öğrenme aksiyonuna dönüşmüyor.

Bir dosyada “etkinlik kontrolü eksik” yazıyor. Başka dosyada “effectiveness check missing” yazıyor. Dil değişiyor, problem aynı kalıyor.

KANIT bu tekrarı yakalamak için var.

## Kullanıcı

İlk kullanıcı kalite mühendisi ve supplier quality ekibidir.

Bu ekipler 8D/CAPA, PPAP, corrective action ve kanıt paketleriyle çalışır. Onlar için dosyanın kapanması yetmez. Aynı eksik tekrar ediyor mu, bunu görmek isterler.

İkinci kullanıcı mentor veya ekip lideridir. Çünkü hazır oluş sadece ekranda kapanmaz. Sahada kısa bir pratik ve insan onayı gerekir.

## AI’ın Rolü

AI vaka metnini okur. Kanıt boşluklarını çıkarır. Farklı dillerde yazılmış benzer ifadeleri aynı beceri/süreç riskine bağlar.

Ama son kararı AI vermez.

Readiness skoru görünür kural motoruyla hesaplanır. Kapanış mentor veya kalite reviewer onayı ister.

## Rakip Durum

QMS sistemleri CAPA dosyasını yönetir. LMS sistemleri eğitim verir. Connected worker araçları işi sahaya taşır. Excel ve Power BI geçmişi gösterir. ChatGPT tek dosyayı özetler.

KANIT bunların yerine geçmez.

KANIT aradaki boşluğu hedefler:

```text
kalite kanıtı -> canonical risk -> readiness skoru -> mentor onaylı mikro aksiyon
```

En zor rakip başka bir startup değildir. En zor rakip “bunu zaten QMS ve Excel ile yapıyoruz” refleksidir.

KANIT’ın cevabı basittir:

> Kayıt tutmak başka, tekrar eden kanıt zayıflığını hazır oluş aksiyonuna çevirmek başka.

## Başarı Kriteri

Buildathon sonunda KANIT şunları göstermelidir:

- Sentetik 8D/CAPA vakasından kanıt boşluğu çıkarır.
- Benzer ifadeleri aynı canonical riske bağlar.
- Readiness skorunu açık formülle hesaplar.
- Mentor onayı olmadan riski kapatmaz.
- Kişi puanı değil, istasyon/takım/rol aksiyonu üretir.
- QMS, LMS, connected worker veya BI araçlarına export edilebilir sinyal üretir.

İlk gerçek pilot başarısı:

> 30-50 redakte edilmiş 8D/CAPA vakasında, tekrar eden kanıt boşluklarının kalite reviewer tarafından güvenilir bulunması.
