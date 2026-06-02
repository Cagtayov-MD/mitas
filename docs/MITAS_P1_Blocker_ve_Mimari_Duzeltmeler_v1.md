# MITAS P1 Blocker ve Mimari Düzeltmeler v1

## 1. Amaç

Bu doküman, MITAS master planına eklenecek P1 blocker ve mimari düzeltme kararlarını toplar.

Bu dosya implementation dosyası değildir.
Kod, model, pipeline veya UI üretmez.

## 2. Model Seçim Disiplini

Hiçbir model benchmark yapılmadan production ana motoru ilan edilmez.

Model listelerinde görünen sıralama kesin kalite sıralaması değildir; test önceliğidir.

Bu kural şu alanların tamamı için geçerlidir:

- OCR
- ASR
- Face
- Visual Tag
- Audio Activity
- Song Recognition
- Speech Enhancement
- Diarization

Model seçimi şu koşullar sağlanmadan kapanmaz:

1. Test seti hazırdır.
2. Ground truth hazırdır.
3. Smoke/import testi geçmiştir.
4. VRAM ölçümü alınmıştır.
5. Runtime ölçümü alınmıştır.
6. Kalite metrikleri hesaplanmıştır.
7. Profil bazlı uygunluk değerlendirilmiştir.
8. Seçim nedeni rapora yazılmıştır.

## 3. OCR Adayları Kararı

OneOCR aktif kullanılan ve öncelikli test edilecek OCR adayıdır.

Güncel OCR test önceliği:

1. OneOCR
2. PaddleOCR
3. VITOS baseline
4. Tesseract

EasyOCR aktif test kapsamindan cikarildi; PaddleOCR hatti ile devam edilir.

Notlar:

- OneOCR lisans nedeniyle düşürülmez.
- OneOCR aktif olarak kullanılmaktadır.
- Lisans / ticari dağıtım konusu bu proje için P1 blocker değildir.
- Proje kurum içi iş kolaylaştırma amacıyla kullanılmaktadır.
- Dış ticari ürün veya üçüncü tarafa dağıtılan yazılım olarak konumlandırılmamaktadır.
- Buna rağmen production ana OCR motoru benchmark sonucuna göre seçilecektir.

## 4. Performans Bütçesi Kararı

Önceki “1 saat video ≤ 1 saat” ifadesi kesin başarı vaadi değildir.

Performans bütçesi benchmark ile doğrulanacak kabul alanıdır.

Kural:

- Performans bütçesi ölçülmeden kesin hedef değildir.
- İlk hedef, profil bazlı gerçek runtime ölçümü almaktır.
- Süreler yüksek çıkarsa pipeline optimizasyonu, model load/unload stratejisi, modül sırası, adaptive sampling ve GPU/CPU iş bölümü yeniden düzenlenecektir.
- Performans ölçümü teslimiyet değil, optimizasyon alarmıdır.

Not:

Kullanıcı için 60-80 dakika bandı korkutucu ve istenmeyen bir seviyedir.
Bu nedenle performans ölçümü erken sprintlerde yapılacak ve hızlandırma kritik takip kalemi olacaktır.

## 5. Test Set Owner / Ground Truth Owner Blocker

Test Set Owner ve Ground Truth Owner atanmadan benchmark sprinti başlamaz.

Bu bölüm dolmadan v0.1 model benchmark süreci başlatılamaz.

Test Set Owner sorumlulukları:

- Test videolarını seçmek
- İçerik türlerini dengelemek
- Dosyaların doğru klasörlerde hazır olmasını sağlamak
- Film/dizi, haber, studio, müzik/eğlence, spor, belgesel ve ASR `streaming_transcription` test örneklerini temsil etmek

Ground Truth Owner sorumlulukları:

- Doğru transcriptleri onaylamak
- OCR/KJ doğrularını onaylamak
- Spor skor/takım/lig doğrularını onaylamak
- Face/person doğrularını gerektiğinde onaylamak
- Visual tag doğrularını gerektiğinde onaylamak
- Benchmark geçer/kaldı kararına veri sağlamak

Bu roller aynı kişi olabilir ama dokümanda ayrı rol olarak tutulacaktır.

## 6. P1 Kapıları Bağımlılık Zinciri

P1 kapıları düz liste gibi değil, bağımlılık zinciri olarak ele alınacaktır.

Sıra:

A. Test Set Owner + Ground Truth Owner atanır.  
B. Test seti ve ground truth klasörleri hazırlanır.  
C. Model smoke/import testleri yapılır.  
D. VRAM ölçümü yapılır.  
E. Compatibility matrix çıkarılır.  
F. Performans bütçesi doğrulanır.  
G. Fallback kararları verilir.  
H. Profil bazlı model seçimleri kesinleşir.  
I. v0.1 vertical slice başlatılır.

Notlar:

- VRAM ölçümü olmadan compatibility matrix tamamlanmış sayılmaz.
- Compatibility matrix olmadan performans bütçesi güvenilir değildir.
- Performans bütçesi olmadan fallback kararları kesinleştirilmez.

## 7. Worker Kararı

v1 worker kararı:

DB tabanlı single worker.

v1’de Celery, RQ veya Redis zorunlu değildir.

Gerekçe:

- Daha az altyapı bağımlılığı
- Daha sade kurulum
- Tek makine / tek GPU akışına uygunluk
- MITAS’ın ilk aşamasında job state ve crash recovery için yeterli olması

v2 adayları:

- RQ / Redis
- Celery
- başka queue altyapıları

Bu adaylar ancak gerçek paralel ölçek ihtiyacı doğarsa değerlendirilir.

## 8. Review UI ve Face Bank Management Ayrımı

Review UI ile Face Bank Management aynı şey değildir.

Review UI MVP alanları:

1. Face review
2. OCR/KJ review
3. Song performance review
4. Face Bank Management

Face review:

- bilinmeyen yüzleri inceleme
- eşleşme adaylarını onaylama/reddetme

Face Bank Management:

- yeni kişi oluşturma
- fotoğraf yükleme
- embedding çıkarma
- kalitesiz fotoğrafı eleme
- kişi bankasını yönetme

Not:

Eğer Face Bank Management v1 MVP içinde tutulacaksa Review UI MVP 3 alan değil, 4 alan olarak yazılmalıdır.

## 9. Schema Versioning Kararı

Tüm ana schema modellerine schema_version alanı eklenecektir.

Kapsam:

- MediaItem
- TimelineEvent
- Evidence
- CandidateRelation
- JobRun
- ModuleRun

Başlangıç:

schema_version: "1.0"

Kural:

- Schema kırıcı şekilde değişirse yeni schema_version açılır.
- Eski JSON kayıtları sessizce yeni formata zorlanmaz.
- Gerekirse migration script’i yazılır.
- Eski review onayları ve eski event kayıtları hangi schema_version ile üretildiyse o bilgi korunur.

## 10. Demo / Showcase Sadeleştirme Kararı

Demo ayrı profil değildir.

Demo profili kaldırılmıştır.

Demo ihtiyacı şu yapıya taşınmıştır:

ASR > streaming_transcription > tracking_overlay

Tracking overlay:

- checkbox ile açılır
- tik açılınca küçük pencere çıkar:
  “Kimi takip edeyim abicim?”
- kullanıcı ekrandaki kişiyi seçer
- sistem sadece seçilen kişiyi takip eder
- tik kaldırılınca tracking kapanır

Yasaklar:

- DB’ye yazmaz
- enrollment yapmaz
- face bank match yapmaz
- identity claim yapmaz
- production face recognition olarak davranmaz

Bu yapı showcase maliyetini düşürür ve ayrı demo pipeline ihtiyacını ortadan kaldırır.

## 11. Master’a Taşınacak Özet

Bu dokümandaki kararlar daha sonra MITAS_Master_Plan_Denetimli_v5.md dosyasına özet olarak taşınacaktır.

Master’a taşınacak ana kararlar:

- Hiçbir model benchmark öncesi production ana motor ilan edilmez.
- OneOCR öncelikli OCR test adayıdır.
- Lisans konusu P1 blocker değildir.
- Test Set Owner / Ground Truth Owner atanmadıkça benchmark başlamaz.
- P1 kapıları bağımlılık zinciriyle yönetilir.
- v1 worker DB tabanlı single worker’dır.
- Review UI MVP 4 alan olarak düzeltilir.
- schema_version zorunludur.
- demo profili yoktur; ASR `streaming_transcription` tracking overlay vardır.

## 12. Son Karar

Bu dosya kabul edilen mimari düzeltmeleri sabitler.

Sprint 4’e geçmeden önce profil routing dokümanı ve bu düzeltme dokümanı birlikte master plana özetlenmelidir.
