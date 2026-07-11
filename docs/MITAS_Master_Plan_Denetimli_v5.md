# MITAS Master Plan Denetimli v5

> Not:
> Bu dosya, E:\MITAS altında önceki master plan bulunamadığı için Sprint 3.5 karar özetleriyle yeni master başlangıcı olarak oluşturulmuştur.
> Önceki master plan daha sonra bulunursa bu dosya onunla karşılaştırılacak ve reconcile edilecektir.
> Bu nedenle dosya şu anda “yeni master başlangıcı” olarak kabul edilir; geçmiş master içeriği varsa onun yerine geçtiği varsayılmaz.

## Sprint 3.5 — Karar Özetleri

Bu bölüm, Sprint 3.5 ara karar dokümanlarından master plana taşınacak özet kararları içerir.

Kaynak ara dokümanlar:

- `docs/MITAS_Profile_Routing_Kaba_Kararlar_v1.md`
- `docs/MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md`
- `docs/MITAS_Karar_Denetim_Checklist_v1.md`
- `docs/MITAS_3_5_Karar_Dokumanlari_Denetim_Raporu.md`

### Profil Listesi

MITAS ilk aşamada 6 içerik profili kullanacaktır:

- `film_dizi`
- `haber`
- `studio_program`
- `muzik_eglence`
- `spor_karsilasma`
- `belgesel`

STT ayrı ana profil değildir. Canlı konuşma metne dökümü ASR modülünün `streaming_transcription` alt modu olarak ele alınır.

### Demo Profili Kararı

Demo profili kaldırılmıştır.

Demo ihtiyacı `ASR > streaming_transcription > tracking_overlay` altında yaşayacaktır.

### ASR Streaming Transcription Özeti

ASR alt modları:

- `file_transcription`
- `streaming_transcription`
- `vad`
- `diarization`
- `alignment`

`ASR > streaming_transcription > tracking_overlay`:

- checkbox ile açılır
- kullanıcı ekrandaki kişiyi seçer
- sistem sadece seçilen kişiyi takip eder
- DB’ye yazmaz
- enrollment yapmaz
- face bank match yapmaz
- identity claim yapmaz

### Runtime Override Kuralı

Kural:

```text
profile_defaults + runtime_overrides = resolved_config
```

Runtime override global modülü değil, seçilen profilin o job içindeki davranışını değiştirir.

Örnek:

- `studio_program + visual_tag kapalı` = studio profilinin hafif/adaptif tag davranışı kapalı.
- `belgesel + visual_tag kapalı` = belgesel profilinin daha yoğun/adaptif_full tag davranışı kapalı.

### Model Seçim Disiplini

Hiçbir model benchmark öncesi production ana motor ilan edilmez.

Model sıralamaları kesin kalite sıralaması değil, test önceliğidir.

Bu kural OCR, ASR, Face, Visual Tag, Audio Activity, Song Recognition, Speech Enhancement ve Diarization için geçerlidir.

### OCR Adayları Özeti

OneOCR aktif kullanılan ve öncelikli test edilecek OCR adayıdır.

Ancak production ana OCR motoru benchmark sonucuna göre seçilecektir.

### Test Set Owner / Ground Truth Owner

Test Set Owner ve Ground Truth Owner atanmadan benchmark sprinti başlamaz.

### P1 Kapıları Bağımlılık Zinciri

P1 kapıları düz liste değil, bağımlılık zinciri olarak yönetilecektir.

A. Test Set Owner + Ground Truth Owner atanır.  
B. Test seti ve ground truth klasörleri hazırlanır.  
C. Model smoke/import testleri yapılır.  
D. VRAM ölçümü yapılır.  
E. Compatibility matrix çıkarılır.  
F. Performans bütçesi doğrulanır.  
G. Fallback kararları verilir.  
H. Profil bazlı model seçimleri kesinleşir.  
I. v0.1 vertical slice başlatılır.

### Worker Kararı

v1 worker kararı: DB tabanlı single worker.

RQ / Redis / Celery v2 ölçek adaylarıdır.

### Review UI / Face Bank Ayrımı

Review UI MVP 4 alan olarak yazılmalıdır:

- Face review
- OCR/KJ review
- Song performance review
- Face Bank Management

Review UI ile Face Bank Management aynı şey değildir.

### Schema Versioning

Ana schema modellerinde `schema_version` zorunludur.

Başlangıç değeri: `"1.0"`

Kapsam:

- MediaItem
- TimelineEvent
- Evidence
- CandidateRelation
- JobRun
- ModuleRun

### Karar Denetim Checklist’i

MITAS 12 maddelik karar denetim checklist’i master plan süreç kuralı olarak kabul edilmiştir.

Bir karar checklist’ten geçmeden sabit kabul edilmez.
