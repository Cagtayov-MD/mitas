# MITAS 3.5 Karar Dokümanları Denetim Raporu

## 1. Kapsam

Denetlenen dosyalar:

- MITAS_Profile_Routing_Kaba_Kararlar_v1.md
- MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md
- MITAS_Karar_Denetim_Checklist_v1.md

Bu rapor yalnızca dokümantasyon/inceleme görevidir. Kod, test, model, YAML, pipeline veya UI üretilmemiştir.

## 2. MITAS_Profile_Routing_Kaba_Kararlar_v1.md Denetimi

| Madde | Durum | Açıklama | Aksiyon |
| --- | --- | --- | --- |
| 1. Bu kararın owner’ı var mı? | Eksik | Profil routing kararlarının sahibi kişi/ekip olarak atanmadı. | Profil karar owner’ı master veya ara karar dokümanında atanmalı. |
| 2. Test seti / ground truth gerektiriyor mu? | Sonra değerlendirilecek | Profil davranışları test seti ve benchmark ile doğrulanmalı; bu doküman kaba routing kararıdır. | Sprint 4 sonrası profil bazlı test seti ihtiyacı işaretlenmeli. |
| 3. Benchmark görmeden ana motor ilan ediyor muyuz? | OK | Doküman model veya production ana motor ilan etmiyor. | Aksiyon yok. |
| 4. Performans hedefi ölçülmüş mü, yoksa niyet mi? | Sonra değerlendirilecek | Profil stratejilerinin runtime etkisi henüz ölçülmedi. | Profil bazlı runtime ölçümü benchmark aşamasında yapılmalı. |
| 5. VRAM/runtime etkisi var mı? | Sonra değerlendirilecek | Visual tag, scene detection, diarization ve audio activity profil bazlı maliyet yaratabilir. | VRAM/runtime etkileri model smoke ve benchmark aşamasında ölçülmeli. |
| 6. Başka modüle bağımlı mı? | OK | ASR, OCR, diarization, visual tag, scene detection ve audio activity bağımlılıkları açıkça görülüyor. | Aksiyon yok. |
| 7. P1 kapısı ise sırası belli mi? | Bu karar için geçerli değil | Bu doküman P1 kapı zinciri değil, profil routing kararıdır. | Aksiyon yok. |
| 8. Schema değiştiriyorsa schema_version var mı? | Bu karar için geçerli değil | Schema değişikliği tanımlamıyor. | Aksiyon yok. |
| 9. Eski veriye migration gerekiyor mu? | Bu karar için geçerli değil | Mevcut veri yapısını değiştirmiyor. | Aksiyon yok. |
| 10. Review UI / kullanıcı akışıyla çelişiyor mu? | OK | ASR streaming_transcription tracking overlay davranışı ve yasakları açık; ayrı demo profili kaldırılmış. | UI tasarımına geçildiğinde bu karar referans alınmalı. |
| 11. Runtime override ile profil default’ları karışıyor mu? | OK | `profile_defaults + runtime_overrides = resolved_config` kuralı açık. | Aksiyon yok. |
| 12. Bu karar master’a mı, ara karar dokümanına mı girmeli? | OK | Kaba karar ara dokümanda kalmalı; ana ilkeler master’a özetlenmeli. | Master özetine profil listesi, demo kaldırma ve override kuralı taşınmalı. |

## 3. MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md Denetimi

| Madde | Durum | Açıklama | Aksiyon |
| --- | --- | --- | --- |
| 1. Bu kararın owner’ı var mı? | Eksik | Test Set Owner ve Ground Truth Owner rolleri tanımlı ama kişi/ekip ataması yok. | Benchmark başlamadan owner atamaları yapılmalı. |
| 2. Test seti / ground truth gerektiriyor mu? | OK | Test seti ve ground truth benchmark ön koşulu olarak yazılmış. | Aksiyon yok. |
| 3. Benchmark görmeden ana motor ilan ediyor muyuz? | OK | Hiçbir modelin benchmark öncesi production ana motor ilan edilmeyeceği açık. | Aksiyon yok. |
| 4. Performans hedefi ölçülmüş mü, yoksa niyet mi? | Sonra değerlendirilecek | Performans bütçesi ölçülecek kabul alanı olarak tanımlı; henüz ölçüm yok. | Profil bazlı runtime ölçümü P1 zincirinde yapılmalı. |
| 5. VRAM/runtime etkisi var mı? | OK | VRAM ve runtime ölçümü model seçimi ve P1 kapıları içine alınmış. | Aksiyon yok. |
| 6. Başka modüle bağımlı mı? | OK | P1 kapıları bağımlılık zinciri olarak tanımlanmış. | Aksiyon yok. |
| 7. P1 kapısı ise sırası belli mi? | OK | A-I sıralı bağımlılık zinciri mevcut. | Aksiyon yok. |
| 8. Schema değiştiriyorsa schema_version var mı? | OK | Ana schema modelleri için `schema_version: "1.0"` kararı var. | Sprint 4 öncesi/sonrası schema uygulama işi açılmalı. |
| 9. Eski veriye migration gerekiyor mu? | OK | Kırıcı değişiklikte migration script’i yazılacağı belirtilmiş. | Migration ihtiyacı schema değişiminde ayrıca değerlendirilmeli. |
| 10. Review UI / kullanıcı akışıyla çelişiyor mu? | OK | Review UI ile Face Bank Management ayrımı düzeltilmiş. | UI sprintinde 4 alanlı MVP dikkate alınmalı. |
| 11. Runtime override ile profil default’ları karışıyor mu? | Bu karar için geçerli değil | Bu doküman P1/mimari düzeltme dokümanı; override kuralı profil routing dokümanında ele alınıyor. | Aksiyon yok. |
| 12. Bu karar master’a mı, ara karar dokümanına mı girmeli? | OK | Master’a taşınacak özet bölümü mevcut. | Master güncellemesinde bu özet taşınmalı. |

## 4. MITAS_Karar_Denetim_Checklist_v1.md Denetimi

| Madde | Durum | Açıklama | Aksiyon |
| --- | --- | --- | --- |
| 1. Bu kararın owner’ı var mı? | Eksik | Checklist’in bakım sahibi/karar sahibi atanmadı. | Checklist owner’ı master veya ara karar dokümanında atanmalı. |
| 2. Test seti / ground truth gerektiriyor mu? | Bu karar için geçerli değil | Checklist dokümanı test seti veya ground truth üretmez. | Aksiyon yok. |
| 3. Benchmark görmeden ana motor ilan ediyor muyuz? | OK | Checklist’in ana amacı bunu engellemektir. | Aksiyon yok. |
| 4. Performans hedefi ölçülmüş mü, yoksa niyet mi? | Bu karar için geçerli değil | Performans hedefi tanımlamıyor; performans kontrol sorusu içeriyor. | Aksiyon yok. |
| 5. VRAM/runtime etkisi var mı? | Bu karar için geçerli değil | Teknik runtime etkisi yok; VRAM/runtime kontrol maddesi içeriyor. | Aksiyon yok. |
| 6. Başka modüle bağımlı mı? | Bu karar için geçerli değil | Bağımsız karar filtresi. | Aksiyon yok. |
| 7. P1 kapısı ise sırası belli mi? | Bu karar için geçerli değil | Checklist P1 kapısı değildir. | Aksiyon yok. |
| 8. Schema değiştiriyorsa schema_version var mı? | Bu karar için geçerli değil | Schema değiştirmiyor. | Aksiyon yok. |
| 9. Eski veriye migration gerekiyor mu? | Bu karar için geçerli değil | Mevcut veriyi değiştirmiyor. | Aksiyon yok. |
| 10. Review UI / kullanıcı akışıyla çelişiyor mu? | OK | UI/review çelişkilerini yakalamak üzere madde içeriyor. | Aksiyon yok. |
| 11. Runtime override ile profil default’ları karışıyor mu? | OK | Override/default karışıklığını yakalamak üzere madde içeriyor. | Aksiyon yok. |
| 12. Bu karar master’a mı, ara karar dokümanına mı girmeli? | OK | Checklist ara doküman olarak kalmalı; master’a süreç kuralı olarak özetlenmeli. | Master plan süreç bölümüne kısa özet taşınmalı. |

## 5. Master’a Taşınması Gereken Kararlar

### Profil listesi

Master’a taşınmalı.

6 içerik profili şunlardır: `film_dizi`, `haber`, `studio_program`, `muzik_eglence`, `spor_karsilasma`, `belgesel`.

STT ayrı ana profil değildir; ASR modülünün `streaming_transcription` alt modu olarak ele alınır.

### Demo profilinin kaldırılması

Master’a taşınmalı.

Demo ayrı profil değildir; kaldırılmıştır.

### ASR streaming_transcription + tracking overlay

Master’a özet taşınmalı.

Detaylı mikro-akış ara dokümanda kalabilir, ancak `ASR > streaming_transcription > tracking_overlay` yapısı master’da yer almalıdır.

### Runtime override / resolved_config

Master’a taşınmalı.

Temel kural:

```text
profile_defaults + runtime_overrides = resolved_config
```

Runtime override global modülü değil, seçilen profilin o job içindeki davranışını değiştirir.

### Model seçim disiplini

Master’a taşınmalı.

Hiçbir model benchmark öncesi production ana motor ilan edilmez.

### Test Set Owner / Ground Truth Owner blocker

Master’a taşınmalı.

Bu owner’lar atanmadıkça benchmark başlamaz.

### P1 bağımlılık zinciri

Master’a taşınmalı.

A-I sıralı zincir master planın P1 kapıları bölümüne girmelidir.

### Worker kararı

Master’a taşınmalı.

v1 worker kararı: DB tabanlı single worker.

### Review UI / Face Bank ayrımı

Master’a taşınmalı.

Review UI MVP 4 alan olarak düzeltilmelidir: Face review, OCR/KJ review, Song performance review, Face Bank Management.

### schema_version kararı

Master’a taşınmalı.

Ana schema modellerinde `schema_version` zorunludur ve başlangıç değeri `"1.0"` olmalıdır.

## 6. Ara Dokümanda Kalması Gereken Detaylar

- Profil bazlı kaba davranış detayları.
- `film_dizi`, `haber`, `studio_program`, `muzik_eglence`, `spor_karsilasma`, `belgesel` altındaki ayrıntılı notlar.
- ASR `streaming_transcription` tracking overlay mikro-akışı ve “Kimi takip edeyim abicim?” kullanıcı penceresi metni.
- Profil bazlı visual tag yoğunluk farkları.
- OCR adaylarının ayrıntılı test önceliği.
- Performans bütçesi yorumları ve 60-80 dakika bandının risk olarak görülmesi.
- Test Set Owner ve Ground Truth Owner sorumluluk listeleri.
- P1 kapılarının A-I ayrıntılı bağımlılık zinciri.
- Face review ile Face Bank Management operasyonel ayrımı.
- Checklist cevap seçenekleri ve kullanım kuralı.

## 7. Eksik / Riskli Kalan Maddeler

- Profil routing kararları için owner atanmadı.
- Checklist dokümanının bakım/karar owner’ı atanmadı.
- Test Set Owner ve Ground Truth Owner kişi/ekip olarak atanmadı.
- Profil bazlı test seti ve ground truth ihtiyacı ileride netleştirilmeli.
- Profil bazlı VRAM/runtime etkileri henüz ölçülmedi.
- Performans bütçesi henüz ölçülmedi; şu an doğrulanacak kabul alanı olarak duruyor.

## 8. Sprint 3.5 Durumu

Sprint 3.5 DONE olabilir

Gerekçe:

- Üç ara karar dokümanı 12 maddelik checklist ile denetlendi.
- Master’a taşınması gereken kararlar ayrıldı.
- Ara dokümanda kalması gereken detaylar ayrıldı.
- Eksik/riskli kalan maddeler açıkça yazıldı.

Bu karar implementation, benchmark veya model seçimi kapanışı değildir.

## 9. Son Karar

Sprint 3.5 dokümantasyon/karar denetimi kapanabilir.

Master plan güncellemesine geçmeden önce bu rapordaki master’a taşınacak kararlar kullanılmalıdır. Owner atamaları, test seti, ground truth, VRAM/runtime ölçümü ve performans doğrulaması açık takip kalemi olarak kalır.
