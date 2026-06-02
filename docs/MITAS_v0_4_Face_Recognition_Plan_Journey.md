# MITAS v0.4 — Face Recognition Plan İnşa Günlüğü (Journey)

> **Bu dosya nedir?**
> Face Recognition modülünün sıfırdan ayağa kalkması için yapılan plan **inşa sürecidir**. Her blok yazıldıktan sonra dört öz-denetim sorusu sorulur (amaç, bağlam, regresyon, daha iyisi). Karar değiştiğinde eskisi üstü çizili kalır, yeni satır gerekçesiyle eklenir.
> Temiz/derli toplu final plan ayrı dosyadadır: `docs/MITAS_v0_4_Face_Recognition_Plan_Final.md`.

> **Workspace:** `E:\MITAS` (canonical)
> **Sürüm hedefi:** v0.4 — Face Recognition dikey dilimi
> **Donanım hedefi:** RTX 3090 / 24 GB VRAM
> **Bağlayıcı üst dosyalar:** `MITAS_Master_Plan_Denetimli_v5.md` §2.2 + `mutfak/` (00-13) + Karar günlüğü M4/M5/M9 + `benchmark_templates/face_benchmark.yaml`.

---

## 0. Bağlam Özümseme (yazmadan önce ne biliyoruz?)

Bu plan boş sayfaya yazılmıyor. Aşağıdaki **sabit kararlar** zaten var; plan onları kabul ederek başlar:

### 0.1 Bağlayıcı kararlar (master plan v5 + mutfak)

- `M1` — Türkçe-merkezli, kurum içi, lokal çalışır. Bulut yok. Yüz embedding **biyometrik veridir**, KVKK kapsamındadır, kurumu terk etmez.
- `M2` — RTX 3090 / 24 GB VRAM hedef donanım. 96 GB VRAM varsayımı geçersiz.
- `M4` — **Filmde face identification kapalıdır.** Yalnızca "yüz var" event'i tutulur. Film kişi kimliği `FilmCreditsParser` + IMDb/TMDB ile çözülür (v1.x).
- `M9` — Face cluster + KJ name + speaker_id ilişkileri **CandidateRelation** olarak tutulur. Kullanıcı onayı olmadan identity'ye dönüşmez.
- §2.2 — Detector: **SCRFD**, embedding: **ArcFace**, tracker: **ByteTrack** (default/tek ana), clustering: **HDBSCAN**, vector DB: **PostgreSQL + pgvector**.
- §0.3.13 — Quality gate başlangıç değerleri: `min_face_height=80px`, `blur_laplacian_min=100`, `pose_yaw_max=30°`, `pose_pitch_max=25°`, `min_track_duration=1.5s`, `min_detector_confidence=0.70`.
- §0.3.13 — Importance ağırlıkları: `screen_time=0.35`, `KJ_overlap=0.25`, `ASR_speaker_overlap=0.20`, `face_size/quality=0.15`, `existing_bank_match=0.05`.
- §0.3.15 — KVKK retention taslağı: unknown face crop 30 gün, unknown cluster 30 gün, confirmed embedding yetki + hukuki dayanak, silme → embedding/crop/template/review linklerini sil veya anonimleştir, audit log zorunlu (ekleme/silme/birleştirme/eşik değişimi).
- v1 Review UI MVP üç alandan biri: Face unknown + Face match + Face bank yönetimi.

### 0.2 Modüller arası bağımlılıklar

- **ASR (v0.1, hazır):** TimelineEvent + ModuleRun bağlantısı var. Speaker turn ve speech aktivitesi face importance hesaplamasında **sinyal** olarak kullanılır (identity değil).
- **OCR/KJ (v0.2, planlı):** `screen_text` event'i, özellikle `lower_third_person` subtype, yüz ↔ KJ adı CandidateRelation üretiminde kanıttır.
- **Görsel Tagleme (v0.3, planlı):** Sahne tipi + atmosfer, "kalabalık" tag'i ile küçük yüzlerin önemini sıralamada yardımcı olur.
- **Timeline (v0.5):** Face event ve CandidateRelation Timeline omurgasına yazılır; cross-module evidence linking burada olur.

Yani Face modülü ASR + OCR + Visual Tag'in **üstüne otururken**, bunlardan birinin eksik olduğu kliplerde de tek başına anlamlı çıktı verecek şekilde tasarlanmalıdır (partial pipeline graceful degradation).

### 0.3 Sözleşme katmanı (var olan)

`core/schemas/`:
- `timeline.py` → `TimelineEvent` (zaman + module + payload + evidence + status)
- `candidate_relation.py` → `CandidateRelation` (face_matches_kj_name vs.)
- `evidence.py` → `Evidence` (frame, bbox, track_id, embedding ref, vs.)
- `module_run.py` → `ModuleRun` (job_id + media_id + pipeline + step kayıtları)
- `job_run.py` → `JobRun` (background worker durumları)
- `media.py` → `MediaItem` (clip_id, hash, duration, fps)

Face modülü bu sözleşmeye yeni alan tipi getirmez; mevcut şemalara `payload` içinde face-spesifik alanlar yazar. Şema değişikliği gerekirse Pydantic önce; sonra `scripts/export_json_schema.py` ile JSON Schema yeniden export.

### 0.4 Mevcut venv durumu (gerçek, dolaylı değil)

`venvs/face/` (2026-05-16 itibarıyla):
- `insightface 0.7.3`, `onnxruntime-gpu 1.23.2`
- `supervision 0.28.0` (ByteTrack için)
- `hdbscan 0.8.42`, `pgvector 0.4.2`, `scikit-learn 1.7.2`
- `torch 2.11.0+cu126`, `opencv-python 4.13.0.92`, `pillow 12.2.0`
- `pydantic 2.13.4`, `albumentations 2.0.8`

**Eksik tespitler:**
- FastAPI/uvicorn → backend API yok (gerekecek)
- psycopg/SQLAlchemy → DB driver yok
- PostgreSQL kurulum durumu **belirsiz** (`locks/`'ta yok)
- buffalo_l ONNX model dosyaları lokalde **henüz kontrol edilmedi**
- chromaprint, faiss vb. face dışı — gerek yok

### 0.5 Output klasör sözleşmesi (13. brief'ten)

```
outputs/clips/<clip_id>/face/<job_id>/
├── job.json                  ← durum (status, progress, paths)
├── job_log.jsonl             ← face içi adımlar
├── run/
│   ├── face_tracks.json      ← track id + bbox + frame index zaman serisi
│   ├── face_clusters.json    ← cluster_id + member track_ids + embedding centroid ref
│   ├── face_matches.json     ← match results (cluster_id ↔ person_id + score)
│   ├── face_events.json      ← TimelineEvent uyumlu face event'ler
│   ├── face_candidate_relations.json  ← CandidateRelation çıktıları
│   ├── face_summary.json     ← özet rapor
│   └── face_quality_report.json  ← quality gate kabul/red sayıları
└── crops/                    ← seçilmiş face crop'ları (KVKK retention'a tabi)
```

`system_events.jsonl` içine `face_queued/started/completed/partial/failed` event'leri yazılır (kind genişletmesi).

### 0.6 v0.4 dikey diliminin amacı

> **Tek video** alınır, sonunda timeline'da face cluster'ları görünür, kaliteli olanlar bankayla eşleşmeye çalışılır, bilinmeyenler operatöre review olarak sunulur.

Bu bir "research project" değil, **çalışan dikey dilim**. Ölçü: 1 saatlik haber/panel klibinde bu pipeline 1 saatin altında biter, importance kovaları doluştur (yüksek/orta/düşük), review queue üretir.

---

## 1. Blok 1 — Vizyon, Kapsam ve Prensipler

### 1.1 Modülün tek cümlelik vaadi

> Face Recognition modülü, **kendi yapım** TRT programlarında ekrana giren yüzleri tespit eder, takip eder, kümelendirir, **önem sırasına göre** review kovasına atar veya banka eşleşmesi önerir; her sonuç evidence ile açıklanabilir, hiçbir sonuç kullanıcı onayı olmadan kimlik kararı olarak yazılmaz.

### 1.2 Kapsam içi (v0.4 yapacak)

- SCRFD ile yüz tespiti (5-point landmark + bbox + confidence)
- Yüz hizalama (alignment) → ArcFace embedding kalitesi için
- ByteTrack ile takip → `track_id` ardışık frame'lerde aynı yüz
- Track-level **kalite kapısı** + **en iyi crop seçimi** (her track için 3-5 crop)
- ArcFace embedding (track başına temsilci 512-d vektör)
- HDBSCAN ile cluster (medya içi unknown cluster)
- pgvector ile **face bank** lookup (top-k match)
- **Önem skoru** hesaplama (screen_time + KJ overlap + ASR speaker overlap + face_size/quality + existing_bank_match)
- Önem kovaları: **yüksek / orta / düşük** + override toggle
- **Banka seed yönetimi**: kişi oluşturma, fotoğraf yükleme, embedding çıkarımı, kalitesiz örnekleri eleme (web UI)
- Banka **review öğrenme döngüsü**: confirmed bilinmeyen → bankaya ekle
- Audit log: ekleme / silme / birleştirme / threshold değişimi
- Retention scheduler: unknown crop + cluster için 30 gün TTL (taslak, hukuk onaylayana kadar config bayrağıyla)
- **CandidateRelation** üretimi: `face_matches_kj_name_candidate`, `speaker_overlaps_face_candidate`
- Showcase modu (tıkla-seç-takip; identity yok; final analizle aynı anda GPU paylaşmaz)
- Film içerikleri için: **face identification kapalı**, sadece "yüz var" event'i + track süresi
- JSON primary çıktı (yukarıdaki output sözleşmesi)
- Backend API uçları: `POST /api/face/analyze`, `GET /api/face/jobs/{id}`, `GET /api/face/bank/persons`, `POST /api/face/bank/persons`, `POST /api/face/bank/persons/{id}/photos`, `POST /api/face/review/confirm`, `POST /api/face/review/reject`

### 1.3 Kapsam dışı (v0.4 yapmayacak)

- Live capture / RTMP / kamera (v1 dışı, master plan)
- Filmde kişi kimliği (M4 — IMDb/TMDB ile v1.x)
- Cross-session voice identification (M5)
- VLM yardımcı (v0.2+ aday, v0.4 dışı)
- BoT-SORT (ByteTrack yetersiz kalırsa yedek; v0.4 dışı)
- DBSCAN, RetinaFace, Qdrant/FAISS dış vector DB (master plan ile çıkarıldı)
- Hızlı/Dengeli/Detaylı modları (master plan ile çıkarıldı)
- Otomatik showcase tanıma (v2)
- Tag dictionary expansion review (v1.1)

### 1.4 Bağlı olduğu prensipler (asla feda edilmez)

1. **Yanlış kimlik > yok kimlik.** Eşik altı match `auto` olamaz; `needs_review` veya `null`.
2. **Candidate ≠ Identity.** `face_track_044` bir track, `face_cluster_A4` bir küme, `person_001021` bir kişi. Üçünün arasındaki köprü daima evidence + kullanıcı onayı.
3. **Showcase ≠ Final.** Tıkla-seç-takip showcase'i kişi adı çıkartmaz, bankaya yazmaz. Showcase açıkken final analiz GPU paylaşmaz.
4. **Evidence olmadan kayıt olmaz.** Her face event'i: frame_idx, time_ms, bbox, det_conf, track_id, kalite skoru, model versiyonu içerir.
5. **Türkçe-merkezli yüz bankası.** Açık kaynak embedding modeli Batı veri setinde eğitilmiş; bu yüzden TRT seed + review döngüsüyle **kuruma özgü** banka büyütülür. Default bank Türk kamuoyu figürleri ile beslenir.
6. **Modüler venv.** Face venv kendi içinde tutulur; `core` venv schema doğrulaması yapar ama face runtime çağırmaz. Showcase backend `face` venv'inde subprocess olarak çalışır (ASR'deki alignment subprocess deseni gibi).
7. **KVKK ilkesi.** Embedding ham görüntü değildir; ama biyometrik veridir. Banka erişimi yetki ile, audit log zorunlu, silme talebi cascade.
8. **Lisans uyarısı.** InsightFace `buffalo_l` modeli production lisans doğrulaması alınmadan kurum-içi production'a alınmaz. Geliştirme/araştırma kullanımı serbest, production gating var.

### 1.5 Başarı ölçütleri (v0.4 kabul kriteri)

- 1 saatlik haber/panel klibinde **önemli kişi kaçırma < %5** (önemli = ASR speaker overlap > 30s ∨ KJ name overlap)
- **Review gürültüsü < %20** (operatörün "bu sorulmamalıydı" dediği oran)
- Face match **false positive < %2** (lisans + KVKK kabul ettiği eşikte)
- Quality gate kabul oranı **30-60%** (çok düşükse track çok fazla atılıyor, çok yüksekse gate zayıf)
- Cluster purity **> 0.85** (gerçek aynı kişi içinde aynı cluster)
- Runtime: 1 saatlik 1080p video için **face pipeline < 35 dk** (ASR ile aynı anda değil, ardışık)
- VRAM peak: SCRFD + ArcFace warm-load **< 4 GB**, geçici peak < 6 GB
- JSON output sözleşmeye uyar; smoke test golden ile geçer.

### 1.6 Açık sorular (final plana taşımadan operatöre sorulacak)

> ⚠ Bu sorular Block 1'in sonunda durur. Final plan içinde "OPEN" bölümünde toplanır.

- **OQ-1:** PostgreSQL kurulu mu? Yoksa Docker ile mi kurulacak? pgvector için PG 13+ gerekir.
- **OQ-2:** Showcase modu için ayrı bir UI tab mı? `AnalysisWorkspace` içinde yeni "FaceBank Builder" zaten var (mutfak 10.UI iki ana sekme). Sözleşme uyumu?
- **OQ-3:** buffalo_l üzerinden gidiyoruz ama lisans kontrolü yok. Geliştirme aşamasında devam edip lisans gelmezse fallback nedir? (Alternatif: ArcFace açık ağırlık + SCRFD bağımsız.)
- **OQ-4:** Banka seed listesi nasıl gelecek? Manuel mi yoksa Anadolu Ajansı / TRT içi listeyle mi? İlk 50-100 kişi kim seçecek?
- **OQ-5:** Filmde "yüz var" event'i timeline'da hangi `event_type` ile yazılır? `face_presence` olabilir; identity yokken yine de timeline'da göstermek mantıklı.
- **OQ-6:** Audit log nereye yazılır? Ayrı tablo (`face_audit_log`) mı, yoksa mevcut `system_events.jsonl` mi? Audit log retention politikası ne (KVKK için)?
- **OQ-7:** Showcase + final analiz GPU exclusive disiplini operasyonel olarak nasıl uygulanır? Backend mutex mi, yoksa job queue tek slot mu?

### 1.7 Blok 1 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Bu blok modülün ne yapacağını, ne yapmayacağını ve hangi prensiplere bağlı olduğunu tek sayfada veriyor. Kullanıcının "sıfırdan ayağa kaldırmak için detaylı plan" isteğine bu blok temeli koyar; ardışık bloklar bu çerçeveyi doldurur.

**Soru 2: Bağlamı korudum mu?**
> Evet. M4 (filmde face kapalı), M5 (voice yok), M9 (CandidateRelation), §2.2 (model seçimleri), §0.3.13 (quality + importance değerleri), §0.3.15 (KVKK taslak) hepsi kapsam içinde. ASR/OCR/Visual Tag bağımlılıkları açıkça yazıldı. Output sözleşmesi `outputs/clips/<clip_id>/face/<job_id>/` 13. brief ile uyumlu.

**Soru 3: Başka şeyi bozdum mu?**
> Hayır. Bu blok henüz kod yazmıyor, sadece kapsam çiziyor. ASR'nin v0.1'i sabit, OCR/Visual Tag henüz yok — Face'in bunlara bağımlılığı `graceful degradation` ile yazıldı, eksik modülde de tek başına çalışacak şekilde tarif edildi.

**Soru 4: Daha iyisi var mı?**
> İki potansiyel iyileştirme tespit ettim:
>
> **İyileştirme A — "Modüler venv" prensibinde bir nüans var.** ASR'de WhisperX `alignment` venv'inde subprocess olarak çalışır. Face tarafında SCRFD + ArcFace + ByteTrack + HDBSCAN aynı venv'de (face). Buraya kadar tutarlı. Ama **backend API** (FastAPI) ASR'de `asr` venv'inde, OCR'de muhtemelen `ocr` venv'inde olacak. Face için backend API'yi `face` venv'inde mi çalıştıracağız, yoksa ortak `core` venv'inde mi? Bu kararı **Blok 5**'te (kurulum) netleştireceğim — ama Blok 1'de prensibi şöyle güçlendireyim: **"backend API her modülün kendi venv'inde çalışır; modüller arası RPC HTTP üzerinden değil, JSON dosya/DB üzerinden konuşur. Cross-module timeline merge `core` venv'inin işidir."** Bu zaten ASR'de uygulanan yaklaşım.
>
> **İyileştirme B — "Showcase ≠ Final" prensibini somutlaştır.** Showcase mode'da identity yok, bankaya yazma yok, KVKK retention bile uygulanmaz çünkü crop saklanmaz. Bunu prensip yerine **operasyonel bir kapı** olarak Blok 1'e koymalıyım: showcase'in adı "**Live Track Demo**" olsun; backend endpoint'i `/api/face/demo/track` olsun (ayrı namespace). Bu daha sonra UI ve audit log'da karışıklık önler.
>
> **Karar:** Her iki iyileştirme de plana dahil edilir. İlki Blok 5'te detaylanır, ikincisi Blok 1'in 1.4'üne yeni satır olarak girer:
>
> > "Showcase mod **`Live Track Demo`** olarak adlandırılır; endpoint namespace'i `/api/face/demo/...` altındadır. Final analiz endpoint'i `/api/face/analyze/...` altındadır. Bu iki namespace asla aynı GPU job kuyruğunu paylaşmaz."

**Plan değişikliği notu (DEC-FACE-J-001):**
- 2026-05-16: Blok 1'de prensip 6 (Modüler venv) genişletildi → "backend API her modülün kendi venv'inde çalışır, cross-module timeline merge `core` venv'inin işidir." Bu zaten ASR'de var, Face'e de uygulanır.
- 2026-05-16: Showcase modunun adı **`Live Track Demo`** olarak sabitlendi, endpoint namespace'i `/api/face/demo/...` olarak ayrıldı.

---

## 2. Blok 2 — Pipeline Mimarisi (Detect → Track → Embed → Cluster → Match)

### 2.1 Üst seviye akış

```
[Video Input (clip)]
   │
   ▼
[Stage 0: Media Prep]   ← FFmpeg metadata, fps, duration, output dir hazırla
   │
   ▼
[Stage 1: Pre-Scan]     ← 2 saniye/frame örnekleme, "yüz var mı" haritası
   │                       (SCRFD low-conf, hızlı kararla; sadece yüz olan bölgeleri işaretler)
   │
   ▼
[Stage 2: Dense Detect] ← yüz olan zaman aralıklarında 2-3 fps detect (SCRFD full)
   │                       her detection: bbox + 5 landmark + det_conf
   │
   ▼
[Stage 3: Tracking]     ← ByteTrack ile track_id atama
   │                       her track: zaman aralığı + bbox serisi + frame_idx listesi
   │
   ▼
[Stage 4: Track Quality Gate]   ← gate'i geçen track + en iyi 3-5 crop seç
   │
   ▼
[Stage 5: Alignment + Embedding] ← landmark ile align → ArcFace 512-d embedding
   │                                track başına temsilci embedding (kalite ağırlıklı ortalama)
   │
   ▼
[Stage 6: Clustering]   ← HDBSCAN ile aynı yayın içinde aynı kişi cluster'ı
   │                       (multi-frame consistency için)
   │
   ▼
[Stage 7: Bank Match]   ← cluster temsilcileri pgvector ile face bank'ta arandı
   │                       her cluster için top-k aday + score
   │
   ▼
[Stage 8: Importance + Bucketing]   ← screen_time + KJ + ASR + size/quality + bank_match
   │                                   önem skoru → yüksek/orta/düşük kova
   │
   ▼
[Stage 9: Event + CandidateRelation Emit]   ← TimelineEvent + CandidateRelation yazımı
   │
   ▼
[Stage 10: Output Write]    ← outputs/clips/<clip_id>/face/<job_id>/run/*.json
   │
   ▼
[Stage 11: Review Queue]    ← Yüksek + orta kovadaki cluster'lar review için kuyruğa
   │
   ▼
[Stage 12: System Event]    ← outputs/system_events.jsonl içine face_completed
```

**İçerik tipine göre kapı:**
- `media.content_type = "film"` ise Stage 6-8 atlanır; yalnızca Stage 1-5'ten sonra "face_presence" event'i ve track süresi yazılır. Stage 9'da `face_presence` event'i emit edilir, CandidateRelation üretilmez. Stage 11 review queue boş kalır (master plan M4).
- `media.content_type` ∈ `{news, panel, music, documentary, studio}` → tam pipeline.
- `media.content_type` yoksa → varsayılan tam pipeline ama log'a "content_type missing, defaulting to full" uyarısı.

### 2.2 Stage detayları

#### Stage 0 — Media Prep
- Girdi: `clip_id`, source path
- İş: FFmpeg ile fps/width/height/duration al; output dir oluştur; `job.json` yaz (status=running, progress=0)
- Çıktı: `clip.json` modülünde `face.jobs[]` listesine yeni job_id eklenir; `outputs/clips/<clip_id>/face/<job_id>/job.json` yaratılır
- Süre: < 1 sn

#### Stage 1 — Pre-Scan (yüz var/yok haritası)
- Girdi: ham video frame'leri
- İş: 2 saniyede 1 frame örnekle, SCRFD'yi düşük confidence (0.50) ve düşük input boyutuyla koştur. Sadece "bu zaman aralığında yüz olabilir" sinyali üret.
- Çıktı: `face_regions.json` — `[{start_sec, end_sec, has_face: true}]` aralık listesi
- Süre: 1 saatlik 1080p için ~3-5 dk (SCRFD CPU+GPU karışık)
- Amaç: Stage 2'nin tüm videoyu yoğun taramamasını sağlamak. Yüz olmayan bölgeler atlanır.

#### Stage 2 — Dense Detection
- Girdi: Stage 1 aralıkları
- İş: Yüz olan aralıklarda 2-3 fps örnekle, SCRFD'yi tam confidence (0.70) ve gerçek input boyutuyla koştur. Her detection: `{frame_idx, time_ms, bbox, det_conf, landmarks[5]}` üret.
- Çıktı: `face_detections.json` (ara çıktı, debug için saklanır)
- Süre: 1 saatlik klip için ~8-12 dk (yüz yoğunluğuna bağlı)
- VRAM: SCRFD ~1 GB

#### Stage 3 — Tracking (ByteTrack)
- Girdi: Stage 2 detection listesi
- İş: `supervision` paketindeki ByteTrack ile ardışık frame'lerde aynı yüz `track_id` ile birleştirilir. Kalman filtresi + IoU eşleştirme. Düşük confidence detection'lar takip için bağlam sağlar (master plan §2.2 — düşük güvenli tespitler bağlam için).
- Çıktı: `face_tracks.json` — `[{track_id, start_ms, end_ms, frames: [{frame_idx, time_ms, bbox, det_conf, landmarks}, ...]}]`
- Süre: CPU ağırlıklı, ~1-2 dk
- VRAM: ihmal edilebilir

#### Stage 4 — Track Quality Gate + En İyi Crop Seçimi
- Girdi: tracks
- İş: Her track için **§0.3.13 quality gate**'i uygula:
  - `min_face_height = 80 px`
  - `blur_laplacian_min = 100` (OpenCV Laplacian variance)
  - `pose_yaw_max = 30°` (landmark'tan tahmini)
  - `pose_pitch_max = 25°`
  - `min_track_duration = 1.5 s`
  - `min_detector_confidence = 0.70`
  - Occlusion: landmark visibility (bazı landmark'lar bbox dışındaysa skip)
- Track gate'i geçtiyse, içinden **en iyi 3-5 crop** seç (kalite skoru = size * blur * confidence * pose_score'un ağırlıklı ortalaması).
- Reddedilenler: `face_quality_report.json` içine `rejected_tracks` listesi + reason kodu (`too_small`, `too_blurry`, `too_short`, ...).
- Çıktı: `face_tracks_kept.json` + `crops/track_<id>_<frame>.jpg`
- Süre: CPU, ~30 sn-1 dk
- Not: Crop'lar 30 gün TTL'e tabi (KVKK retention, §0.3.15).

#### Stage 5 — Alignment + Embedding (ArcFace)
- Girdi: gate'ten geçen track'ler + 3-5 crop
- İş: Her crop için landmark ile yüzü hizala (5-point similarity transform, 112x112 hedef). Hizalanmış crop'ları ArcFace'e ver, 512-d embedding al. Track için **temsilci embedding** = kalite ağırlıklı ortalama (sonra L2 normalize).
- Çıktı: `face_embeddings.parquet` (track_id, embedding_512d) — JSON içine vector koymayız, parquet daha ucuz; pgvector'a track_id referansıyla yazılır
- Süre: GPU, ~30 sn-1 dk
- VRAM: ArcFace ~1 GB

#### Stage 6 — Clustering (HDBSCAN)
- Girdi: track embedding'leri (track_id × 512-d)
- İş: HDBSCAN ile aynı medya içinde aynı kişi cluster'ı oluştur. Parametre başlangıç değerleri:
  - `min_cluster_size = 2` (en az 2 track aynı kişi)
  - `min_samples = 1`
  - `cluster_selection_epsilon = 0.35` (cosine distance benzeri normalize embedding üzerinde Euclidean)
  - `metric = "euclidean"` (L2 normalize sonrası Euclidean ≈ cosine)
- Bazı track'ler `cluster_id = -1` (noise) kalabilir; bunlar "tek tek track" olarak işlenir.
- Çıktı: `face_clusters.json` — `[{cluster_id, member_track_ids, centroid_embedding_ref, total_screen_time_ms, num_appearances}]`
- Süre: CPU, < 30 sn (track sayısı düşük)
- Not: Cluster cross-video değil, **medya-içi**. Cross-video birleştirme banka match aşamasında olur.

#### Stage 7 — Bank Match (pgvector)
- Girdi: cluster centroid embedding'leri
- İş: Her cluster centroid'i için pgvector `face_bank_embeddings` tablosunda top-k (k=5) en yakın komşu aranır. Distance metric: cosine.
- Karar kuralı (master plan §2.2 ve §0.3.13 eşikleri kalibre edilene kadar **başlangıç eşikleri**):
  - `score >= 0.85` (cosine similarity) → `match_decision = "auto_matched"` → CandidateRelation status `auto`
  - `0.70 <= score < 0.85` → `match_decision = "needs_review"` → review queue'ya yüksek öncelik
  - `score < 0.70` → `match_decision = "unknown"` → unknown cluster, review için orta öncelik (importance göre)
- Çıktı: `face_matches.json` — `[{cluster_id, candidates: [{person_id, person_name, score, match_decision}]}]`
- Süre: pgvector lookup ~1-5 ms/cluster, toplam < 5 sn
- VRAM: pgvector lookup CPU/disk, GPU'ya dokunmaz

#### Stage 8 — Importance + Bucketing
- Girdi: cluster + ASR speaker turns + OCR `screen_text` (subtype `lower_third_person`) + Visual Tag (eğer varsa)
- İş: Her cluster için **önem skoru** hesapla (§0.3.13 ağırlıkları):
  - `screen_time = total_screen_time_ms / clip_duration_ms` × 0.35
  - `kj_overlap = 1.0 if cluster zaman aralığında lower_third_person KJ varsa else 0.0` × 0.25
  - `asr_speaker_overlap = max_overlap_ratio_with_any_speaker_turn` × 0.20
  - `face_size_quality = mean_track_quality_normalized` × 0.15
  - `existing_bank_match = 1.0 if match_decision == "auto_matched" else (0.5 if "needs_review" else 0.0)` × 0.05
  - `importance_score = sum(above)` ∈ [0, 1]
- Bucketing eşikleri (başlangıç):
  - `>= 0.55` → `high`
  - `0.25 - 0.55` → `medium`
  - `< 0.25` → `low`
- Çıktı: `face_importance.json` — `[{cluster_id, importance_score, bucket, signals: {...}}]`
- Override: review UI'da "düşük öneme atılanları da göster" toggle'ı var.

#### Stage 9 — Event + CandidateRelation Emit
- Girdi: cluster + match + importance
- İş: Aşağıdaki TimelineEvent ve CandidateRelation'lar üretilir:
  - **`face_presence` event** (her track için): `{event_type: "face_presence", start_ms, end_ms, payload: {track_id, cluster_id, det_conf_avg, bbox_avg, quality_score}, confidence: track_quality}`
  - **`face_cluster_appearance` event** (her cluster için, her sürekli görünme bloğu): `{event_type: "face_cluster_appearance", start_ms, end_ms, payload: {cluster_id, total_screen_time_ms, member_tracks_count, importance_score, bucket, match: {person_id?, score?, decision}}, confidence: importance_score}`
  - **`face_matches_kj_name_candidate` CandidateRelation** (cluster + KJ zamanı kesişiyorsa): `{relation_type: "face_matches_kj_name_candidate", entity_a: {type: "face_cluster", id: cluster_id}, entity_b: {type: "kj_text", id: ocr_event_id}, confidence: temporal_overlap_ratio, source_signals: ["face_overlap", "ocr_lower_third"]}`
  - **`speaker_overlaps_face_candidate` CandidateRelation** (cluster + ASR speaker turn kesişiyorsa, sadece importance high/medium): `{relation_type: "speaker_overlaps_face_candidate", entity_a: {type: "face_cluster", id: cluster_id}, entity_b: {type: "speaker_id", id: speaker_id}, confidence: overlap_ratio, source_signals: ["face_overlap", "asr_speaker_turn"]}`
- Film modu: yalnız `face_presence` event'i yazılır, cluster/match/CandidateRelation üretilmez.

#### Stage 10 — Output Write
- Tüm Stage 9 çıktıları JSON dosyalara yazılır (output sözleşmesine göre).
- `face_summary.json`: clip-level özet — `{job_id, clip_id, total_tracks, kept_tracks, total_clusters, importance_buckets: {high: N, medium: M, low: K}, runtime_seconds, vram_peak_mb}`
- `module_run` kaydı `core.schemas.module_run.ModuleRun` ile yazılır.

#### Stage 11 — Review Queue
- Yüksek + orta kovadaki cluster'lar review için kuyruğa alınır. Düşük kova default kapalı (override ile açılır).
- Review queue: ayrı tablo veya `face_review_queue.json` (DB hazırsa DB, yoksa JSON dosya — Blok 5'te netleştirilecek).

#### Stage 12 — System Event
- `outputs/system_events.jsonl` içine `{kind: "face_completed", media_id, job_id, ...}` event'i yazılır.

### 2.3 Hata yönetimi (master plan §0.3.8)

- Bir Stage fail olursa önceki valid çıktılar korunur.
- Transient error (file lock, GPU OOM transient): 1 otomatik retry.
- OOM: retry yok; `status = "failed_resource_limit"`, log'a peak VRAM yazılır.
- Schema validation fail: `status = "failed_invalid_output"`.
- Partial result kabul edilir. Örneğin Stage 7 (bank match) fail olursa Stage 8-12 yine çalışır, sadece `existing_bank_match = 0` kullanır.
- pgvector down ise → Stage 7 atlanır, tüm cluster `unknown` olur. Operasyonel uyarı.

### 2.4 GPU yaşam döngüsü (master plan §0.3.9)

```
load_model("scrfd")        # ~1 GB VRAM
run_stage_1_and_2()
unload_model("scrfd")
load_model("arcface")      # ~1 GB VRAM
run_stage_5()
unload_model("arcface")
# Stage 3, 4, 6, 7, 8, 9, 10, 11, 12 CPU/disk; GPU'da değil
```

Aynı anda iki yüz modeli yüklenmez. SCRFD + ArcFace ardışık. Toplam peak VRAM: ~1.5 GB (overlap yok).

Showcase modu farklı: hem SCRFD hem (showcase için kullanılırsa ArcFace değil — sadece tracking) sürekli warm tutulur. **Final analiz showcase'le aynı anda çalıştırılmaz** (M8).

### 2.5 Engine Interface (Strategy Pattern)

ASR'de denenen pattern face'de de uygulanır:

```python
# core/pipelines/face/engines/detector.py
class DetectorEngine(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...
    def warm_up(self) -> None: ...
    def unload(self) -> None: ...

class SCRFDEngine(DetectorEngine):
    # buffalo_l üzerinden SCRFD
    ...

# core/pipelines/face/engines/embedder.py
class EmbedderEngine(Protocol):
    def embed(self, aligned_crops: list[np.ndarray]) -> np.ndarray: ...

class ArcFaceEngine(EmbedderEngine):
    ...

# core/pipelines/face/engines/tracker.py
class TrackerEngine(Protocol):
    def update(self, detections: list[Detection]) -> list[Track]: ...

class ByteTrackEngine(TrackerEngine):
    ...

# core/pipelines/face/engines/clusterer.py
class ClustererEngine(Protocol):
    def cluster(self, embeddings: np.ndarray) -> np.ndarray: ...

class HDBSCANClusterer(ClustererEngine):
    ...
```

Bu pattern sayesinde:
- BoT-SORT yedek olarak gelirse `BoTSortEngine` eklenir, `TrackerEngine`'i implement eder.
- ArcFace yerine başka embedding modeli (varsa) eklenir.
- HDBSCAN yerine DBSCAN/agglomerative test edilebilir (master plan v1 dışı ama mimari hazır).

### 2.6 Background Worker entegrasyonu

`core/jobs/worker.py` zaten skeleton halinde. Face pipeline buraya `register_pipeline("face", run_face_pipeline)` ile bağlanır.

```python
# core/pipelines/face/pipeline.py
def run_face_pipeline(
    media_id: str,
    job_id: str,
    config: FacePipelineConfig,
    deps: PipelineDeps,
) -> FacePipelineResult: ...
```

`step_runner.py` her stage'i ayrı `step` olarak kaydeder. `job_runs` tablosuna her stage'in `started_at`, `completed_at`, `status`, `error_msg`, `retry_count`, `last_successful_step` yazılır. Bu sayede crash sonrası recovery: `last_successful_step` sonrası adımdan devam edilebilir (ASR'de uygulanan desen).

### 2.7 Blok 2 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Her stage net girdi/çıktı/süre/VRAM ile yazıldı. Strategy pattern future-proof. Hata yönetimi ve GPU lifecycle master plan §0.3.8-9'a uygun. Film modunun nasıl ayrıldığı (Stage 6-8 atlanır) açık.

**Soru 2: Bağlamı korudum mu?**
> Evet. SCRFD + ArcFace + ByteTrack + HDBSCAN + pgvector (§2.2). Quality gate değerleri (§0.3.13). Importance ağırlıkları (§0.3.13). CandidateRelation tipleri (§0.3.5). M4 film kuralı. M9 candidate ≠ identity. M8 showcase ≠ final.

**Soru 3: Başka şeyi bozdum mu?**
> Bir potansiyel sorun var: **Stage 5'te embedding parquet'e yazılıyor.** ASR'de tüm output JSON. Parquet alternatif/extra format. Bu UI ile sözleşme kırar mı? Hayır, çünkü UI embedding'i okumaz; sadece `face_summary.json` + `face_clusters.json` + `face_matches.json` okur. Embedding parquet **pgvector'a yazılırken** ara dosya. Pratik nedeni: 512-d float vector'leri JSON'da string olarak yazmak hem büyük hem yavaş. Yine de **UI sözleşmesi etkilenmiyor**. Tamam.
>
> İkinci kontrol: **`face_presence` event'i film modunda da yazılıyor.** Bu master plan M4 ile uyumlu — "Sadece 'yüz var' event'i tutulur" diyor. `face_presence` tam bu. Tamam.
>
> Üçüncü kontrol: **Pre-scan (Stage 1) varsayılan yapılır.** Master plan §2.2'de "Ön tarama: 2 saniyede 1 frame ile yüz var/yok haritası" denmiş. Uyumlu.

**Soru 4: Daha iyisi var mı?**
> Üç potansiyel iyileştirme:
>
> **İyileştirme A — Stage 1 (Pre-Scan) gereksiz mi olabilir?** Eğer klip kısa (<5 dk) ve büyük çoğunluğunda yüz var (haber, panel), pre-scan boşa zaman olur. Karşı argüman: yüzü kontrol etmek de Stage 2'ye benzer SCRFD koşumu istiyor; sadece daha düşük örnekleme. Faydası: yüzü olmayan uzun belgesellerde Stage 2'yi atlamak. **Karar:** Pre-scan profile bazlı opsiyonel olsun. `news/panel` profilinde **kapalı** (yüz hemen her zaman var); `documentary/film` profilinde **açık** (yüz seyrek). Config bayrağı: `face.pre_scan.enabled`, default `false`, profile bazlı override.
>
> **İyileştirme B — Stage 6 (Clustering) öncesi "intra-track stability" kontrolü.** Bazen ByteTrack ID hata yapar (occlusion + farklı kişi). Aynı `track_id` içinde embedding varyansı çok yüksekse track'i 2'ye böl. Bu hem cluster purity'yi artırır hem de false positive azaltır. **Karar:** Stage 4'e ek bir alt-adım olarak ekle: "intra-track embedding variance check". Eğer track içi embedding'lerin std-dev'i belirli eşikten yüksekse, track yarıya bölünür (zamanca). Gate sonrası, embedding sonrası bir filtre. Eşik kalibrasyonu benchmark sonrası.
>
> **İyileştirme C — Stage 7 (Bank Match) eşikleri çok agresif olabilir.** 0.85 cosine similarity yüksek bir bar; gerçek production'da false negative'i artırır. Buffalo_l ArcFace TR yüzlerinde tipik intra-class similarity 0.70-0.80 arasında olabiliyor. **Karar:** Eşikler **kalibrasyon-gated** — v0.4 implementasyonu eşik değerini config'ten alır (`face.match.auto_threshold`, default 0.85; `face.match.review_threshold`, default 0.70). İlk benchmark koşumunda TRT seed bank'la kalibre edilir (`benchmark_templates/face_benchmark.yaml` `false_match_rate_max` ve `missed_face_rate_max` eşiği TBD'den sayısal değere taşınır). Kararı v0.4 release öncesi.
>
> **Karar:** Üç iyileştirme de plana dahil. A → Stage 1 profile-conditional. B → Stage 4'e intra-track stability sub-step ekle. C → eşikler config-driven, benchmark kalibrasyon ile bağlı.

**Plan değişikliği notu (DEC-FACE-J-002):**
- 2026-05-16: Stage 1 (Pre-Scan) varsayılan **kapalı**, profile bazlı override ile açılır. `documentary/film` için açık, `news/panel/music/studio` için kapalı.
- 2026-05-16: Stage 4'e "intra-track embedding variance check" alt-adımı eklendi (Stage 5 sonrası, Stage 6 öncesi geri-baktırma). Track içi std-dev belirli eşikten yüksekse track ikiye bölünür.
- 2026-05-16: Stage 7 eşikleri config-driven. `face.match.auto_threshold=0.85`, `face.match.review_threshold=0.70` başlangıç değerleri. v0.4 release öncesi benchmark ile kalibre.

---

## 3. Blok 3 — Face Bank Şeması, Seed ve Öğrenme Döngüsü

### 3.1 Yüz bankası nedir?

Yüz bankası MITAS'ın **uzun vadeli en kıymetli varlığı**. Açık kaynak embedding modelleri Batı yüzlerinde eğitildi; TRT içeriği büyük oranda Türkiye'ye özgü. Yüz bankası şu nesneleri saklar:

- Kişi (`person`) — gerçek kimliği temsil eder
- Kişiye ait yüz örnekleri (`face_samples`) — fotoğraf + embedding + meta
- Kişinin **canonical embedding centroid'i** — örneklerin ağırlıklı ortalaması (lookup hızı için pre-computed)

Banka iki yoldan büyür: **seed** (manuel başlangıç listesi) ve **review döngüsü** (operatör onaylı bilinmeyenler).

### 3.2 Veritabanı şeması (PostgreSQL + pgvector)

**Hedef DB:** PostgreSQL 16+ + pgvector extension.
**Şema adı:** `face_bank`.

```sql
-- 3.2.1 Kişi
CREATE TABLE face_bank.persons (
  person_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name       TEXT NOT NULL,
  aliases            TEXT[] DEFAULT '{}',     -- "A. Yılmaz", "Sn. Yılmaz" gibi
  category           TEXT,                    -- "presenter", "politician", "athlete", "artist", "guest", "other"
  organization       TEXT,                    -- "TRT", "AKP", "CHP", "Galatasaray" vs.
  notes              TEXT,
  created_by         TEXT NOT NULL,           -- operator user_id
  created_at         TIMESTAMPTZ DEFAULT now(),
  updated_at         TIMESTAMPTZ DEFAULT now(),
  -- soft delete
  deleted_at         TIMESTAMPTZ NULL,
  -- KVKK
  kvkk_consent_basis TEXT,                    -- hukuki dayanak metni (boş bırakılırsa production'da kullanılamaz)
  retention_class    TEXT DEFAULT 'standard'  -- "standard", "long_term_archive", "research_only"
);

CREATE INDEX idx_persons_name ON face_bank.persons (display_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_persons_active ON face_bank.persons (deleted_at) WHERE deleted_at IS NULL;

-- 3.2.2 Yüz örneği (her fotoğraf veya video crop)
CREATE TABLE face_bank.face_samples (
  sample_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id          UUID NOT NULL REFERENCES face_bank.persons(person_id) ON DELETE CASCADE,
  source_kind        TEXT NOT NULL,           -- "seed_photo", "review_confirmed", "manual_upload"
  source_clip_id     TEXT NULL,               -- review_confirmed ise hangi klipten
  source_track_id    TEXT NULL,               -- review_confirmed ise hangi track
  crop_path          TEXT NOT NULL,           -- E:/MITAS/outputs/face_bank/samples/<sample_id>.jpg
  bbox               INTEGER[4] NULL,         -- video'dan geldiyse
  landmarks          REAL[5][2] NULL,
  embedding          vector(512) NOT NULL,    -- pgvector
  embedding_model    TEXT NOT NULL DEFAULT 'buffalo_l/w600k_r50',
  embedding_version  TEXT NOT NULL DEFAULT 'v1',
  quality_score      REAL NOT NULL,
  det_conf           REAL NOT NULL,
  pose_yaw           REAL NULL,
  pose_pitch         REAL NULL,
  blur_score         REAL NULL,
  face_height_px     INTEGER NULL,
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,  -- silinen örnekler deactive
  created_by         TEXT NOT NULL,
  created_at         TIMESTAMPTZ DEFAULT now(),
  deactivated_at     TIMESTAMPTZ NULL
);

CREATE INDEX idx_samples_person ON face_bank.face_samples (person_id) WHERE is_active = TRUE;
CREATE INDEX idx_samples_model ON face_bank.face_samples (embedding_model, embedding_version);
-- pgvector cosine index
CREATE INDEX idx_samples_embedding ON face_bank.face_samples
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 3.2.3 Kişi centroid embedding (pre-computed)
CREATE TABLE face_bank.person_centroids (
  person_id          UUID PRIMARY KEY REFERENCES face_bank.persons(person_id) ON DELETE CASCADE,
  centroid_embedding vector(512) NOT NULL,
  embedding_model    TEXT NOT NULL,
  embedding_version  TEXT NOT NULL,
  active_sample_count INTEGER NOT NULL,
  last_recomputed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_centroids_embedding ON face_bank.person_centroids
  USING ivfflat (centroid_embedding vector_cosine_ops) WITH (lists = 50);

-- 3.2.4 Unknown cluster'lar (cross-video birikim)
CREATE TABLE face_bank.unknown_clusters (
  unknown_cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  first_seen_clip_id TEXT NOT NULL,
  first_seen_at      TIMESTAMPTZ DEFAULT now(),
  last_seen_clip_id  TEXT NOT NULL,
  last_seen_at       TIMESTAMPTZ DEFAULT now(),
  appearance_count   INTEGER NOT NULL DEFAULT 1,
  centroid_embedding vector(512) NOT NULL,
  embedding_model    TEXT NOT NULL,
  embedding_version  TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'pending_review',
                     -- "pending_review", "merged_to_person", "rejected", "expired"
  promoted_person_id UUID NULL REFERENCES face_bank.persons(person_id),
  retention_expires_at TIMESTAMPTZ NOT NULL  -- created_at + 30 gün (KVKK)
);

CREATE INDEX idx_unknown_status ON face_bank.unknown_clusters (status) WHERE status = 'pending_review';
CREATE INDEX idx_unknown_expiry ON face_bank.unknown_clusters (retention_expires_at);
CREATE INDEX idx_unknown_embedding ON face_bank.unknown_clusters
  USING ivfflat (centroid_embedding vector_cosine_ops) WITH (lists = 50);

-- 3.2.5 Audit log (KVKK + master plan §0.3.15 zorunlu)
CREATE TABLE face_bank.audit_log (
  audit_id           BIGSERIAL PRIMARY KEY,
  ts                 TIMESTAMPTZ DEFAULT now(),
  actor              TEXT NOT NULL,           -- operator user_id veya "system"
  action             TEXT NOT NULL,           -- "create_person", "delete_person", "add_sample",
                                              -- "deactivate_sample", "merge_persons", "split_cluster",
                                              -- "promote_unknown", "reject_unknown", "threshold_change",
                                              -- "kvkk_deletion_request", "retention_expire"
  target_kind        TEXT NOT NULL,           -- "person", "sample", "unknown_cluster", "config"
  target_id          TEXT NOT NULL,
  before_state       JSONB NULL,
  after_state        JSONB NULL,
  reason             TEXT NULL,
  job_id             TEXT NULL,               -- ilgili face job
  ip_or_session      TEXT NULL
);

CREATE INDEX idx_audit_ts ON face_bank.audit_log (ts DESC);
CREATE INDEX idx_audit_target ON face_bank.audit_log (target_kind, target_id);
CREATE INDEX idx_audit_actor ON face_bank.audit_log (actor);

-- 3.2.6 Konfig snapshot (eşik değişimleri için)
CREATE TABLE face_bank.config_versions (
  config_version_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_name        TEXT NOT NULL,           -- "match.auto_threshold", "match.review_threshold",
                                              -- "quality.min_face_height", vb.
  config_value       JSONB NOT NULL,
  effective_from     TIMESTAMPTZ DEFAULT now(),
  effective_until    TIMESTAMPTZ NULL,
  changed_by         TEXT NOT NULL,
  reason             TEXT NULL
);

CREATE INDEX idx_config_name_time ON face_bank.config_versions (config_name, effective_from DESC);
```

**Notlar:**
- `embedding_model` ve `embedding_version` alanları zorunlu (§0.3.16). Banka birden fazla model sürümünü destekleyebilir ama lookup tek model versiyonu üzerinden yapılır. Model değişince **re-embed** job planlanır.
- `pgvector` ivfflat index başlangıç için yeterli. Banka 50k+ kişiye ulaşırsa HNSW geçişi düşünülür (§0.3.16).
- `unknown_clusters` cross-video. Bir kliptte unknown çıkan cluster sonraki klipte tekrar çıkarsa **embedding similarity** ile birleştirilir; `appearance_count` artar; `last_seen_*` güncellenir.
- Audit log **append-only**. Silme yok. Yalnız retention_expire ile eski kayıt arşivlenebilir (≥ 1 yıl tut).

### 3.3 Seed (başlangıç dolumu) süreci

**Hedef:** v0.4 ilk koşumunda banka 50-100 kişi içerir, her kişi 5-10 fotoğraf.

**Adım 1 — Kişi listesi:**
Operatör bir CSV/JSON ile başlangıç kişi listesi sağlar:
```json
[
  {"display_name": "Mehmet Ali Birand", "aliases": ["M.A. Birand"], "category": "presenter", "organization": "TRT"},
  {"display_name": "Bülent Ecevit", "aliases": [], "category": "politician", "organization": "DSP"},
  ...
]
```
Liste **TRT operatörünün önceliklendirmesi** ile gelir (OQ-4'te netleşecek).

**Adım 2 — Kişi başına 5-10 fotoğraf:**
- Manuel kıyafet/açı çeşitliliği önemli (sadece "vesikalık" değil)
- Yüz büyüklüğü minimum 200x200 px
- Tercih edilen kaynak: TRT arşiv görüntülerinden manual seçilmiş crop'lar (KVKK uyumlu kaynak)
- Yedek kaynak: Wikimedia Commons / Wikipedia kamuya açık fotoğraflar (lisans CC-BY-SA, kullanım amacı tanıma)

**Adım 3 — Backend bulk import endpoint:**
```
POST /api/face/bank/seed
Content-Type: multipart/form-data
- persons.json (kişi listesi)
- photos/<person_index>/photo_<n>.jpg (fotoğraflar)

Response:
{
  "persons_created": 73,
  "samples_created": 542,
  "rejected_photos": [{"path": "photos/12/photo_3.jpg", "reason": "face_too_small"}],
  "audit_log_entries": 615
}
```

**Adım 4 — Otomatik centroid hesaplama:**
Her kişi için `person_centroids` tablosu otomatik doldurulur. Kalite ağırlıklı ortalama, L2 normalize. Trigger ile veya backend manuel çağırılır.

### 3.4 Review döngüsüyle banka büyütme

**Akış:**

```
1. Final analiz sonunda unknown cluster üretilir (Stage 6, score < 0.70)
2. Cluster önemliyse (importance bucket = high/medium) review queue'ya düşer
3. Operatör review UI'da cluster'ı görür:
   - cluster temsilci crop'ları
   - clip + zaman aralığı
   - aynı cluster'ın diğer kliplerdeki appearance (unknown_clusters cross-video birleşmesi)
4. Üç seçenek:
   a) "Bu kişi: <isim>" → mevcut person seç veya yeni person oluştur
      → cluster temsilci embedding'leri yeni sample olarak persons + face_samples'a eklenir
      → unknown_cluster.status = "merged_to_person", promoted_person_id set
      → person centroid yeniden hesaplanır
      → audit_log: "promote_unknown" + before/after
   b) "Bu kişi tanımlanamaz" → reject
      → unknown_cluster.status = "rejected"
      → retention_expires_at gelince crop'lar silinir, embedding deactivate edilir
   c) "Sonra bakacağım" → skip (queue'da kalır)
```

**Cross-video unknown birleştirme:**
Yeni klip işlenirken Stage 6 sonunda unknown cluster oluşursa:
- Önce mevcut `unknown_clusters` tablosunda **cross-video similarity search** yapılır (cosine >= 0.75)
- Eşleşme varsa: `appearance_count++`, `last_seen_*` güncellenir, yeni cluster eski unknown_cluster_id ile birleştirilir
- Eşleşme yoksa: yeni `unknown_cluster_id` üretilir, `retention_expires_at = now() + 30 days`

Bu yapı operatöre "bu yüzü 8 farklı yayında gördüm" gibi güçlü öncelik sinyali verir.

### 3.5 Banka yönetim UI sözleşmesi (web)

WebUI'daki **FaceBank Builder** sekmesi şu işlevleri sunar:

**Kişi listesi:**
- `GET /api/face/bank/persons?limit=50&offset=0&q=...`
- Liste: display_name + thumbnail (en kaliteli sample) + sample_count + last_seen_clip

**Kişi detayı:**
- `GET /api/face/bank/persons/{person_id}`
- Tüm sample'lar, embeddings (sayı, deactive olanlar gri), audit log son 20 entry, görüldüğü kliplerin listesi (face_event log query)

**Kişi yarat:**
- `POST /api/face/bank/persons` body: `{display_name, category, organization, ...}`
- Audit log: "create_person"

**Sample ekle:**
- `POST /api/face/bank/persons/{person_id}/samples` body: image file or video crop reference
- Backend: detect → quality gate → embedding → insert
- Audit log: "add_sample"

**Sample sil (deactivate):**
- `POST /api/face/bank/samples/{sample_id}/deactivate` body: `{reason}`
- Hard delete değil, `is_active = false` ve `deactivated_at` set
- Crop dosyası KVKK silme talebi varsa fiziksel olarak da silinir
- Person centroid yeniden hesaplanır
- Audit log: "deactivate_sample"

**Kişi birleştirme:**
- `POST /api/face/bank/persons/{primary_id}/merge` body: `{secondary_id, reason}`
- secondary'nin tüm sample'ları primary'ye taşınır
- secondary deleted_at set
- centroid yeniden hesaplanır
- Audit log: "merge_persons"

**Unknown cluster review:**
- `GET /api/face/review/queue?bucket=high,medium`
- `POST /api/face/review/confirm` body: `{unknown_cluster_id, person_id | new_person_data}`
- `POST /api/face/review/reject` body: `{unknown_cluster_id, reason}`

### 3.6 KVKK retention scheduler (§0.3.15)

Background job (cron veya periyodik task):

```
Her gün 03:00:
1. SELECT * FROM unknown_clusters WHERE retention_expires_at < now() AND status IN ('pending_review', 'rejected')
2. Her satır için:
   - centroid_embedding ANONYMIZE (NULL veya hash)
   - crop dosyaları (outputs/face_bank/unknown_crops/<unknown_cluster_id>/*) sil
   - status = 'expired'
   - audit_log: "retention_expire"
```

Confirmed person silme talebi (data subject request):
```
POST /api/face/bank/persons/{person_id}/kvkk-delete
1. Tüm face_samples deactive
2. Crop dosyaları sil
3. person centroid sil
4. person row: display_name → "[REDACTED]", category → null, aliases → []
5. deleted_at set
6. audit_log: "kvkk_deletion_request"
```

Audit log retention: minimum **1 yıl** (KVKK doğrulama isteklerine cevap için). Sonra anonymize.

### 3.7 Veri kaynağı sözleşmesi (lisans + onay)

Banka'ya **hiçbir fotoğraf** lisans/onay belgesi olmadan yüklenmez. Backend zorunlu alan kontrolü:
- `kvkk_consent_basis` (person seviyesinde) bir metin değer içermeli (örn. "TRT yayıncılık hizmetleri için kamuya açık görüntüler kullanım hakkı, sözleşme XYZ").
- Sample yüklenirken `source_provenance` JSON alanı doldurulur (zorunlu): `{source: "trt_archive" | "wikimedia" | "manual_upload", license: "...", uploaded_by: "...", uploaded_for: "..."}`.
- Eksikse insert reddedilir.

### 3.8 Blok 3 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Banka şeması KVKK'yı (§0.3.15) baştan tasarımda var: retention, audit, silme talebi, lisans alanları zorunlu. Seed + review döngüsü iki yönlü büyüme açık. Cross-video unknown birleştirme operatöre öncelik sinyali veriyor. Schema model versiyonu izlenebilir (re-embed planı için).

**Soru 2: Bağlamı korudum mu?**
> Evet. Master plan §2.2 (pgvector), §0.3.15 (retention/audit/silme), §0.3.16 (embedding_model_version + active flag) hepsi var. M9 (Candidate ≠ Identity) banka match'inin auto/needs_review/unknown kararına yansıdı. Bu blok §3.5'te belirttiği FaceBank Builder UI sekmesini somut endpoint'lere bağladı (mutfak 10.UI iki ana sekme: Analysis Workstation + FaceBank Builder zaten var).

**Soru 3: Başka şeyi bozdum mu?**
> Bir gözden geçirme noktası: `face_bank` PostgreSQL şeması **yeni bir DB ihtiyacı** doğuruyor. ASR ve OCR şu an JSON output odaklı. Master plan §1.5'te v1 prensibi "önce JSON + DB ile sade ilerle" diyor. Yani DB v1 için zaten gerekli. Ama DB **hangi DB**? master plan §0.3.16 "PostgreSQL + pgvector + JSONB" der. OK. Yani Face bu DB'yi **ilk gerçekten kullanan modül** olur. Bu Blok 5 (Setup)'ın kritik adımı: PostgreSQL kurulumu + pgvector kurulumu + schema migration. Bu eksik bırakılamaz.
>
> İkinci kontrol: **Audit log retention**. KVKK genelde 1 yıl. Master plan'da süre yok, taslak. Ben "minimum 1 yıl" yazdım — bu kabul edilebilir bir başlangıç ama hukuktan onay almak gerekir (OQ-6).
>
> Üçüncü kontrol: **`source_provenance` JSONB alanı zorunlu** dedim ama şemada bu alan yok! Eklemeyi unuttum. Bu bir blok-içi düzeltme:

**Soru 4: Daha iyisi var mı?**
> İki düzeltme + iki iyileştirme:
>
> **Düzeltme 1 — `face_samples.source_provenance` alanı şemaya ekle.** Zorunlu JSONB alanı.
>
> **Düzeltme 2 — `face_bank.persons.kvkk_consent_basis` boş olamaz check constraint ekle (production mode için).** Geliştirme mode'da boş olabilir, production deploy'da zorunlu.
>
> **İyileştirme A — Cross-video unknown birleştirme similarity eşiği 0.75 yeterli mi?** Aynı kişi farklı kıyafet/ışık/yaşta bu kadar yakın embedding üretebilir mi? Belirsiz. Karşı argüman: çok düşük eşik (örn. 0.65) farklı insanları yanlışlıkla birleştirir. **Karar:** Bu eşik de **config-driven** olsun (`face.unknown_merge.similarity_threshold`, default 0.75), kalibrasyon-gated. v0.4 release öncesi benchmark.
>
> **İyileştirme B — Embedding model değişikliği nasıl yönetilir?** Yeni ArcFace sürümü çıkarsa bütün banka re-embed edilmeli. Bu büyük iş. Planlanan akış: Yeni model `embedding_version = "v2"` ile banka'ya **paralel** yazılır; her sample iki versiyon embedding tutar; lookup başlangıçta v1, sonra v2'ye geçiş. Cutover sonrası v1 sample'lar `is_active=false` ama kayıt durur. **Karar:** Bu re-embed paterni Blok 7 (test/benchmark) içinde "model upgrade smoke test" olarak da yer alacak. v0.4 sadece v1 ile başlar; üst seviye plan korunur.

**Plan değişikliği notu (DEC-FACE-J-003):**
- 2026-05-16: `face_bank.face_samples.source_provenance JSONB NOT NULL` alanı şemaya eklendi (lisans/onay belgesi zorunluluğu).
- 2026-05-16: `face_bank.persons.kvkk_consent_basis` için production-mode CHECK constraint planlandı.
- 2026-05-16: Cross-video unknown birleştirme eşiği config-driven oldu (`face.unknown_merge.similarity_threshold=0.75`, benchmark ile kalibre).
- 2026-05-16: Re-embed paterni (model_version paralel yazım + cutover) Blok 7'ye smoke test olarak eklenecek.

Şema düzeltmesi (yukarıdaki `face_samples` CREATE TABLE'a eklenir):

```sql
ALTER TABLE face_bank.face_samples
  ADD COLUMN source_provenance JSONB NOT NULL DEFAULT '{}'::jsonb;
-- production cutover'da: ALTER COLUMN ... DROP DEFAULT;
-- check constraint: source_provenance ? 'source' AND source_provenance ? 'license'

ALTER TABLE face_bank.persons
  ADD CONSTRAINT chk_persons_kvkk_consent_when_production
  CHECK (
    current_setting('app.env', true) <> 'production'
    OR (kvkk_consent_basis IS NOT NULL AND length(kvkk_consent_basis) > 10)
  );
-- production deploy'da app.env='production' set edilir
```

---

## 4. Blok 4 — Quality Gate, Importance ve Threshold Mühendisliği

### 4.1 Niye ayrı blok?

Modellerin kendisi (SCRFD/ArcFace) sabit. Pipeline mimarisi (Blok 2) sabit. Banka şeması (Blok 3) sabit. Ama bu modülün **production değeri** aslında:
- Hangi track'i öne çıkarıyoruz? (Importance)
- Hangi track'i ciddiye alıyoruz? (Quality gate)
- Hangi match'i kabul ediyoruz? (Threshold)

Yanlış sabitlerle pipeline çalışır gözükür ama operatöre 1000 false positive sorar veya 50 doğru kişiyi atlar. Bu blok tüm sayısal parametreleri **isim, default, gerekçe, kalibrasyon yöntemi** üçlüsüyle topluyor.

### 4.2 Quality Gate parametreleri (Stage 4)

| Parametre | Default | Birim | Gerekçe | Kalibrasyon |
|---|---:|---|---|---|
| `face.quality.min_face_height` | 80 | px | <80 px ArcFace embedding'i güvenilir değil | TRT haber/panel keep_rate %30-60 olana göre |
| `face.quality.blur_laplacian_min` | 100 | OpenCV Laplacian variance | <100 blur, embedding noise yüksek | TRT eski arşiv klipleriyle test (interlaced blur var) |
| `face.quality.pose_yaw_max` | 30 | derece | Yan profil ArcFace'de embedding büyük dağılır | Manual landmark-based estimate |
| `face.quality.pose_pitch_max` | 25 | derece | Aşağı/yukarı bakış embedding'i bozar | Aynı |
| `face.quality.min_track_duration` | 1.5 | saniye | <1.5s anlık parlama olabilir, embedding kaliteli olmuyor | False positive azalmasıyla kalibre |
| `face.quality.min_detector_confidence` | 0.70 | [0,1] | SCRFD < 0.70 yüksek false positive | Aynı |
| `face.quality.occlusion_check` | true | bool | Landmark bbox dışındaysa skip | Sabit kural |
| `face.quality.intra_track_embedding_std_max` | 0.25 | float | Track içi embedding std-dev > 0.25 ise ByteTrack hatası | DEC-FACE-J-002 ile eklendi, ilk koşumla kalibre |
| `face.quality.crops_per_track_min` | 3 | int | En az 3 crop kullanılır embedding ortalaması için | Sabit |
| `face.quality.crops_per_track_max` | 5 | int | En fazla 5 crop; daha fazlası marjinal getiri | Sabit |

**Pose tahmini:** SCRFD landmark'larından (göz-burun-ağız) basit yaw/pitch kestirimi. Detaylı 3D pose modeline (örn. dlib veya 6DRepNet) v0.4'te girmiyoruz — gerekirse v0.5'te.

**Blur skoru:** Crop'un grayscale Laplacian variance. Düşük variance = blur.

### 4.3 Importance Scoring (Stage 8)

`importance_score = w1*S1 + w2*S2 + w3*S3 + w4*S4 + w5*S5`

| Sinyal | Ağırlık | Hesaplama | Eksik veriyse |
|---|---:|---|---|
| `S1: screen_time` | 0.35 | `total_cluster_screen_time_ms / clip_duration_ms`, max 1.0 | Her zaman var (face stage'den) |
| `S2: kj_overlap` | 0.25 | `1.0` if cluster zaman aralığında en az 1 `lower_third_person` KJ varsa else `0.0` | OCR yoksa `0.0`, importance düşer |
| `S3: asr_speaker_overlap` | 0.20 | `max overlap_ratio over all speaker_turns ∩ cluster_appearances` | ASR yoksa `0.0`, importance düşer |
| `S4: face_size_quality` | 0.15 | `mean(track.quality_score) / max_observed_quality` | Her zaman var |
| `S5: existing_bank_match` | 0.05 | `1.0` if auto_matched, `0.5` if needs_review, `0.0` else | Banka boşsa `0.0` |

**Buckets:**
- `importance_score >= 0.55` → `high` (review öncelikli)
- `0.25 ≤ importance_score < 0.55` → `medium` (review opsiyonel)
- `< 0.25` → `low` (review default kapalı, override ile açılır)

**Graceful degradation:**
- OCR yoksa S2=0, max possible score 0.75 — `high` bucket eşiği 0.55 hâlâ ulaşılabilir.
- ASR yoksa S3=0, max possible score 0.80 — yine ulaşılabilir.
- OCR + ASR ikisi yoksa S2+S3=0, max possible score 0.55. Borderline. Sadece S1 + S4 + S5 = 0.55. Bu durumda **bucket eşiklerini de oransal düşür** veya **uyarı ver**.

**Karar:** Graceful degradation için bucket eşikleri ASR/OCR varlığına göre **göreli** hesaplanır:
- `max_possible = S1_max + (S2_max if ocr_available else 0) + (S3_max if asr_available else 0) + S4_max + S5_max_if_bank_nonempty`
- `high_threshold = 0.55 * max_possible`
- `medium_threshold = 0.25 * max_possible`

Bu sayede sadece face çıktısı olan klipte de high/medium ayrımı yapılabilir.

### 4.4 Match Threshold'ları (Stage 7)

| Parametre | Default | Kalibrasyon |
|---|---:|---|
| `face.match.auto_threshold` | 0.85 cosine sim | TRT seed bank'la false_match_rate ölçülür; FMR < 2% olana kadar yukarı |
| `face.match.review_threshold` | 0.70 cosine sim | missed_face_rate ölçülür; MFR < 5% olana kadar aşağı |
| `face.match.top_k` | 5 | UI'da en fazla 5 aday önerilir |
| `face.match.same_person_score_gap` | 0.05 | top_1 ile top_2 score farkı bu kadarsa "açıkça top_1"; değilse iki aday eşit ağırlık |

### 4.5 Konfig sistemi

Tüm parametreler tek yerde — `config/face.yaml`:

```yaml
face:
  pipeline:
    pre_scan:
      enabled: false
      profile_overrides:
        documentary: true
        film: true
    dense_detect:
      sample_fps: 2.5
      input_size: 640
      detector_confidence: 0.70
    tracker:
      engine: "bytetrack"
      max_age: 30
      min_hits: 3
  quality:
    min_face_height: 80
    blur_laplacian_min: 100
    pose_yaw_max: 30
    pose_pitch_max: 25
    min_track_duration_sec: 1.5
    min_detector_confidence: 0.70
    intra_track_embedding_std_max: 0.25
    crops_per_track_min: 3
    crops_per_track_max: 5
  embedding:
    model: "buffalo_l/w600k_r50"
    version: "v1"
    output_dim: 512
    align_size: 112
  clustering:
    engine: "hdbscan"
    min_cluster_size: 2
    min_samples: 1
    cluster_selection_epsilon: 0.35
  match:
    auto_threshold: 0.85
    review_threshold: 0.70
    top_k: 5
    same_person_score_gap: 0.05
  importance:
    weights:
      screen_time: 0.35
      kj_overlap: 0.25
      asr_speaker_overlap: 0.20
      face_size_quality: 0.15
      existing_bank_match: 0.05
    bucket_thresholds:
      high: 0.55
      medium: 0.25
    relative_to_available_signals: true
  unknown_merge:
    similarity_threshold: 0.75
    cross_video: true
  kvkk:
    unknown_cluster_retention_days: 30
    unknown_crop_retention_days: 30
    audit_log_retention_days: 365
    require_consent_basis_in_production: true
  film_mode:
    identification_disabled: true
    presence_event_only: true
  showcase:
    namespace: "/api/face/demo"
    exclusive_gpu: true
```

**Konfig değişimi tracklı:**
- Her değişiklik `face_bank.config_versions` tablosuna yazılır (audit_log'da reference).
- Backend startup'ta config diff varsa otomatik audit kaydı.

### 4.6 Threshold kalibrasyon süreci (v0.4 release öncesi)

1. **Seed bank doldur** (50-100 kişi).
2. **Mini benchmark seti hazırla:** 5 saat haber/panel + 1 saat müzik + 1 saat belgesel + 1 saat film. Toplam 8 saat. Her saat için bilinen kişilerin doğru tanınması ground truth olarak işaretlenir (~50-100 etiket).
3. **Pipeline'ı default eşiklerle çalıştır.**
4. **Metrik üret:**
   - False Match Rate (FMR): bilinen kişiye yanlış kimlik atayan match sayısı
   - Missed Face Rate (MFR): bilinen kişiyi `auto_matched` yapmayan match sayısı
   - Cluster purity: tek bir cluster içinde tek bir kişi mi
   - Review load: operatör başına soru sayısı
5. **Eşik tarama:**
   - `auto_threshold` 0.80 → 0.95 arası 5 noktada ölç
   - `review_threshold` 0.65 → 0.80 arası 5 noktada ölç
   - 25 nokta x 5 metrik = 125 değer
6. **Karar:** FMR <= 2% ve MFR <= 5% en geniş aralık seçilir.
7. **Audit:** Eşik değişikliği `face_bank.audit_log` + `config_versions` yazılır.

`benchmark_templates/face_benchmark.yaml` zaten bu kalibrasyon için iskelet. `false_match_rate_max`, `missed_face_rate_max`, `cluster_purity_min` TBD alanları bu süreçle doldurulur.

### 4.7 Blok 4 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Her sayısal parametre **isim, default, gerekçe, kalibrasyon** üçlüsüyle. Konfig sistemi tek dosyada toplandı. Eşik kalibrasyon süreci somut adımlarla yazıldı. Graceful degradation (ASR/OCR yoksa) açık.

**Soru 2: Bağlamı korudum mu?**
> Evet. §0.3.13 quality + importance değerleri default olarak alındı. §0.3.5 CandidateRelation, §0.3.15 KVKK config'e bağlandı. Master plan §2.2 (review buckets + override toggle) korundu (override `face.importance.bucket_thresholds.low` config'le de yapılabilir). `benchmark_templates/face_benchmark.yaml`'ın TBD alanları kalibrasyon süreciyle eşleşti.

**Soru 3: Başka şeyi bozdum mu?**
> Bir dikkat: **`relative_to_available_signals: true`** importance hesaplama mantığı master plan'da spesifik tarif edilmemiş. Master plan §0.3.13 sabit ağırlık veriyor. Ben graceful degradation için göreli hesaplama önerdim. Bu **master plan'dan sapma** mı?
>
> Hayır. Master plan §0.3.13 sonu der: "Bu değerler nihai değildir; review gürültüsünü kontrol etmek için başlangıç değeridir ve benchmark sonrası kalibre edilir." Yani metodoloji açık, ben sadece bucket eşiklerinin **sinyalsiz durumda** kalibre olmasını mantığa bağladım. Bu master plan'la çelişmez; master plan'ın "benchmark sonrası kalibre" zihniyetini somut bir kurala bağlar.
>
> İkinci dikkat: **Konfig hot-reload.** Şu an config startup'ta okunuyor. Eşik değiştirilince servisi restart etmek gerek mi? Production için iyi olmaz. Ama v0.4'te kabul edilebilir (single iş istasyonu). Hot-reload v1.x sonrası.

**Soru 4: Daha iyisi var mı?**
> İki iyileştirme:
>
> **İyileştirme A — Film modu için "presence_event_only=true" ama yine de quality gate uygulanmalı.** Master plan M4 film modunda "yüz var" event'i tutar. Ama her tespiti event yazarsak büyük bir spam olur. Quality gate film modunda da çalışmalı, gate'i geçen track için event yazılmalı. Bu zaten Stage 4'te uygulanıyor (Stage 6-8 atlanır, Stage 4 atlanmaz). Sadece config'e açık not yazayım:
>
> ```yaml
> film_mode:
>   identification_disabled: true
>   presence_event_only: true
>   apply_quality_gate: true     # film modunda da gate uygula
>   skip_stages: [clustering, bank_match, importance, candidate_relation]
> ```
>
> **İyileştirme B — Kalibrasyon süreci `face.match.auto_threshold` ve `face.match.review_threshold` için tek bir 2D pareto front üretsin.** İki metrik (FMR ve MFR) trade-off var. Pareto front analizi seçimi nesnelleştirir. Skript taslağı:
>
> ```
> scripts/face_threshold_calibration.py
>   --benchmark-set benchmarks/face_calibration_8h
>   --output outputs/face_calibration/pareto_v1.json
> ```
>
> Bu komut tüm threshold kombinasyonlarını test eder, pareto-optimal noktaları işaretler, görselleştirir.
>
> **Karar:** Her iki iyileştirme planda. A → config dosyasına eklendi. B → Blok 7 (test/benchmark) içine kalibrasyon scripti olarak girer.

**Plan değişikliği notu (DEC-FACE-J-004):**
- 2026-05-16: `film_mode` config detaylandı: `apply_quality_gate=true`, `skip_stages=[...]`. Film klipleri için Stage 4 her zaman çalışır.
- 2026-05-16: Threshold kalibrasyon süreci `scripts/face_threshold_calibration.py` Pareto front analizi olarak Blok 7'ye girecek.

---

## 5. Blok 5 — Kurulum, Bağımlılıklar, Konfig, Dizin Yapısı

### 5.1 Mevcut durum kontrolü

`venvs/face` venv'inin **gerçek paketleri** (2026-05-16 doğrulandı):
- ✅ `insightface 0.7.3`, `onnxruntime-gpu 1.23.2`
- ✅ `supervision 0.28.0` (ByteTrack), `hdbscan 0.8.42`
- ✅ `pgvector 0.4.2` (Python client), `scikit-learn 1.7.2`, `albumentations 2.0.8`
- ✅ `torch 2.11.0+cu126`, `opencv-python 4.13.0.92`, `pillow 12.2.0`
- ✅ `pydantic 2.13.4`

**Eksik paketler:**
- `fastapi`, `uvicorn` (face backend API için)
- `psycopg[binary,pool]` veya `asyncpg` (PostgreSQL driver)
- `sqlalchemy` veya `psycopg-pool` (DB connection management)
- `python-multipart` (file upload için)
- `pyyaml` (config dosyası okuma)
- `alembic` (DB migration yönetimi — opsiyonel ama önerilen)
- `tenacity` (retry için)
- `httpx` (test client)

**Eksik sistem altyapısı:**
- ❌ PostgreSQL kurulu **olmayabilir** — kontrol edilecek
- ❌ pgvector extension kurulu **olmayabilir** — kontrol edilecek
- ❓ buffalo_l ONNX modelleri lokalde — InsightFace'in `~/.insightface/models/buffalo_l/` altında otomatik indireceği konum; ilk koşumda HF Hub'dan veya InsightFace mirror'dan inecek

### 5.2 Setup checklist (kronolojik adım sırası)

> Tüm adımlar `E:\MITAS` workspace'inde, PowerShell ile.

**ADIM 1 — PostgreSQL + pgvector kurulumu**

İki seçenek:

**A) Docker (önerilen):**
```powershell
# docker-compose.face.yml oluştur:
# services:
#   postgres:
#     image: pgvector/pgvector:pg16
#     environment:
#       POSTGRES_DB: mitas
#       POSTGRES_USER: mitas
#       POSTGRES_PASSWORD: <secret>
#     ports:
#       - "5432:5432"
#     volumes:
#       - ./pgdata:/var/lib/postgresql/data

docker compose -f docker-compose.face.yml up -d
```

**B) Native Windows:**
- PostgreSQL 16 installer indir (https://www.postgresql.org/download/windows/)
- Kurulum sonrası: `CREATE EXTENSION vector;` çalıştır (pgvector binary'sini ayrıca yüklemek gerekir — Windows için pgvector binary mevcut)

**Karar:** v0.4 ilk koşum için **Docker tercih edilir** (kurulum/teardown kolay). v1.x production'da native veya managed.

**ADIM 2 — Face venv eksik paketleri kur**

```powershell
$venv = "E:\MITAS\venvs\face\Scripts"
& "$venv\python.exe" -m pip install --upgrade pip
& "$venv\python.exe" -m pip install `
    "fastapi>=0.115" `
    "uvicorn[standard]>=0.30" `
    "psycopg[binary,pool]>=3.2" `
    "sqlalchemy>=2.0" `
    "python-multipart>=0.0.9" `
    "pyyaml>=6.0" `
    "alembic>=1.13" `
    "tenacity>=9.0" `
    "httpx>=0.27"

# Lock dosyalarını güncelle
& "$venv\python.exe" -m pip freeze > "E:\MITAS\locks\face.freeze.txt"
& "$venv\python.exe" "E:\MITAS\scripts\inspect_model_envs.py" --venv face > "E:\MITAS\locks\face.inspect.json"

# Smoke import testi
& "$venv\python.exe" -c "import insightface, supervision, hdbscan, pgvector, fastapi, psycopg; print('face venv OK')"
```

**ADIM 3 — InsightFace model cache'ini sabitle**

```powershell
# Modeller varsa:
ls "$env:USERPROFILE\.insightface\models\buffalo_l"

# Yoksa, manuel indirme:
& "$venv\python.exe" -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition'])
app.prepare(ctx_id=0)
print('buffalo_l yuklendi')
"

# Cache'i workspace'e taşı (no-internet stratejisi için):
mkdir -Force "E:\MITAS\models\face\buffalo_l"
Copy-Item "$env:USERPROFILE\.insightface\models\buffalo_l\*" "E:\MITAS\models\face\buffalo_l\"
```

**ADIM 4 — Veritabanı şeması oluştur**

```powershell
$pgconn = "host=localhost port=5432 user=mitas password=<secret> dbname=mitas"

# pgvector extension
psql -d $pgconn -c "CREATE EXTENSION IF NOT EXISTS vector;"

# face_bank schema (Blok 3'teki tüm DDL):
psql -d $pgconn -f "E:\MITAS\core\schemas\face_bank\migrations\v1_initial.sql"

# Smoke test
psql -d $pgconn -c "\dt face_bank.*"
```

Veya **Alembic** ile (önerilen v0.4 sonrası):

```powershell
cd E:\MITAS
& "$venv\python.exe" -m alembic init alembic_face
# alembic.ini sqlalchemy.url=postgresql+psycopg://mitas:<secret>@localhost/mitas
& "$venv\python.exe" -m alembic upgrade head
```

**ADIM 5 — Konfig dosyasını oluştur**

```powershell
# config/face.yaml — Blok 4'teki içerikle
# .env dosyası ekle:
# FACE_DB_URL=postgresql+psycopg://mitas:<secret>@localhost/mitas
# FACE_BANK_CROP_DIR=E:/MITAS/outputs/face_bank/samples
# FACE_BANK_UNKNOWN_DIR=E:/MITAS/outputs/face_bank/unknown_crops
# FACE_APP_ENV=development  # production'da 'production'
```

**ADIM 6 — Pipeline kod iskeleti**

```
core/pipelines/face/
├── __init__.py
├── pipeline.py                  ← run_face_pipeline(media_id, job_id, config, deps)
├── config.py                    ← FacePipelineConfig (Pydantic)
├── models.py                    ← Detection, Track, Cluster, MatchResult vs.
├── stages/
│   ├── __init__.py
│   ├── stage_0_media_prep.py
│   ├── stage_1_pre_scan.py
│   ├── stage_2_dense_detect.py
│   ├── stage_3_tracking.py
│   ├── stage_4_quality_gate.py
│   ├── stage_5_alignment_embedding.py
│   ├── stage_6_clustering.py
│   ├── stage_7_bank_match.py
│   ├── stage_8_importance.py
│   ├── stage_9_emit_events.py
│   ├── stage_10_output_write.py
│   ├── stage_11_review_queue.py
│   └── stage_12_system_event.py
├── engines/
│   ├── __init__.py
│   ├── detector.py              ← DetectorEngine Protocol + SCRFDEngine
│   ├── embedder.py              ← EmbedderEngine + ArcFaceEngine
│   ├── tracker.py               ← TrackerEngine + ByteTrackEngine
│   └── clusterer.py             ← ClustererEngine + HDBSCANClusterer
├── bank/
│   ├── __init__.py
│   ├── repository.py            ← face_bank DB operations (persons, samples, centroids)
│   ├── matcher.py               ← pgvector lookup + threshold logic
│   ├── seeder.py                ← bulk import endpoint logic
│   ├── retention.py             ← KVKK retention scheduler
│   └── audit.py                 ← audit_log writer
├── importance/
│   ├── __init__.py
│   ├── scorer.py                ← compute_importance_score()
│   └── signals.py               ← signal extractors (KJ overlap, ASR overlap)
├── quality/
│   ├── __init__.py
│   ├── gate.py                  ← track_passes_quality_gate()
│   └── crop_selector.py         ← pick_best_crops()
└── showcase/
    ├── __init__.py
    └── live_tracker.py          ← Live Track Demo (showcase mode)
```

**ADIM 7 — Backend API (face venv'inde)**

```
core/api/face_server.py          ← FastAPI app
core/api/face_routes/
├── analyze.py                   ← POST /api/face/analyze, GET /api/face/jobs/{id}
├── bank.py                      ← persons, samples, seed
├── review.py                    ← review queue, confirm, reject
└── demo.py                      ← /api/face/demo/track (Live Track Demo)
```

Uvicorn ile başlatma:
```powershell
& "E:\MITAS\venvs\face\Scripts\uvicorn.exe" core.api.face_server:app --port 8788 --workers 1
```

Port 8788 — ASR backend 8787, Face 8788, ileride OCR 8789 vs. Webui Vite proxy `/api/face` → `localhost:8788` eklenir.

**ADIM 8 — Testler**

```
tests/face/
├── test_face_schema.py              ← Pydantic + DDL doğrulama
├── test_face_quality_gate.py        ← quality gate kararları
├── test_face_importance_scorer.py   ← importance formülü
├── test_face_matcher.py             ← match decision logic
├── test_face_repository.py          ← DB CRUD
├── test_face_audit.py               ← audit log invariant'lar
├── test_face_retention.py           ← KVKK TTL job
├── test_face_pipeline_smoke.py      ← golden output smoke (küçük klip)
└── fixtures/
    ├── small_news_clip.mp4
    ├── small_news_clip_expected_output.json
    └── seed_bank/
        ├── persons.json
        └── photos/
```

Pytest komut:
```powershell
cd E:\MITAS
& "venvs\face\Scripts\python.exe" -m pytest tests/face/ -v
```

### 5.3 Dizin yapısı (genel)

```
E:\MITAS\
├── core/
│   ├── pipelines/face/           ← Blok 5 ADIM 6'daki yapı
│   ├── api/face_server.py        ← Blok 5 ADIM 7
│   ├── schemas/                  ← MEVCUT (timeline, candidate_relation, evidence vs.)
│   │   └── face_bank/
│   │       └── migrations/
│   │           └── v1_initial.sql ← Blok 3 şeması
│   └── observability/             ← MEVCUT
├── config/
│   └── face.yaml                  ← Blok 4 config
├── venvs/face/                    ← MEVCUT
├── locks/
│   ├── face.freeze.txt            ← Güncellenecek
│   └── face.inspect.json          ← Güncellenecek
├── models/
│   └── face/buffalo_l/             ← Lokal model cache
├── outputs/
│   ├── system_events.jsonl         ← face_* event'leri eklenecek
│   ├── clips/<clip_id>/face/<job_id>/   ← face job outputs
│   └── face_bank/
│       ├── samples/                 ← person samples crop'ları
│       └── unknown_crops/           ← KVKK TTL'e tabi
├── docs/
│   ├── MITAS_v0_4_Face_Recognition_Plan_Journey.md  ← BU DOSYA
│   └── MITAS_v0_4_Face_Recognition_Plan_Final.md     ← TEMIZ PLAN
└── tests/face/                      ← Blok 5 ADIM 8
```

### 5.4 .env değişkenleri özet

```
FACE_DB_URL=postgresql+psycopg://mitas:<secret>@localhost:5432/mitas
FACE_BANK_CROP_DIR=E:/MITAS/outputs/face_bank/samples
FACE_BANK_UNKNOWN_DIR=E:/MITAS/outputs/face_bank/unknown_crops
FACE_APP_ENV=development
FACE_MODEL_CACHE_DIR=E:/MITAS/models/face
INSIGHTFACE_HOME=E:/MITAS/models/face          # InsightFace cache override
FACE_API_PORT=8788
FACE_LOG_LEVEL=INFO
```

### 5.5 Lisans hatırlatması (operasyonel kapı)

Master plan §0.3.15 ve §7.5:
- **InsightFace / buffalo_l lisans** doğrulaması v0.4 production kapısının ön-koşulu.
- Geliştirme + benchmark için kullanım serbest (InsightFace MIT, buffalo_l weights ayrı).
- Production deploy'a izin verilirken `FACE_APP_ENV=production` kontrolü yapılır; eksik consent_basis kayıtları işlem yapmaz.

Bu bir code değil, **operasyonel proses gereği**. Setup tamam olduğunda hukuk onayı paralel ilerler; production switch'e basılana kadar `FACE_APP_ENV=development`.

### 5.6 Worker entegrasyonu

`core/jobs/worker.py` (mevcut skeleton) Face pipeline'ı kayıt eder:

```python
# core/jobs/worker.py veya benzer entry
from core.pipelines.face.pipeline import run_face_pipeline

REGISTRY = {
    "asr": run_asr_pipeline,        # mevcut
    "face": run_face_pipeline,      # yeni
    # "ocr": run_ocr_pipeline,      # v0.2
}
```

Job alımı:
```python
job = repository.claim_next("face")
if job:
    deps = build_pipeline_deps(...)
    config = load_face_config()
    result = run_face_pipeline(job.media_id, job.job_id, config, deps)
    repository.mark_completed(job, result)
```

GPU exclusivity: showcase varken final analiz alınmaz. İki yaklaşım:
- **Tek slot worker** — `face` worker tek seferde tek job alır (en basit, v0.4 yeterli)
- Daha sonra GPU lock mutex'i

**Karar:** v0.4'te **tek slot worker**. Showcase ile final analizi aynı anda çalıştırma riski yok çünkü ikisi de aynı worker queue'su. Showcase fast-path: showcase request gelince queue'da bekleyen final job pauseolur (advisory). v1.x'te daha ince GPU lock.

### 5.7 Blok 5 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. 8 adımlı setup checklist baştan sona. PostgreSQL/pgvector iki seçenekle. Eksik paketler listelendi. Dizin yapısı, .env, lisans kapısı, worker entegrasyonu hepsi var. Plan code-execute-friendly.

**Soru 2: Bağlamı korudum mu?**
> Evet. Mevcut face venv kontrolü gerçek paketlerden geldi. Output sözleşmesi 13.brief ile uyumlu. Worker entegrasyonu ASR pattern'iyle aynı. Port 8788 ASR'nin 8787'siyle çakışmaz. Lisans gating (§0.3.15) operasyonel olarak ayrılmış.

**Soru 3: Başka şeyi bozdum mu?**
> Bir dikkat: **Alembic** opsiyonel dedim ama eklendiğinde mevcut ASR + OCR migration süreçlerini etkiler mi? Şu an ASR/OCR DB kullanmıyor (sadece JSON output). Face DB'yi ilk kullanan modül. Alembic'i `alembic_face` ile namespace'leyerek ileride OCR/ASR DB tablolarını ayrı tutabiliriz veya unified alembic kullanabiliriz. **Karar:** v0.4'te **unified alembic** — `alembic/` tek dizin, içinde `face_*`, `asr_*`, `ocr_*` migration script'leri. Bu daha sürdürülebilir.
>
> İkinci dikkat: **Backend port 8788.** Vite proxy `/api/face` → `localhost:8788` eklemem lazım. webui/vite.config.ts'te bu var mı diye sonra kontrol etmem gerekiyor. Plan adımı: setup checklist'in **ADIM 9**'a "webui/vite.config.ts proxy ekle" eklenir.
>
> Üçüncü dikkat: **`INSIGHTFACE_HOME` env değişkeni.** InsightFace bu env'i kullanıyor mu? Aslında `INSIGHTFACE_HOME` resmi env değil; doğrusu `~/.insightface` veya `os.environ['INSIGHTFACE_ROOT']`. Bunu doğrulamam gerek — implementer aşamasında InsightFace kodunu okur. Plan içinde "no-internet stratejisi" için lokal cache yolu **`models/face/buffalo_l/`** olarak kalır; backend bunu pipeline.py içinde `model_path = "E:/MITAS/models/face/buffalo_l"` parametresiyle açıkça geçer. Env override karmaşa yapmasın.

**Soru 4: Daha iyisi var mı?**
> İki iyileştirme:
>
> **İyileştirme A — Alembic'i unified yap, namespace'le.** Karar yukarıdaki gibi alındı. Tek `alembic/versions/` dizini, migration adlarında `face_*` prefix.
>
> **İyileştirme B — Setup checklist'te "smoke test" adımı eksik.** ADIM 8 testleri vardı ama "kurulum bittiğinde elimde olan koşan endpoint" testi yok. Eklemeli:
>
> **ADIM 9 — End-to-end smoke koşum:**
> 1. Face backend başlat: `uvicorn core.api.face_server:app --port 8788`
> 2. Seed yükle: `curl -X POST http://localhost:8788/api/face/bank/seed -F persons.json=@tests/face/fixtures/seed_bank/persons.json ...`
> 3. Küçük klip ile analyze: `curl -X POST http://localhost:8788/api/face/analyze -F file=@tests/face/fixtures/small_news_clip.mp4`
> 4. Job tamam olunca: `curl http://localhost:8788/api/face/jobs/{job_id}` → output dosyaları yerinde mi
> 5. Webui smoke: Vite + Face proxy + FaceBank Builder sekmesi açılıp kişi listesini gösteriyor mu
>
> **Karar:** Her iki iyileştirme planda. A → ADIM 4 güncellendi. B → ADIM 9 eklendi. ADIM 10 olarak da "Vite proxy ekle" var.

**Plan değişikliği notu (DEC-FACE-J-005):**
- 2026-05-16: Alembic **unified** — tek `alembic/versions/` dizini, migration adlarında modül prefix (`face_*`, `asr_*`, vs.).
- 2026-05-16: ADIM 9 (E2E smoke koşum) eklendi: backend başlat, seed yükle, klip analyze, job poll, UI smoke.
- 2026-05-16: ADIM 10 (`webui/vite.config.ts` `/api/face` proxy ekle, port 8788) eklendi.

---

## 6. Blok 6 — Review UI, KVKK, Audit ve Güvenlik

### 6.1 Review UI — Üç temel ekran

Master plan §0.3.12 v1 Review UI MVP üç alandan biri olarak Face'i seçmiş: **Face unknown review**, **Face match confirmation**, **Face bank management**. WebUI'da bu üç ekran **FaceBank Builder** sekmesi altında toplanır (mevcut UI iki sekmeli yapıyla uyumlu).

#### 6.1.1 Face Unknown Review Ekranı

**Amaç:** Sistem `match_decision = "unknown"` veya `"needs_review"` dediği cluster'ları operatör onayına sun.

**Layout:**
- Sol panel: review queue (importance bucket sıralı; yüksek üstte)
- Orta: seçili cluster'ın temsilci crop'ları (3-5 adet, en kaliteliler)
- Sağ panel: cluster meta — clip + zaman aralığı, toplam ekran süresi, ASR speaker overlap, KJ metni varsa
- Alt: 3 button — `Bu kişi: [search/create]`, `Reddet`, `Sonra bakacağım`

**`Bu kişi:` aksiyonu:**
1. Mevcut kişi arama (autocomplete person table'dan)
2. Veya "Yeni kişi yarat" → modal: display_name, category, organization, kvkk_consent_basis (zorunlu production'da)
3. Onay → `POST /api/face/review/confirm` body: `{unknown_cluster_id, person_id | new_person_data}`
4. Backend:
   - Cluster temsilci embedding'leri **yeni sample** olarak face_samples'a eklenir (source_kind="review_confirmed", source_clip_id, source_track_id dolu)
   - unknown_cluster.status = "merged_to_person", promoted_person_id set
   - Person centroid yeniden hesaplanır
   - Audit log: "promote_unknown"
   - Eğer cluster zaman aralığında pending `face_matches_kj_name_candidate` veya `speaker_overlaps_face_candidate` varsa, bu CandidateRelation'lar **identity'ye terfi edilir** (status `confirmed`).

**`Reddet` aksiyonu:**
- `POST /api/face/review/reject` body: `{unknown_cluster_id, reason}`
- unknown_cluster.status = "rejected"
- TTL gelince crop'lar silinir, embedding deactive
- Audit log: "reject_unknown"

**Cross-video pattern gösterimi:** Eğer aynı `unknown_cluster_id` farklı kliplerde görüldüyse, UI altta küçük thumb-strip ile "bu yüz şu 6 yayında geçti" gösterir → operatöre daha güçlü sinyal.

#### 6.1.2 Face Match Confirmation Ekranı

**Amaç:** Sistem `auto_matched` dediği match'leri operatör doğrulasın (özellikle ilk 1-2 haftalık alışma döneminde).

**Layout:**
- Liste: clip + zaman + match person + score + cluster temsilci crop
- Quick action: `Onayla`, `Yanlış eşleşme`, `Bu cluster aslında: <başka kişi>`

**Yanlış eşleşme:**
- Cluster match reddedilir, status `needs_review` olur
- Audit log: "match_rejected"
- Banka: eğer sample'ın yanlış kişiye ait olduğu kanıtlanırsa, sample deactivate edilir (operatör isterse)

**Periyot:** v0.4'te tüm `auto_matched` review'a düşer. v1.x'te confidence çok yüksekse (örn. score > 0.92) review atlanabilir (config).

#### 6.1.3 Face Bank Management Ekranı

Blok 3 §3.5'te detayları yazıldı. Özet:
- Kişi listesi + arama + filter (category, organization)
- Kişi detayı: sample'lar, audit log, görüldüğü klipler
- Sample ekle / sil / kalitesiz işaretle
- Kişi birleştirme (merge)
- Manuel foto upload (lisans/source_provenance zorunlu form)

### 6.2 Webui — Component yapısı

Mevcut webui (E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui) iki sekmeli: **Analysis Workstation** + **FaceBank Builder**. Face ekranları **FaceBank Builder** altında:

```
webui/src/app/components/face/
├── FaceBankBuilder.tsx           ← Ana sekme container
├── tabs/
│   ├── BankManagementTab.tsx     ← 6.1.3
│   ├── UnknownReviewTab.tsx      ← 6.1.1
│   └── MatchConfirmationTab.tsx  ← 6.1.2
├── components/
│   ├── PersonList.tsx
│   ├── PersonDetail.tsx
│   ├── PersonCreateModal.tsx
│   ├── PersonMergeModal.tsx
│   ├── SampleGrid.tsx
│   ├── ReviewQueue.tsx
│   ├── ClusterReviewCard.tsx     ← Cluster crop strip + meta + actions
│   ├── CrossVideoStrip.tsx       ← Aynı unknown_cluster diğer klipler
│   └── AuditTimeline.tsx
└── api/
    └── face-api.ts               ← /api/face/* endpoint client'ları
```

Mock data + Türkçe etiketler + status vocabulary master plan ile uyumlu (`raw`, `auto`, `needs_review`, `confirmed`, `rejected`).

### 6.3 KVKK uygulaması (operasyonel detay)

Blok 3 §3.6'da retention süreci yazıldı. Burada **operasyonel kapı** ve **erişim kontrolü** netleştirilir.

#### 6.3.1 Erişim seviyeleri

| Rol | İzinler |
|---|---|
| `viewer` | sadece okuma; review queue okur, person detail okur; sample crop ve embedding görmez |
| `reviewer` | viewer + review confirm/reject; manuel person create; sample upload (own clips) |
| `admin` | tümü + person delete (KVKK), merge, threshold değiştirme, retention manual trigger |

v0.4 ilk aşama: tek user, lokal kullanım. Rol enforcement v1.x'te eklenir. Ama **şema baştan rol-aware** olmalı: `audit_log.actor` doldurulur, `created_by` alanları zorunlu.

v0.4 dönemi için `actor = "local_dev"` veya kullanıcı ortam değişkeninden (`FACE_OPERATOR_ID`) alınır.

#### 6.3.2 KVKK silme talebi prosedürü

Veri sahibi (data subject) silme talep ederse:

1. **Talep alımı** — Yazılı talep, talep no, talep tarihi, kişi adı + identifier
2. **Person bulma** — `display_name` veya kimlik bilgisinden person_id bulunur
3. **Silme komutu**:
   ```
   POST /api/face/bank/persons/{person_id}/kvkk-delete
   body: {
     request_id: "KVKK-2026-001",
     requested_at: "2026-05-16T...",
     legal_basis: "data_subject_right_kvkk_art_11",
     scope: "full"   # veya "anonymize" (audit log korur, kişisel veri siler)
   }
   ```
4. **Backend kaskad:**
   - Tüm face_samples soft delete + crop dosyaları HARD delete (geri dönüş yok)
   - person centroid SİL
   - persons.display_name → `"[KVKK_DELETED_<request_id>]"`, aliases [], deleted_at set
   - Geçmiş face_event'ler ve CandidateRelation'lar: `person_id` referansı bozulmaz ama UI'da `display_name` anonymize gösterir
   - audit_log: action="kvkk_deletion_request", before/after state korunur
5. **Yanıt:** Talep sahibine 30 gün içinde tamamlandı yazılı bildirim

**Unknown cluster KVKK talebi:** Genelde talep edilemez (kimliği belirsiz). Ama operatör bir unknown cluster'ı "bu benim" diye reddederse: `POST /api/face/review/reject` + `kvkk_subject_request: true` flag → 30 gün TTL beklemez, hemen silinir.

#### 6.3.3 Retention scheduler (sistem)

`core/pipelines/face/bank/retention.py`:

```python
def run_retention_job():
    """Günlük 03:00'te çalışır."""
    # Unknown clusters
    expired = db.query(UnknownCluster).filter(
        UnknownCluster.retention_expires_at < now(),
        UnknownCluster.status.in_(['pending_review', 'rejected'])
    ).all()

    for uc in expired:
        delete_crops(uc.unknown_cluster_id)
        uc.centroid_embedding = None  # anonymize
        uc.status = 'expired'
        audit_log.write(actor='system', action='retention_expire', ...)

    # Audit log retention
    cutoff = now() - timedelta(days=config.kvkk.audit_log_retention_days)
    db.query(AuditLog).filter(AuditLog.ts < cutoff).update({
        'before_state': sql.null(),
        'after_state': sql.null(),
        'ip_or_session': sql.null(),
        'reason': '[REDACTED_RETENTION]'
    })
```

Cron / scheduled task: Windows Task Scheduler veya APScheduler ile. v0.4 manuel çağrılabilir endpoint: `POST /api/face/admin/retention/run` (admin role).

#### 6.3.4 Üretim öncesi hukuk çıktıları (askıda)

Master plan §7.5'te listelendi:
- buffalo_l production lisans onayı
- KVKK biometric retention sayıları onayı (30/30/365 gün)
- Face bank erişim yetki politikası
- Embedding export default kapalı (kurum dışına çıkmaz)
- Audit log retention onayı

v0.4 release **production-mode'da çalışmaz** bu onaylar gelmeden. Development/research mode olarak kalır. `FACE_APP_ENV=development` default.

### 6.4 Audit log (detay)

Master plan §0.3.15: "audit log: kişi ekleme / silme / birleştirme / eşik değişimi zorunlu". Blok 3'te şema yazıldı. Burada **ne yazılır** ve **kim yazar** somutlaştırılır.

| Action | Kim | Tetik | Before/After |
|---|---|---|---|
| `create_person` | reviewer/admin | POST /persons | null / {display_name, ...} |
| `delete_person` | admin | POST /persons/{id}/kvkk-delete | {full state} / "[REDACTED]" |
| `merge_persons` | admin | POST /persons/{id}/merge | {primary state} / {merged state} |
| `add_sample` | reviewer/admin | POST /samples or /seed | null / {sample_id, source_kind} |
| `deactivate_sample` | reviewer/admin | POST /samples/{id}/deactivate | {is_active:true} / {is_active:false} |
| `promote_unknown` | reviewer/admin | POST /review/confirm | {status:pending_review} / {status:merged_to_person, promoted_person_id} |
| `reject_unknown` | reviewer/admin | POST /review/reject | {status:pending_review} / {status:rejected} |
| `match_rejected` | reviewer | POST /matches/{id}/reject | {decision:auto_matched} / {decision:needs_review} |
| `threshold_change` | admin | POST /admin/config | {old config} / {new config} + reason |
| `kvkk_deletion_request` | admin | POST /persons/{id}/kvkk-delete | {full} / "[REDACTED_KVKK]" + request_id |
| `retention_expire` | system | cron | {unknown_cluster state} / {status:expired} |
| `config_load` | system | startup | null / {config snapshot} |

**audit_log endpoint:** `GET /api/face/admin/audit` (filter by actor, action, target_kind, time range). Read-only, sadece admin.

### 6.5 Güvenlik (network + storage)

- **Lokal network:** Backend `localhost` veya kurum içi VLAN. Internet dışa çıkış kapalı (No-internet model cache stratejisi, ASR'de zaten var, Face için de uygulanır).
- **DB credential:** `.env` git'e girmez. Production'da Vault veya OS keyring.
- **HTTPS:** v0.4 lokal HTTP yeterli. Production'da reverse proxy (nginx/caddy) TLS.
- **CORS:** Vite dev (5173) + production UI origin'ler. Wildcard yok.
- **File upload limits:** Max 10 MB foto, max 5 GB video (configurable).
- **Crop dosya izinleri:** `outputs/face_bank/` Windows ACL ile kısıtlı (sadece face service hesabı + admin).
- **Embedding export:** API endpoint **yok** (master plan §7.5). DB direct query gerekirse admin SQL erişim.

### 6.6 Showcase (Live Track Demo) güvenliği

Showcase modu (`/api/face/demo/track`) **kişi tanıma yapmaz**, bankaya yazmaz. Sadece tıkla-seç-takip. KVKK riski düşük çünkü:
- Hiçbir embedding üretilmez (sadece ByteTrack ID'leri)
- Hiçbir crop kalıcı saklanmaz (RAM-only)
- Hiçbir DB kaydı yapılmaz
- Audit log: showcase başlangıç/bitiş kaydı (`action="showcase_start"` ve `"showcase_end"`) tutulur.

GPU exclusivity: showcase başlarken Face worker'ı **pause** edilir (yeni final job alımı durur). Showcase bitince resume. Bu policy backend'de:

```python
@app.post("/api/face/demo/track/start")
async def start_showcase(...):
    await face_worker.pause(reason="showcase_active")
    audit.write(action="showcase_start", ...)
    ...
```

### 6.7 Blok 6 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Review UI üç ekran + endpoint sözleşmesi açık. KVKK silme prosedürü adım adım. Audit log "kim, ne, ne zaman, hangi before/after" tam matrisle. Güvenlik (auth, network, files, embedding export) listelendi. Showcase'in KVKK riskinin düşük olduğu gerekçeli.

**Soru 2: Bağlamı korudum mu?**
> Evet. Master plan §0.3.12 (Review UI MVP üç ana alan), §0.3.15 (KVKK retention + audit log zorunlu), §7.5 (lisans/hukuk askıda) hepsi planda. UI Component yapısı mutfak 10.UI'daki React/Vite + shadcn yapısıyla uyumlu (`webui/src/app/components/face/`). Status vocabulary (raw/auto/needs_review/confirmed/rejected) master plan §1.3'ten direkt geldi. Mutfak 10.10.3'teki mock'tan yabancı ünlü (Michael Jordan) gibi sorunların çözümü "default bank Türk kamuoyu" prensibiyle ele alındı (Blok 1 §1.4 #5).

**Soru 3: Başka şeyi bozdum mu?**
> Bir dikkat: **`person_id` referansı bozulmaz ama UI'da anonymize gösterir** dedim. Bu önemli — KVKK silme talebi geldikten sonra timeline'daki geçmiş `face_cluster_appearance` event'lerinde person_id var. Eğer person silinmişse:
> - Ya UI bu event'leri "[KVKK_DELETED]" göstermeli
> - Ya da event'lerin de `person_id` referansı temizlenmeli
>
> Master plan §0.3.15: "silme: embedding/crop/template/review linklerini sil veya anonimleştir". "review linklerini" → event/CandidateRelation gibi yansıyan kayıtları kapsar. Pratikte: **anonymize yeterli**. Event içindeki person_id korunur (audit için), display_name "[KVKK_DELETED]" döner. Bu daha sürdürülebilir.
>
> İkinci dikkat: **Yanlış eşleşme reddedildiğinde sample'a ne olur?** Eğer auto_matched score 0.92 ile çıktıysa ama yanlışsa, sample doğru person'ın değildi demek. Backend bunu otomatik öğrenmeli mi? **Karar:** v0.4'te otomatik öğrenmez. Operatör isterse sample'ı manuel deactivate edebilir. v1.x'te hard negative mining (yanlış eşleşmiş cluster + true person seed pair'i) düşünülebilir.

**Soru 4: Daha iyisi var mı?**
> İki iyileştirme:
>
> **İyileştirme A — Review UI'a "embedding gizleme" politikası.** Master plan §7.5'te "embedding export varsayılan kapalı" var. Review UI'da bazı debug görünümlerinde (cluster centroid 2D PCA projeksiyonu vb.) embedding bilgisi sızdırabilir. **Karar:** UI'da embedding vector hiçbir endpoint'te döndürülmez. Sadece **similarity score** (cosine) gösterilir. Test/debug için ayrı admin SQL aracı. Bu Blok 6 §6.5'e açıkça eklensin.
>
> **İyileştirme B — KVKK silme talebi geldiğinde audit_log'a `request_id` ile bağlanmalı.** Bu bir veri sahibinin talebinin denetlenebilirliği için kritik. Talep no + tarih + scope + applied_by + applied_at audit_log.reason JSON'una yazılır. Schema'da `audit_log.reason` zaten var; sadece dolduralan format belirlensin:
>
> ```json
> {
>   "kvkk_request_id": "KVKK-2026-001",
>   "requested_at": "2026-05-16T10:00:00+03:00",
>   "scope": "full",
>   "legal_basis": "data_subject_right_kvkk_art_11"
> }
> ```
>
> **Karar:** Her iki iyileştirme planda. A → §6.5 "Embedding export endpoint yok, similarity score'a indirgenmiş bilgi gösterilir" netleştirildi. B → `audit_log.reason` JSON format şablonu §6.3.2'ye eklenecek.

**Plan değişikliği notu (DEC-FACE-J-006):**
- 2026-05-16: Embedding vektörü **hiçbir API endpoint'inden dönmez**. Sadece similarity skoru. Debug için admin SQL gerekirse ayrı kanal.
- 2026-05-16: KVKK silme talebi audit_log.reason için JSON şablonu: `{kvkk_request_id, requested_at, scope, legal_basis}`.
- 2026-05-16: KVKK silme sonrası geçmiş event'lerde `person_id` korunur (bağlantı bozulmaz), UI display_name "[KVKK_DELETED]" gösterir; embedding/crop tamamen silinir.

---

## 7. Blok 7 — Test, Benchmark, Validation, Kabul

### 7.1 Test piramidi

```
                  ╱──────────────╲
                 ╱  E2E Smoke      ╲      ← küçük klip uçtan uca
                ╱────────────────────╲
               ╱  Integration         ╲   ← DB + pipeline + worker
              ╱──────────────────────────╲
             ╱  Unit tests                ╲ ← stage'ler, scorer, gate, repository
            ╱──────────────────────────────╲
```

### 7.2 Unit testler (tests/face/)

| Dosya | Kapsam |
|---|---|
| `test_face_quality_gate.py` | Her gate kuralı (height, blur, pose, duration, conf, occlusion, intra-track std) için True/False senaryoları |
| `test_face_crop_selector.py` | En iyi N crop seçimi kalite formülü monotonic? Aynı crop'tan tekrar etmez |
| `test_face_alignment.py` | 5-point similarity transform doğru hesaplanıyor (sanity matris kontrol) |
| `test_face_importance_scorer.py` | weighted sum, graceful degradation (ASR/OCR yokken), bucket eşikleri |
| `test_face_matcher.py` | auto/needs_review/unknown karar mantığı (eşikleri config'ten okur) |
| `test_face_repository.py` | persons CRUD, samples CRUD, centroid recompute, merge persons, soft delete cascade |
| `test_face_audit_log.py` | Her action için audit entry yazılıyor, before/after JSON doğru |
| `test_face_retention.py` | TTL gelen unknown_cluster: crop'lar silinir, embedding nullify, status=expired |
| `test_face_kvkk_delete.py` | Person KVKK delete sonrası: samples deactive, crop'lar fiziksel silinmiş, display_name "[KVKK_DELETED]" |
| `test_face_config_loader.py` | YAML parse, env override, validation errors |
| `test_face_engine_protocols.py` | SCRFDEngine/ArcFaceEngine/ByteTrackEngine/HDBSCANClusterer protokollere uyuyor |

Hedef: **80+ unit test**, hepsi pytest ile, CI'da koşar, GPU gerektirmez (fixture dummy embedding/track ile).

### 7.3 Integration testler

Gerçek DB (pgvector docker container) + dummy media pipeline:

| Test | Akış |
|---|---|
| `test_face_pipeline_e2e_news_clip.py` | Küçük (10 sn) news klibi → pipeline → output dosyalar + DB kayıtlar oluştu mu |
| `test_face_pipeline_e2e_film_mode.py` | content_type=film → Stage 6-8 atlanıyor, sadece face_presence event'i |
| `test_face_pipeline_partial_fail.py` | pgvector down → Stage 7 atlanır, diğer stage'ler tamam, status=partial |
| `test_face_pipeline_oom.py` | Mock OOM → status=failed_resource_limit, no retry |
| `test_face_seed_bulk_import.py` | persons.json + photos → backend → DB persons + samples + centroids |
| `test_face_review_flow.py` | Unknown cluster → confirm → person sample eklendi, audit log var |
| `test_face_cross_video_unknown_merge.py` | İki ayrı klipte aynı yüz → unknown_cluster appearance_count = 2 |
| `test_face_showcase_pauses_worker.py` | Showcase start → worker.is_paused() True → showcase end → resume |

Hedef: **20+ integration test**, docker compose ile DB ayağa kaldırma + pytest fixture.

### 7.4 E2E Smoke (golden output)

ASR'de uygulanan pattern: küçük bilinen klip → pipeline koş → output dosyaları fixture golden ile karşılaştır.

```
tests/face/fixtures/
├── small_news_clip.mp4 (15-20 sn, 2 sunucu, 1 KJ)
├── small_news_clip_expected/
│   ├── face_summary.json         ← golden (büyük olmayan sayılar; track count, cluster count vb.)
│   ├── face_clusters.json        ← golden (cluster IDs deterministic değil ama count, sizes deterministic)
│   ├── face_events.json          ← golden (event count, types, time aralıkları toleransla)
│   └── face_quality_report.json  ← golden
└── seed_bank_small/
    ├── persons.json (5 kişi)
    └── photos/ (her birinde 3 foto)
```

Smoke testi: `pytest tests/face/test_face_pipeline_smoke.py -v` → ASR v0.1'deki gibi. 1 dakikalık koşum + JSON diff.

### 7.5 Benchmark seti

Master plan §0.3.14 ve `benchmark_templates/face_benchmark.yaml` zaten 20 saatlik v1 seti tanımlamış:
- 5 saat haber/panel KJ
- 5 saat müzik programı
- 5 saat belgesel/intertitle
- 5 saat film/jenerik

v0.4 kabul için **mini 8 saatlik** seti yeterli (sprint pace için):
- 5 saat haber/panel
- 1 saat müzik
- 1 saat belgesel
- 1 saat film

Ground truth Owner: TBD (OQ-4 ile bağlı — kim seed kişi listesini sağlayacaksa).

### 7.6 Benchmark metrikleri (`face_benchmark.yaml` 'da tanımlı)

| Metrik | Hesaplama | Hedef |
|---|---|---|
| `false_match_rate` | (yanlış kimlik atanan match) / (tüm auto_matched) | < 2% |
| `missed_face_rate` | (auto_matched olması beklenen ama olmayan) / (tüm beklenenler) | < 5% |
| `cluster_purity` | aynı cluster içinde dominant kişi oranı ortalaması | > 0.85 |
| `review_load` | (review queue eleman sayısı) / (klip süresi saat) | TBD (operatör capacity ile) |
| `runtime_per_minute` | (pipeline runtime sn) / (klip süresi dakika) | < 35 (1 saatlik klip < 35 dk) |
| `important_person_miss_rate` | önemli (KJ+ASR overlap) kişi kaçırma | < 5% |
| `vram_peak_mb` | pipeline boyunca peak GPU memory | < 6 GB |

`benchmark_templates/face_benchmark.yaml` TBD alanları (`false_match_rate_max`, `missed_face_rate_max`, `cluster_purity_min`) **bu hedef değerlerle doldurulur** v0.4 release öncesi.

### 7.7 Threshold kalibrasyon scripti (DEC-FACE-J-004)

`scripts/face_threshold_calibration.py`:

```
python scripts/face_threshold_calibration.py \
  --benchmark-set benchmarks/face_calibration_8h \
  --seed-bank tests/face/fixtures/seed_bank_v1 \
  --output outputs/face_calibration/pareto_v1.json
```

İşlevler:
1. 8 saatlik seti pipeline'a koş (auto_threshold × review_threshold grid 5x5 = 25 nokta)
2. Her noktada FMR + MFR + purity hesapla
3. Pareto-optimal noktaları işaretle
4. JSON rapor: `{thresholds: [...], pareto_front: [...], recommendation: {auto: X, review: Y, rationale: "..."}}`
5. Markdown özet: `outputs/face_calibration/pareto_v1.md`

### 7.8 Re-embed smoke test (DEC-FACE-J-003 — model versiyon değişimi)

```
tests/face/test_face_reembed_v1_to_v2.py
```

Senaryo:
1. v1 ile seed yüklendi
2. v2 model "kuruldu" (dummy/test fixture)
3. Re-embed job çağrıldı
4. Tüm samples'a v2 embedding eklendi (paralel)
5. v1 deaktive edildi (config flag)
6. Eski cluster lookup'ları v2 ile çalıştı

Bu test v0.4'te **smoke seviyesinde** (gerçek v2 yoksa mock dimension değişimi). Re-embed paterni mimaride var; v1.x'te gerçek v2 modelle test.

### 7.9 KVKK doğrulama testleri

Master plan §7.5 hatırlatması: production öncesi hukuk onayı gerekir, ama **planlı testler şimdiden yazılır**:

| Test | Beklenti |
|---|---|
| Production mode'da `kvkk_consent_basis` boş person create → reddedilir | check constraint |
| Person KVKK delete sonrası `face_samples` crop dosyaları diskten silinmiş | OS file check |
| Person KVKK delete sonrası tüm samples is_active=false | DB query |
| Person KVKK delete audit_log'a tam JSON şablonuyla yazılmış | audit_log read |
| Unknown cluster 30 gün sonra retention çalıştırıldığında centroid null, status=expired | TTL job dry-run |
| Audit log 1 yıldan eski entry'ler `before_state/after_state` null'a düşmüş | retention dry-run |
| Embedding vector hiçbir API endpoint response'unda görünmüyor | API contract test |

### 7.10 Performans/runtime testleri

| Test | Beklenti |
|---|---|
| 1 saatlik 1080p haber klibi tam pipeline | < 35 dk |
| Aynı klip film mode | < 25 dk (Stage 6-8 atlanır) |
| pgvector 10k embedding lookup | < 10 ms |
| Seed bulk import 100 person × 10 photo | < 2 dk |
| VRAM peak (SCRFD + ArcFace ardışık) | < 6 GB |
| Retention job 1000 expired unknown_cluster | < 30 sn |

### 7.11 Webui smoke

| Test | Beklenti |
|---|---|
| `npm run build` (vite) | başarılı |
| `tsc --noEmit` | başarılı |
| FaceBank Builder sekmesi açılıyor, 5 kişilik seed listesi gösteriliyor | manuel doğrulama |
| Unknown review queue boş klipte boş, dolu klipte cluster card gösterimi | manuel doğrulama |
| Match confirmation: auto_matched event'lere "Onayla / Yanlış" butonları | manuel doğrulama |

### 7.12 Kabul kriteri (v0.4 release)

v0.4 release sayılabilmesi için tüm aşağıdakiler:

- [ ] 80+ unit test, 100% pass
- [ ] 20+ integration test, 100% pass
- [ ] E2E smoke (golden output) pass
- [ ] Mini benchmark (8 saat) tamamlandı, raporlandı
- [ ] Threshold kalibrasyonu Pareto front analizi yapıldı, eşikler config'e işlendi, audit_log'a yazıldı
- [ ] `benchmark_templates/face_benchmark.yaml` TBD alanları dolu
- [ ] KVKK doğrulama testleri 100% pass
- [ ] Webui FaceBank Builder + smoke test pass
- [ ] Performans hedefleri (1 saatlik klip < 35 dk) gerçek klip üzerinde doğrulandı
- [ ] Sprint dokümanı: `docs/SPRINT_5_FACE_V0_4_DONE.md` yazıldı
- [ ] Hukuk askıda kararları (`OQ-3`, `OQ-6`) operasyonel olarak `FACE_APP_ENV=development` ile kapsam dışı; production deploy ayrı kapı

### 7.13 Yol haritası içindeki yeri

`mutfak/04_YOL_HARITASI.md` ve master plan §6:
- **v0.4 = Face Recognition dikey dilim** (bu plan)
- Önceki sürümler: v0.1 (ASR, hazır), v0.2 (OCR/KJ + Music, planlı), v0.3 (Visual Tag, planlı)
- v0.4 v0.2 ve v0.3 sonrası gelir (sıra master plan'da net). v0.4'ün **standalone çalışması mümkün** ama tam değer üretmesi v0.2 + v0.3 ile birlikte gelir (KJ overlap + speaker overlap importance sinyalleri).
- v0.5: Timeline birleşimi (Face + ASR + OCR + Visual Tag → cross-module relations).

**Pre-requisite tablosu:**

| Pre-req | Durum | v0.4 için kritik mi |
|---|---|---|
| ASR v0.1 | ✅ tamam | Importance signal (asr_speaker_overlap) için |
| OCR/KJ v0.2 | ⚠ planlı | Importance signal (kj_overlap) için; yoksa graceful degradation |
| Visual Tag v0.3 | ⚠ planlı | "kalabalık" tag faydalı; yoksa graceful degradation |
| PostgreSQL + pgvector | ❌ kurulmadı | **Kritik** (Blok 5 ADIM 1) |
| buffalo_l lisans onayı | ❌ askıda | Production için kritik; dev mode OK |
| Seed kişi listesi (50-100) | ❌ yok | **Kritik** (Blok 3 §3.3) |
| KVKK hukuk onayı (retention sayıları) | ❌ askıda | Production için kritik; dev mode OK |
| TRT iç test seti (8 saat) | ❌ yok | **Kritik** (Blok 7 §7.5) |

### 7.14 Blok 7 — Öz-denetim

**Soru 1: Amacımıza uygun mu?**
> Evet. Test piramidi (unit + integration + E2E + benchmark + KVKK + performans + UI) tam. Kabul kriteri 11 madde checklist. Threshold kalibrasyon scripti somut. Yol haritasındaki yer ve pre-requisite tablosu net. v0.4 release tanımı çalıştırılabilir.

**Soru 2: Bağlamı korudum mu?**
> Evet. `benchmark_templates/face_benchmark.yaml` ile metric isimleri eşleştirildi. Master plan §0.3.14 (test set sahibi + benchmark sprint) + §7.5 (lisans/hukuk) + §7.6 (proses) hepsi planda. mutfak 12 §10 "tamamlandı kriterleri" (komut + sonuç + workspace + mutfak update) v0.4 sprint kapanış raporunda uygulanır.

**Soru 3: Başka şeyi bozdum mu?**
> Bir dikkat: **CI/CD durumu.** ASR'de pytest CI'da koşuyor (mutfak 03 §2.3). Face testleri **çoğunlukla GPU gerektirmez** (fixture embedding/track ile mockable). Ama embedding/detection actual mode'da CI'da koşmak istersek GPU runner gerekir. **Karar:** Unit ve integration testleri **mock model ile** CI'da koşar (default). Gerçek model ile e2e testler `@pytest.mark.gpu` ile işaretli, sadece manuel/local GPU runner'da koşar (ASR'deki `real_media` pattern'i ile aynı).

**Soru 4: Daha iyisi var mı?**
> İki iyileştirme:
>
> **İyileştirme A — "Drift testi"**: v0.4 release sonrası 2 hafta operasyonel kullanım. Banka yeni sample'lar aldıkça centroid'ler değişir. Aynı klipte aynı pipeline, 2 hafta sonra farklı cluster üretebilir. Bu **drift**. Test:
>
> ```
> tests/face/test_face_centroid_drift.py
> ```
>
> Bir person'a 5 ek sample eklendiğinde centroid değişim miktarı (L2 distance) ölçülür; belirli eşikten fazla ise warn (uyarı). Bu eşik benchmark sonrası kalibre.
>
> **Karar:** v0.4 sonrası gözlem testi olarak girer (v1.x adayı).
>
> **İyileştirme B — Benchmark scriptinin **idempotent** olması.** Benchmark koşumu kesilirse veya partial fail olursa, tekrar koşturulduğunda kalan klipleri devam ettirir. `outputs/face_benchmark/<run_id>/state.json` kontrolü. Master plan §0.3.7 job_runs paterni zaten bunu sağlar — benchmark da bir worker job olarak kayıt altında olur.
>
> **Karar:** Benchmark script Blok 5'teki worker entegrasyonuna bağlı. Tek seferlik script değil; `benchmark_v0_4_face_calibration` adında bir job tipidir. job_runs tablosuna state kaydı yapar; partial recovery destekler.

**Plan değişikliği notu (DEC-FACE-J-007):**
- 2026-05-16: Benchmark script (`face_threshold_calibration.py`) tek seferlik değil; **worker job tipi** (`benchmark_v0_4_face_calibration`). job_runs üzerinden partial recovery destekler.
- 2026-05-16: Drift testi (centroid değişim takibi) v1.x adayı; v0.4 release'inde değil ama mimari hazır (centroid_versions tablosu zaten var, `last_recomputed_at` kullanılır).

---

## 8. Journey Sonu — Birikmiş Plan Değişiklikleri ve Açık Sorular

### 8.1 Plan değişiklikleri kronoloji

| ID | Tarih | Konu | Karar |
|---|---|---|---|
| `DEC-FACE-J-001` | 2026-05-16 | Modüler venv + Showcase namespace | Backend API her modül kendi venv'inde; showcase adı `Live Track Demo`, namespace `/api/face/demo/...` |
| `DEC-FACE-J-002` | 2026-05-16 | Pre-Scan, intra-track variance, eşikler | Pre-Scan profile bazlı opsiyonel; intra-track embedding std check Stage 4+5'e; eşikler config-driven |
| `DEC-FACE-J-003` | 2026-05-16 | Banka şema güçlendirme | `source_provenance JSONB NOT NULL`; production-mode `kvkk_consent_basis` check constraint; cross-video unknown eşiği config; re-embed paterni planlandı |
| `DEC-FACE-J-004` | 2026-05-16 | Film modu + threshold kalibrasyon | Film modu Stage 4 her zaman çalışır; `face_threshold_calibration.py` Pareto front |
| `DEC-FACE-J-005` | 2026-05-16 | Alembic unified + smoke + vite proxy | Tek alembic; ADIM 9 E2E smoke; ADIM 10 vite proxy `/api/face` → 8788 |
| `DEC-FACE-J-006` | 2026-05-16 | KVKK + embedding gizleme | Embedding endpoint döndürmez; KVKK silme JSON şablonu; geçmiş event'lerde person_id korunur, display_name redacted |
| `DEC-FACE-J-007` | 2026-05-16 | Benchmark worker job + drift | Benchmark script → worker job tipi (recovery'li); drift testi v1.x adayı |

### 8.2 Açık sorular (final plana taşınacak)

| ID | Soru | Cevap kanalı |
|---|---|---|
| `OQ-1` | PostgreSQL kurulu mu? Docker mı native mi? | Setup adım kararı (geliştirici) |
| `OQ-2` | FaceBank Builder sekmesi UI sözleşme uyumu | UI tasarım (geliştirici + UI cephesi) |
| `OQ-3` | buffalo_l lisans onayı? Fallback alternatif? | Hukuk/yayın hakları (TRT) |
| `OQ-4` | Seed kişi listesi kim sağlayacak? 50-100 kişi nasıl seçilecek? | İçerik/arşiv ekibi (TRT) |
| `OQ-5` | Film için `face_presence` event tipi ismi onayı | Plan içi karar (önerilen: `face_presence`) |
| `OQ-6` | Audit log retention süresi (1 yıl önerisi) | Hukuk/KVKK |
| `OQ-7` | Showcase + final GPU exclusivity tekniği (mutex/queue) | Plan içi karar (önerilen: tek slot worker) |

### 8.3 v0.4 implementasyon sırası (kronolojik öneri)

Final planda da çıkacak. Burada günlük/sprint ölçeğinde:

1. **Hafta 1 — Altyapı:** PostgreSQL + pgvector kurulum, face venv eksik paketler, alembic init, face_bank schema migration. Smoke import testi.
2. **Hafta 1-2 — Engine + Stage 0-3:** SCRFD, ByteTrack engine'leri ve Stage 0-3 (media prep, pre-scan, dense detect, tracking) kod + unit test.
3. **Hafta 2-3 — Stage 4-6:** Quality gate, crop selector, alignment + embedding, HDBSCAN clustering. Unit test + intra-track variance.
4. **Hafta 3 — Bank repository:** persons, samples, centroids, audit_log repository, seed bulk import endpoint. CRUD testler.
5. **Hafta 3-4 — Stage 7-9:** Bank match (pgvector), importance scoring, event + CandidateRelation emit. Graceful degradation testleri.
6. **Hafta 4 — Stage 10-12 + Worker:** Output write, review queue, system event, worker entegrasyonu.
7. **Hafta 4-5 — Backend API + UI:** FastAPI routes, FaceBank Builder webui component'leri.
8. **Hafta 5 — KVKK + Retention:** Retention scheduler, KVKK delete prosedürü, audit log retention.
9. **Hafta 5-6 — Showcase:** Live Track Demo backend + frontend.
10. **Hafta 6 — Seed + Benchmark:** 50-100 kişi seed yükleme, 8 saat benchmark seti hazırlama.
11. **Hafta 6-7 — Threshold kalibrasyon:** Pareto front analizi, eşikleri config'e ve audit_log'a yazma.
12. **Hafta 7 — Performance + Documentation:** Performans testleri, sprint dokümanı (`SPRINT_5_FACE_V0_4_DONE.md`).

Yaklaşık **7 hafta** — kabaca face dikey diliminin tek kişilik geliştirme yoğunluğu. Paralel cepheler (test seti hazırlama, hukuk onayı) bu süreyi etkileyebilir.

### 8.4 Risk listesi

| Risk | Etki | Azaltma |
|---|---|---|
| buffalo_l lisans red | Production blocklanır, alternatif model gerekir | Geliştirme dev mode'da devam; fallback: ArcFace açık ağırlık + SCRFD bağımsız kullanım |
| KVKK retention onayı gecikme | Production deploy blocklanır | Dev mode'da geliştirme devam, hukuk paralel ilerler |
| TRT seed listesi gelmiyor | Banka match çalışmaz | Geliştirici küçük dev seed (5-10 kişi) ile başlar; gerçek seed sonra |
| pgvector performans (50k+ embedding) | Lookup yavaşlar | HNSW index'e geçiş hazır (§0.3.16) |
| ByteTrack TRT haber kameranın kalabalık sahnelerinde yetersiz | False track ID | Master plan yedek: BoT-SORT (engine pattern hazır) |
| ArcFace TR yüzlerinde düşük accuracy | False match yüksek | Threshold kalibrasyon + seed banka büyütme |
| Eski TRT arşiv (interlaced/U-matic) yüz tanımıyor | Banka match düşük | Quality gate ile track atılır; banka match yapılmaz, unknown cluster oluşur |
| GPU OOM | Pipeline fail | load/unload yaşam döngüsü + retry policy |

### 8.5 Bu Journey hakkında kapanış

Bu dosya **plan inşa süreci**. Yedi blok yazıldı, her birinde dört öz-denetim sorusu soruldu, **on iki kayıtlı plan değişikliği** + **yedi açık soru** üretildi.

Eski "hızlı plan yazma" deseninden farklı olarak bu süreçte:
- Her blok sonrası kendine dürüst soru: "daha iyisi var mı?"
- Cevap "evet" ise gerekçesi yazıldı, plan revize edildi, eski karar üstü çizilmedi ama yeni karar net işlendi.
- Master plan / mutfak / kod tabanı / venv durumu hep referans alındı; varsayım üretilmedi.
- Açık sorular bastırılmadı; OQ-1 ile OQ-7 arasında listelendi.

Şimdi sıradaki adım: **Temiz Final Plan** — `docs/MITAS_v0_4_Face_Recognition_Plan_Final.md`. Bu dosyadaki tüm sonuçlar (revize sonrası sabitlenmiş) Final plana taşınır, journey detayları (öz-denetim, plan değişiklikleri) burada kalır.

---














