# MITAS v0.4 — Face Recognition Modülü — Temiz Plan

> Bu dosya **uygulayıcı için tek kaynak**. Tüm öz-denetim, kararsızlık, revizyon süreci `docs/MITAS_v0_4_Face_Recognition_Plan_Journey.md` içindedir. Bu plan revize edilmiş **son hâli** sunar.

> **Workspace:** `E:\MITAS` (canonical)
> **Sürüm hedefi:** v0.4 — Face Recognition dikey dilimi
> **Donanım hedefi:** RTX 3090 / 24 GB VRAM
> **Bağlayıcı üst dosyalar:** `MITAS_Master_Plan_Denetimli_v5.md` §2.2 + mutfak (00-13) + Karar günlüğü M4/M5/M9 + `benchmark_templates/face_benchmark.yaml`

---

## İçindekiler

1. [Vizyon ve Kapsam](#1-vizyon-ve-kapsam)
2. [Bağlayıcı Prensipler](#2-bağlayıcı-prensipler)
3. [Pipeline Mimarisi](#3-pipeline-mimarisi)
4. [Face Bank — Veritabanı Şeması](#4-face-bank--veritabanı-şeması)
5. [Seed ve Öğrenme Döngüsü](#5-seed-ve-öğrenme-döngüsü)
6. [Quality Gate, Importance, Threshold](#6-quality-gate-importance-threshold)
7. [Konfig Dosyası (Tek Yer)](#7-konfig-dosyası-tek-yer)
8. [Setup Adımları](#8-setup-adımları)
9. [Dizin ve Kod Yapısı](#9-dizin-ve-kod-yapısı)
10. [Backend API Sözleşmesi](#10-backend-api-sözleşmesi)
11. [Review UI ve FaceBank Builder](#11-review-ui-ve-facebank-builder)
12. [KVKK, Audit, Güvenlik](#12-kvkk-audit-güvenlik)
13. [Test ve Benchmark Planı](#13-test-ve-benchmark-planı)
14. [Kabul Kriteri](#14-kabul-kriteri-v04-release)
15. [İmplementasyon Sırası](#15-implementasyon-sırası-7-hafta)
16. [Risk Listesi](#16-risk-listesi)
17. [Açık Sorular](#17-açık-sorular-operatör-cevabı-bekleyen)

---

## 1. Vizyon ve Kapsam

**Tek cümlelik vaat:**

> Face Recognition modülü, kendi yapım TRT programlarında ekrana giren yüzleri tespit eder, takip eder, kümelendirir, önem sırasına göre review kovasına atar veya banka eşleşmesi önerir; her sonuç evidence ile açıklanabilir, hiçbir sonuç kullanıcı onayı olmadan kimlik kararı olarak yazılmaz.

### Kapsam içi
- Yüz tespit (SCRFD) + landmark
- Yüz hizalama
- Track (ByteTrack) → `track_id`
- Kalite kapısı + en iyi crop seçimi (3-5 crop/track)
- ArcFace embedding (512-d, L2 normalize)
- Intra-track embedding variance kontrolü
- HDBSCAN ile medya-içi cluster
- pgvector ile face bank lookup (cosine)
- Önem skoru + bucket (yüksek/orta/düşük + override toggle)
- Banka seed yönetimi (kişi + foto + embedding)
- Review döngüsü: unknown cluster → confirm → banka büyür
- Cross-video unknown cluster birleştirme
- Audit log (zorunlu)
- KVKK retention scheduler (30 gün unknown crop/cluster + 1 yıl audit)
- CandidateRelation üretimi (face_matches_kj_name_candidate, speaker_overlaps_face_candidate)
- Live Track Demo (showcase): tıkla-seç-takip; identity yok, banka yok, KVKK yok
- Film modu: face_presence event'i sadece (Stage 6-8 atlanır)
- Backend API + WebUI FaceBank Builder sekmesi
- JSON primary çıktı (output sözleşmesi `outputs/clips/<clip_id>/face/<job_id>/`)

### Kapsam dışı
- Live capture/RTMP/kamera (v1 dışı)
- Filmde kişi kimliği (M4, IMDb/TMDB v1.x)
- Cross-session voice ID (M5)
- VLM yardımcı (v0.4 dışı)
- BoT-SORT (yedek; v0.4 dışı)
- DBSCAN, RetinaFace, Qdrant/FAISS
- Hızlı/Dengeli/Detaylı modlar
- Otomatik showcase tanıma (v2)

---

## 2. Bağlayıcı Prensipler

1. **Yanlış kimlik > yok kimlik.** Eşik altı match `auto` olamaz; `needs_review` veya `null`.
2. **Candidate ≠ Identity.** `face_track_*`, `face_cluster_*`, `person_*` üç ayrı entity; köprü evidence + kullanıcı onayı.
3. **Showcase ≠ Final.** Live Track Demo namespace `/api/face/demo/...`; final analiz `/api/face/analyze/...`. GPU exclusivity.
4. **Evidence olmadan kayıt olmaz.** Her event'te frame_idx, time_ms, bbox, det_conf, track_id, kalite skoru, model versiyonu.
5. **Türkçe-merkezli banka.** Default Türk kamuoyu figürleri. Yabancı ünlü match örneği yasak.
6. **Modüler venv.** Backend her modülün kendi venv'inde; cross-module timeline merge `core` venv'inin işidir.
7. **KVKK temelde.** Embedding biyometrik veri. Yetki + audit + silme cascade + retention.
8. **Lisans gating.** `buffalo_l` production onayı yokken `FACE_APP_ENV=development`; production kapalı.

---

## 3. Pipeline Mimarisi

```
[Video Input] → Stage 0 → Stage 1 (opt) → Stage 2 → Stage 3 → Stage 4 →
Stage 5 → Stage 6 → Stage 7 → Stage 8 → Stage 9 → Stage 10 → Stage 11 → Stage 12
```

| # | Stage | İş | GPU? | Süre (1 saat klip) | VRAM peak |
|---:|---|---|---|---:|---:|
| 0 | Media Prep | FFmpeg metadata, output dir, job.json | yok | < 1 sn | — |
| 1 | Pre-Scan (opt) | 2sn/frame örnekleme, "yüz var mı" haritası | SCRFD | 3-5 dk | ~1 GB |
| 2 | Dense Detect | yüz olan aralıkta 2.5 fps tarama (SCRFD full) | SCRFD | 8-12 dk | ~1 GB |
| 3 | Tracking | ByteTrack ile track_id | yok (CPU) | 1-2 dk | — |
| 4 | Quality Gate | gate kuralları + en iyi 3-5 crop | yok | 30 sn-1 dk | — |
| 5 | Alignment+Embed | landmark align + ArcFace embedding | ArcFace | 30 sn-1 dk | ~1 GB |
| 5b | Intra-track stability | track içi embedding std > eşikse track ikiye böl | yok | < 30 sn | — |
| 6 | Clustering | HDBSCAN ile medya-içi cluster | yok | < 30 sn | — |
| 7 | Bank Match | pgvector top-k + threshold karar | yok | < 5 sn | — |
| 8 | Importance | weighted sum + bucket (graceful degradation) | yok | < 5 sn | — |
| 9 | Event + CandidateRelation Emit | TimelineEvent + CandidateRelation | yok | < 5 sn | — |
| 10 | Output Write | JSON dosyalar + ModuleRun kaydı | yok | < 5 sn | — |
| 11 | Review Queue | high/medium bucket cluster'lar queue'ya | yok | < 5 sn | — |
| 12 | System Event | `system_events.jsonl` `face_completed` | yok | < 1 sn | — |

**Toplam:** ~15-25 dk (1 saatlik haber klibi; pre-scan kapalı). **Hedef:** < 35 dk.

### GPU yaşam döngüsü

```
load("scrfd") → run Stage 1+2 → unload
load("arcface") → run Stage 5 → unload
# Stage 3, 4, 5b, 6-12 CPU/disk
```

Aynı anda iki yüz modeli yüklenmez. Peak VRAM ~1.5 GB.

### İçerik tipine göre kapı

- `content_type = "film"` → Stage 6-8 atlanır. Stage 4 yine çalışır. Stage 9'da yalnız `face_presence` event'i yazılır. CandidateRelation üretilmez. Review queue boş.
- Diğer (`news`, `panel`, `music`, `documentary`, `studio`) → tam pipeline.
- `content_type` boş → log uyarısı + tam pipeline.

### Hata yönetimi

- Bir stage fail → önceki valid çıktı korunur.
- Transient: 1 retry.
- OOM: retry yok → `status="failed_resource_limit"`.
- Schema validation fail → `status="failed_invalid_output"`.
- pgvector down → Stage 7 atlanır, Stage 8 `existing_bank_match=0`, status `partial`.

### Engine Strategy Pattern

```python
class DetectorEngine(Protocol): detect, warm_up, unload
class EmbedderEngine(Protocol): embed
class TrackerEngine(Protocol): update
class ClustererEngine(Protocol): cluster
```

Implementasyonlar: `SCRFDEngine`, `ArcFaceEngine`, `ByteTrackEngine`, `HDBSCANClusterer`. Yedek (BoT-SORT, DBSCAN) protokole uyarlanır.

---

## 4. Face Bank — Veritabanı Şeması

**DB:** PostgreSQL 16+ + pgvector extension.
**Schema:** `face_bank`.

```sql
-- Kişi
CREATE TABLE face_bank.persons (
  person_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name       TEXT NOT NULL,
  aliases            TEXT[] DEFAULT '{}',
  category           TEXT,
  organization       TEXT,
  notes              TEXT,
  created_by         TEXT NOT NULL,
  created_at         TIMESTAMPTZ DEFAULT now(),
  updated_at         TIMESTAMPTZ DEFAULT now(),
  deleted_at         TIMESTAMPTZ NULL,
  kvkk_consent_basis TEXT,
  retention_class    TEXT DEFAULT 'standard',
  CONSTRAINT chk_persons_kvkk_consent_when_production CHECK (
    current_setting('app.env', true) <> 'production'
    OR (kvkk_consent_basis IS NOT NULL AND length(kvkk_consent_basis) > 10)
  )
);

CREATE INDEX idx_persons_name ON face_bank.persons (display_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_persons_active ON face_bank.persons (deleted_at) WHERE deleted_at IS NULL;

-- Yüz örneği
CREATE TABLE face_bank.face_samples (
  sample_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id          UUID NOT NULL REFERENCES face_bank.persons(person_id) ON DELETE CASCADE,
  source_kind        TEXT NOT NULL,
  source_clip_id     TEXT NULL,
  source_track_id    TEXT NULL,
  crop_path          TEXT NOT NULL,
  bbox               INTEGER[4] NULL,
  landmarks          REAL[5][2] NULL,
  embedding          vector(512) NOT NULL,
  embedding_model    TEXT NOT NULL DEFAULT 'buffalo_l/w600k_r50',
  embedding_version  TEXT NOT NULL DEFAULT 'v1',
  quality_score      REAL NOT NULL,
  det_conf           REAL NOT NULL,
  pose_yaw           REAL NULL,
  pose_pitch         REAL NULL,
  blur_score         REAL NULL,
  face_height_px     INTEGER NULL,
  is_active          BOOLEAN NOT NULL DEFAULT TRUE,
  source_provenance  JSONB NOT NULL,
  created_by         TEXT NOT NULL,
  created_at         TIMESTAMPTZ DEFAULT now(),
  deactivated_at     TIMESTAMPTZ NULL
);

CREATE INDEX idx_samples_person ON face_bank.face_samples (person_id) WHERE is_active = TRUE;
CREATE INDEX idx_samples_model ON face_bank.face_samples (embedding_model, embedding_version);
CREATE INDEX idx_samples_embedding ON face_bank.face_samples
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Kişi centroid
CREATE TABLE face_bank.person_centroids (
  person_id           UUID PRIMARY KEY REFERENCES face_bank.persons(person_id) ON DELETE CASCADE,
  centroid_embedding  vector(512) NOT NULL,
  embedding_model     TEXT NOT NULL,
  embedding_version   TEXT NOT NULL,
  active_sample_count INTEGER NOT NULL,
  last_recomputed_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_centroids_embedding ON face_bank.person_centroids
  USING ivfflat (centroid_embedding vector_cosine_ops) WITH (lists = 50);

-- Unknown cluster cross-video
CREATE TABLE face_bank.unknown_clusters (
  unknown_cluster_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  first_seen_clip_id    TEXT NOT NULL,
  first_seen_at         TIMESTAMPTZ DEFAULT now(),
  last_seen_clip_id     TEXT NOT NULL,
  last_seen_at          TIMESTAMPTZ DEFAULT now(),
  appearance_count      INTEGER NOT NULL DEFAULT 1,
  centroid_embedding    vector(512) NOT NULL,
  embedding_model       TEXT NOT NULL,
  embedding_version     TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'pending_review',
  promoted_person_id    UUID NULL REFERENCES face_bank.persons(person_id),
  retention_expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_unknown_status ON face_bank.unknown_clusters (status) WHERE status = 'pending_review';
CREATE INDEX idx_unknown_expiry ON face_bank.unknown_clusters (retention_expires_at);
CREATE INDEX idx_unknown_embedding ON face_bank.unknown_clusters
  USING ivfflat (centroid_embedding vector_cosine_ops) WITH (lists = 50);

-- Audit log (KVKK zorunlu)
CREATE TABLE face_bank.audit_log (
  audit_id           BIGSERIAL PRIMARY KEY,
  ts                 TIMESTAMPTZ DEFAULT now(),
  actor              TEXT NOT NULL,
  action             TEXT NOT NULL,
  target_kind        TEXT NOT NULL,
  target_id          TEXT NOT NULL,
  before_state       JSONB NULL,
  after_state        JSONB NULL,
  reason             TEXT NULL,
  job_id             TEXT NULL,
  ip_or_session      TEXT NULL
);

CREATE INDEX idx_audit_ts ON face_bank.audit_log (ts DESC);
CREATE INDEX idx_audit_target ON face_bank.audit_log (target_kind, target_id);
CREATE INDEX idx_audit_actor ON face_bank.audit_log (actor);

-- Config versiyonları
CREATE TABLE face_bank.config_versions (
  config_version_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_name        TEXT NOT NULL,
  config_value       JSONB NOT NULL,
  effective_from     TIMESTAMPTZ DEFAULT now(),
  effective_until    TIMESTAMPTZ NULL,
  changed_by         TEXT NOT NULL,
  reason             TEXT NULL
);

CREATE INDEX idx_config_name_time ON face_bank.config_versions (config_name, effective_from DESC);
```

---

## 5. Seed ve Öğrenme Döngüsü

### Seed (başlangıç)

- Operatör 50-100 kişilik liste sağlar (CSV/JSON).
- Her kişiye 5-10 fotoğraf (200x200+ px, çeşitli açı/ışık).
- Bulk import endpoint: `POST /api/face/bank/seed`.
- Kabul edilen her sample için backend: detect → quality gate → align → embed → DB insert + audit_log.

### Review döngüsüyle büyüme

1. Pipeline `unknown` cluster üretir (Stage 6).
2. Cluster importance bucket high/medium ise review queue'ya.
3. Operatör:
   - `Bu kişi: <isim>` → cluster temsilci embedding'leri yeni sample olarak person'a eklenir, centroid yeniden hesaplanır, audit "promote_unknown".
   - `Reddet` → unknown_cluster.status="rejected", retention TTL (30 gün) sonunda crop fiziksel silinir, embedding null.
   - `Sonra` → queue'da kalır.

### Cross-video birleştirme

- Yeni klipte unknown cluster oluşunca önce `unknown_clusters` tablosunda cosine ≥ `face.unknown_merge.similarity_threshold` (default 0.75) aranır.
- Bulunursa: `appearance_count++`, `last_seen_*` güncellenir, UI cross-video strip gösterir.

---

## 6. Quality Gate, Importance, Threshold

### Quality Gate (Stage 4)

| Parametre | Default | Birim |
|---|---:|---|
| `face.quality.min_face_height` | 80 | px |
| `face.quality.blur_laplacian_min` | 100 | Laplacian variance |
| `face.quality.pose_yaw_max` | 30 | derece |
| `face.quality.pose_pitch_max` | 25 | derece |
| `face.quality.min_track_duration_sec` | 1.5 | saniye |
| `face.quality.min_detector_confidence` | 0.70 | [0,1] |
| `face.quality.intra_track_embedding_std_max` | 0.25 | float (track içi std) |
| `face.quality.crops_per_track_min` | 3 | int |
| `face.quality.crops_per_track_max` | 5 | int |

Tüm değerler benchmark sonrası kalibre edilir (`benchmark_templates/face_benchmark.yaml`).

### Importance Score (Stage 8)

```
importance_score = 0.35*screen_time
                 + 0.25*kj_overlap
                 + 0.20*asr_speaker_overlap
                 + 0.15*face_size_quality
                 + 0.05*existing_bank_match
```

- `screen_time` ∈ [0,1] (total_cluster_screen_time / clip_duration)
- `kj_overlap` ∈ {0, 1} (cluster zaman aralığında lower_third_person KJ varsa 1)
- `asr_speaker_overlap` ∈ [0,1] (max overlap ratio with any speaker_turn)
- `face_size_quality` ∈ [0,1] (mean track quality_score normalized)
- `existing_bank_match` ∈ {0, 0.5, 1} (auto / needs_review / unknown)

**Buckets:**
- `>= 0.55` → `high`
- `0.25 - 0.55` → `medium`
- `< 0.25` → `low` (default review default kapalı, override toggle ile)

**Graceful degradation:** ASR/OCR yoksa ilgili sinyal 0, max_possible azalır, bucket eşikleri max_possible'a göre ölçeklenir. Bayrak: `face.importance.relative_to_available_signals: true`.

### Match Threshold (Stage 7)

- `face.match.auto_threshold = 0.85` cosine sim → `auto_matched`
- `0.70 ≤ score < 0.85` → `needs_review`
- `< 0.70` → `unknown` (unknown cluster)
- `face.match.top_k = 5`
- `face.match.same_person_score_gap = 0.05`

Eşikler config-driven; benchmark Pareto front sonrası kalibre.

---

## 7. Konfig Dosyası (Tek Yer)

`config/face.yaml`:

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
    apply_quality_gate: true
    skip_stages: [clustering, bank_match, importance, candidate_relation]
  showcase:
    namespace: "/api/face/demo"
    exclusive_gpu: true
```

Konfig değişikliği `face_bank.config_versions` tablosuna otomatik yazılır.

---

## 8. Setup Adımları

> Tüm komutlar `E:\MITAS` workspace'inde, PowerShell.

### ADIM 1 — PostgreSQL + pgvector

Docker (önerilen):

```powershell
# docker-compose.face.yml
docker compose -f docker-compose.face.yml up -d
docker exec -it mitas-pg psql -U mitas -d mitas -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### ADIM 2 — Face venv eksik paketler

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

& "$venv\python.exe" -m pip freeze > "E:\MITAS\locks\face.freeze.txt"
```

Smoke import:
```powershell
& "$venv\python.exe" -c "import insightface, supervision, hdbscan, pgvector, fastapi, psycopg; print('face venv OK')"
```

### ADIM 3 — buffalo_l model cache

```powershell
& "$venv\python.exe" -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_l', allowed_modules=['detection','recognition'])
app.prepare(ctx_id=0)
print('buffalo_l yuklendi')
"
mkdir -Force "E:\MITAS\models\face\buffalo_l"
Copy-Item "$env:USERPROFILE\.insightface\models\buffalo_l\*" "E:\MITAS\models\face\buffalo_l\"
```

### ADIM 4 — Schema migration (Alembic unified)

```powershell
cd E:\MITAS
& "$venv\python.exe" -m alembic init alembic
# alembic/env.py + sqlalchemy.url=postgresql+psycopg://mitas:<secret>@localhost/mitas
# Yeni migration: alembic/versions/<timestamp>_face_v1_initial.py (Blok 4 DDL'i)
& "$venv\python.exe" -m alembic upgrade head
```

### ADIM 5 — Konfig + .env

`config/face.yaml` Bölüm 7'deki içerikle.

`.env`:
```
FACE_DB_URL=postgresql+psycopg://mitas:<secret>@localhost:5432/mitas
FACE_BANK_CROP_DIR=E:/MITAS/outputs/face_bank/samples
FACE_BANK_UNKNOWN_DIR=E:/MITAS/outputs/face_bank/unknown_crops
FACE_APP_ENV=development
FACE_MODEL_CACHE_DIR=E:/MITAS/models/face
FACE_API_PORT=8788
FACE_LOG_LEVEL=INFO
FACE_OPERATOR_ID=local_dev
```

### ADIM 6 — Pipeline kod iskeleti

`core/pipelines/face/` (Blok 9 dizin yapısı).

### ADIM 7 — Backend API

`core/api/face_server.py` + `core/api/face_routes/` (analyze, bank, review, demo).

```powershell
& "E:\MITAS\venvs\face\Scripts\uvicorn.exe" core.api.face_server:app --port 8788 --workers 1
```

### ADIM 8 — Test seti iskeleti

`tests/face/` (Bölüm 13).

```powershell
& "E:\MITAS\venvs\face\Scripts\python.exe" -m pytest tests/face/ -v
```

### ADIM 9 — E2E smoke

1. Face backend başlat (`uvicorn ... --port 8788`).
2. Seed yükle: `curl -X POST http://localhost:8788/api/face/bank/seed -F persons=@tests/face/fixtures/seed_bank_small/persons.json ...`
3. Klip analyze: `curl -X POST http://localhost:8788/api/face/analyze -F file=@tests/face/fixtures/small_news_clip.mp4`
4. Job poll: `curl http://localhost:8788/api/face/jobs/{job_id}` → output dosyaları yerinde mi.
5. WebUI: FaceBank Builder sekmesi açılıp persons listesini gösteriyor mu.

### ADIM 10 — Vite proxy

`webui/vite.config.ts` `server.proxy` içine ekle:
```ts
'/api/face': { target: 'http://localhost:8788', changeOrigin: true, rewrite: p => p.replace(/^\/api\/face/, '/api/face') }
```

---

## 9. Dizin ve Kod Yapısı

```
E:\MITAS\
├── core/
│   ├── pipelines/face/
│   │   ├── pipeline.py                  ← run_face_pipeline
│   │   ├── config.py
│   │   ├── models.py                    ← Detection, Track, Cluster, MatchResult
│   │   ├── stages/
│   │   │   ├── stage_0_media_prep.py
│   │   │   ├── stage_1_pre_scan.py
│   │   │   ├── stage_2_dense_detect.py
│   │   │   ├── stage_3_tracking.py
│   │   │   ├── stage_4_quality_gate.py
│   │   │   ├── stage_5_alignment_embedding.py
│   │   │   ├── stage_5b_intra_track_stability.py
│   │   │   ├── stage_6_clustering.py
│   │   │   ├── stage_7_bank_match.py
│   │   │   ├── stage_8_importance.py
│   │   │   ├── stage_9_emit_events.py
│   │   │   ├── stage_10_output_write.py
│   │   │   ├── stage_11_review_queue.py
│   │   │   └── stage_12_system_event.py
│   │   ├── engines/
│   │   │   ├── detector.py              ← DetectorEngine + SCRFDEngine
│   │   │   ├── embedder.py              ← EmbedderEngine + ArcFaceEngine
│   │   │   ├── tracker.py               ← TrackerEngine + ByteTrackEngine
│   │   │   └── clusterer.py             ← ClustererEngine + HDBSCANClusterer
│   │   ├── bank/
│   │   │   ├── repository.py
│   │   │   ├── matcher.py
│   │   │   ├── seeder.py
│   │   │   ├── retention.py
│   │   │   └── audit.py
│   │   ├── importance/
│   │   │   ├── scorer.py
│   │   │   └── signals.py
│   │   ├── quality/
│   │   │   ├── gate.py
│   │   │   └── crop_selector.py
│   │   └── showcase/
│   │       └── live_tracker.py
│   ├── api/
│   │   ├── face_server.py
│   │   └── face_routes/
│   │       ├── analyze.py
│   │       ├── bank.py
│   │       ├── review.py
│   │       └── demo.py
│   └── schemas/                         ← MEVCUT (timeline, candidate_relation, evidence...)
├── alembic/
│   └── versions/
│       └── <ts>_face_v1_initial.py      ← face_bank schema
├── config/
│   └── face.yaml
├── scripts/
│   └── face_threshold_calibration.py    ← Pareto front worker job tipi
├── outputs/
│   ├── system_events.jsonl
│   ├── clips/<clip_id>/face/<job_id>/
│   │   ├── job.json
│   │   ├── job_log.jsonl
│   │   ├── run/
│   │   │   ├── face_tracks.json
│   │   │   ├── face_clusters.json
│   │   │   ├── face_matches.json
│   │   │   ├── face_events.json
│   │   │   ├── face_candidate_relations.json
│   │   │   ├── face_summary.json
│   │   │   └── face_quality_report.json
│   │   └── crops/                       ← KVKK retention'a tabi
│   └── face_bank/
│       ├── samples/
│       └── unknown_crops/
├── tests/face/
│   ├── test_face_quality_gate.py
│   ├── test_face_crop_selector.py
│   ├── test_face_alignment.py
│   ├── test_face_importance_scorer.py
│   ├── test_face_matcher.py
│   ├── test_face_repository.py
│   ├── test_face_audit_log.py
│   ├── test_face_retention.py
│   ├── test_face_kvkk_delete.py
│   ├── test_face_config_loader.py
│   ├── test_face_engine_protocols.py
│   ├── test_face_pipeline_e2e_news_clip.py
│   ├── test_face_pipeline_e2e_film_mode.py
│   ├── test_face_pipeline_partial_fail.py
│   ├── test_face_pipeline_oom.py
│   ├── test_face_seed_bulk_import.py
│   ├── test_face_review_flow.py
│   ├── test_face_cross_video_unknown_merge.py
│   ├── test_face_showcase_pauses_worker.py
│   ├── test_face_reembed_v1_to_v2.py
│   ├── test_face_pipeline_smoke.py
│   └── fixtures/
│       ├── small_news_clip.mp4
│       ├── small_news_clip_expected/
│       └── seed_bank_small/
├── webui/src/app/components/face/
│   ├── FaceBankBuilder.tsx
│   ├── tabs/{BankManagement,UnknownReview,MatchConfirmation}Tab.tsx
│   ├── components/{PersonList,PersonDetail,...}.tsx
│   └── api/face-api.ts
└── docs/
    ├── MITAS_v0_4_Face_Recognition_Plan_Journey.md
    └── MITAS_v0_4_Face_Recognition_Plan_Final.md   ← BU DOSYA
```

---

## 10. Backend API Sözleşmesi

### Analyze (final)

| Endpoint | Method | İşlev |
|---|---|---|
| `POST /api/face/analyze` | POST | Klip yükle ve face analiz başlat (form-data: `file`, `content_type?`, `profile?`) |
| `GET /api/face/jobs/{job_id}` | GET | Job durumu + sonuç özeti |
| `GET /api/face/jobs/{job_id}/events` | GET | Job log entries |

### Bank

| Endpoint | Method | İşlev |
|---|---|---|
| `GET /api/face/bank/persons` | GET | Kişi listesi (`?q=`, `?category=`, `?limit=`, `?offset=`) |
| `GET /api/face/bank/persons/{person_id}` | GET | Detay + sample'lar + audit |
| `POST /api/face/bank/persons` | POST | Yeni kişi (body: `{display_name, category, organization, kvkk_consent_basis, ...}`) |
| `POST /api/face/bank/persons/{person_id}/samples` | POST | Manuel foto upload (form-data + `source_provenance`) |
| `POST /api/face/bank/samples/{sample_id}/deactivate` | POST | Sample deactive |
| `POST /api/face/bank/persons/{primary_id}/merge` | POST | İki kişiyi birleştir (body: `{secondary_id, reason}`) |
| `POST /api/face/bank/persons/{person_id}/kvkk-delete` | POST | KVKK silme talebi |
| `POST /api/face/bank/seed` | POST | Bulk import (multipart: persons.json + photos) |

### Review

| Endpoint | Method | İşlev |
|---|---|---|
| `GET /api/face/review/queue` | GET | Review queue (`?bucket=high,medium`) |
| `POST /api/face/review/confirm` | POST | Cluster → person bağla |
| `POST /api/face/review/reject` | POST | Cluster reddet |
| `POST /api/face/matches/{match_id}/reject` | POST | Auto-match'i reddet |

### Admin

| Endpoint | Method | İşlev |
|---|---|---|
| `GET /api/face/admin/audit` | GET | Audit log (filter: actor, action, target, time range) |
| `POST /api/face/admin/retention/run` | POST | Retention scheduler manuel tetik |
| `POST /api/face/admin/config` | POST | Threshold/config değişikliği (audit_log + config_versions yazar) |
| `GET /api/face/admin/health` | GET | DB + model + worker durumu |

### Showcase (Live Track Demo)

| Endpoint | Method | İşlev |
|---|---|---|
| `POST /api/face/demo/track/start` | POST | Live Track Demo başlat (worker'ı pause eder) |
| `POST /api/face/demo/track/select` | POST | Ekrandaki yüzlerden birini seç (track_id) |
| `POST /api/face/demo/track/stop` | POST | Stop, worker resume |
| `WS /api/face/demo/track/stream` | WebSocket | Frame + bbox + track_id akışı |

**Kritik kurallar:**
- Embedding vector hiçbir endpoint response'unda dönmez.
- Sadece similarity score gösterilir.
- KVKK silme cascade tüm endpoint'lerden geçer.

---

## 11. Review UI ve FaceBank Builder

Mevcut webui (E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui) iki sekmeli. Face ekranları **FaceBank Builder** sekmesi altında üç alt-sekme:

### 11.1 BankManagementTab

- Kişi listesi (autocomplete arama, kategori filter)
- Kişi detayı (sample grid, audit timeline, görüldüğü klipler)
- Yeni kişi modal (display_name, category, organization, kvkk_consent_basis zorunlu prod'da)
- Sample upload modal (foto + source_provenance JSON form)
- Sample deactivate (reason)
- Merge persons (primary + secondary + reason)
- KVKK delete (admin only, request_id + scope)

### 11.2 UnknownReviewTab

- Sol: queue (bucket sıralı; high üstte)
- Orta: seçili cluster'ın 3-5 temsilci crop'u
- Sağ: meta (clip, zaman aralığı, screen_time, ASR overlap, KJ text varsa)
- Alt: Cross-video strip ("bu yüz şu 6 yayında geçti")
- Aksiyonlar: `Bu kişi: <search/create>`, `Reddet`, `Sonra`

### 11.3 MatchConfirmationTab

- Liste: clip + zaman + match person + score + crop
- Quick action: `Onayla`, `Yanlış eşleşme`, `Bu cluster aslında: <search>`

### 11.4 UI Status vocabulary (master plan §1.3)

`raw`, `auto`, `needs_review`, `confirmed`, `rejected`, `ignored`, `failed`, `skipped`, `low_confidence`.

---

## 12. KVKK, Audit, Güvenlik

### 12.1 Erişim seviyeleri

| Rol | İzinler |
|---|---|
| `viewer` | sadece okuma; embedding ve sample crop görmez |
| `reviewer` | review confirm/reject + manuel person create + sample upload |
| `admin` | tümü + person delete (KVKK) + merge + threshold + retention manuel trigger |

v0.4'te `actor=local_dev` veya `FACE_OPERATOR_ID` env'inden alınır. Rol enforcement v1.x.

### 12.2 KVKK silme prosedürü

1. Yazılı talep (request_id, requested_at, scope, legal_basis).
2. `POST /api/face/bank/persons/{person_id}/kvkk-delete` body: yukarıdaki alanlar.
3. Backend kaskad:
   - `face_samples` is_active=false + crop dosyaları **fiziksel sil**.
   - `person_centroids` SİL.
   - `persons.display_name → "[KVKK_DELETED_<request_id>]"`, aliases [], deleted_at set.
   - Geçmiş timeline event'lerde `person_id` korunur (audit), UI'da display_name redacted gösterir.
   - `audit_log`: action="kvkk_deletion_request", reason JSON `{kvkk_request_id, requested_at, scope, legal_basis}`.
4. 30 gün içinde talep sahibine yazılı bildirim.

### 12.3 Retention scheduler

Günlük 03:00:
- Unknown cluster: `retention_expires_at < now()` AND status ∈ `{pending_review, rejected}` → crop sil, embedding null, status=expired, audit "retention_expire".
- Audit log: 1 yıldan eski entry'lerde `before_state/after_state/ip_or_session` null, `reason="[REDACTED_RETENTION]"`.

Manuel tetik: `POST /api/face/admin/retention/run`.

### 12.4 Audit log actions

`create_person`, `delete_person`, `merge_persons`, `add_sample`, `deactivate_sample`, `promote_unknown`, `reject_unknown`, `match_rejected`, `threshold_change`, `kvkk_deletion_request`, `retention_expire`, `showcase_start`, `showcase_end`, `config_load`.

### 12.5 Güvenlik özet

- Lokal network. Internet outbound kapalı (no-internet model cache).
- DB credential `.env`; production'da Vault/keyring.
- HTTPS production'da reverse proxy (nginx/caddy).
- CORS: dev `5173` + production origin'leri; wildcard yok.
- File upload limit: foto 10 MB, video 5 GB (configurable).
- `outputs/face_bank/` Windows ACL kısıtlı.
- **Embedding export endpoint yok.** Debug için admin SQL erişim.

### 12.6 Showcase (Live Track Demo) güvenliği

- Embedding üretmez, banka yazmaz, KVKK riski düşük.
- GPU exclusivity: showcase başlarken worker pause.
- Audit log: showcase_start + showcase_end.
- RAM-only: crop saklanmaz, DB kayıt yok.

---

## 13. Test ve Benchmark Planı

### 13.1 Unit testler (80+ hedef)

`tests/face/test_face_*.py` — quality gate, crop selector, alignment, importance scorer, matcher, repository, audit, retention, kvkk_delete, config loader, engine protocols.

### 13.2 Integration testler (20+ hedef)

`tests/face/test_face_pipeline_*.py` — e2e (news clip), film mode, partial fail, OOM, seed bulk import, review flow, cross-video unknown merge, showcase pauses worker, re-embed v1→v2.

### 13.3 E2E Smoke (golden output)

`tests/face/test_face_pipeline_smoke.py`:
- Fixture: `small_news_clip.mp4` (15-20 sn, 2 sunucu, 1 KJ)
- Çalıştır → `face_summary.json`, `face_clusters.json`, `face_events.json`, `face_quality_report.json` golden ile karşılaştır
- Tolerans: cluster_id deterministic değil ama count, sizes, time aralıkları match etmeli

### 13.4 Mini benchmark seti (v0.4 release için 8 saat)

- 5 saat haber/panel
- 1 saat müzik
- 1 saat belgesel
- 1 saat film

Ground truth: bilinen kişilerin doğru tanınması (~50-100 etiket).

### 13.5 Metrikler (`face_benchmark.yaml` TBD doldurulur)

| Metrik | Hedef |
|---|---:|
| false_match_rate | < 2% |
| missed_face_rate | < 5% |
| cluster_purity | > 0.85 |
| important_person_miss_rate | < 5% |
| runtime_per_minute | < 35 (1h klip < 35 dk) |
| vram_peak_mb | < 6 GB |

### 13.6 Threshold kalibrasyon

`scripts/face_threshold_calibration.py` (worker job tipi `benchmark_v0_4_face_calibration`):
- 8 saatlik set
- `auto_threshold ∈ [0.80, 0.95]` × `review_threshold ∈ [0.65, 0.80]` 5×5 grid
- Pareto front analizi
- `outputs/face_calibration/pareto_v1.json` + `.md`
- FMR ≤ 2% AND MFR ≤ 5% en geniş aralık → eşik sabitlenir, config'e ve audit_log'a yazılır.

### 13.7 KVKK doğrulama testleri

- Production mode'da empty `kvkk_consent_basis` → reddedilir
- Person KVKK delete → crop fiziksel silinmiş, samples is_active=false, display_name redacted
- Unknown 30 gün sonra retention → status=expired
- Audit log 1 yıl sonra `before/after` null
- Embedding API response'unda görünmüyor (contract test)

### 13.8 Performans testleri

- 1 saatlik 1080p haber: full pipeline < 35 dk
- Aynı film mode: < 25 dk
- pgvector 10k embedding lookup: < 10 ms
- Seed bulk import 100×10: < 2 dk
- VRAM peak: < 6 GB
- Retention job 1000 expired: < 30 sn

### 13.9 WebUI smoke

- `npm run build` + `tsc --noEmit` pass
- FaceBank Builder sekmesi açılıyor
- 5 kişilik seed listesi gösteriliyor
- Unknown review queue cluster card gösterimi
- Match confirmation butonları

---

## 14. Kabul Kriteri (v0.4 release)

- [ ] 80+ unit test, 100% pass (mock model)
- [ ] 20+ integration test, 100% pass (docker pgvector)
- [ ] E2E smoke (golden output) pass
- [ ] Mini benchmark (8 saat) tamamlandı, raporlandı
- [ ] Threshold kalibrasyon Pareto front, eşikler config'te ve audit_log'da
- [ ] `benchmark_templates/face_benchmark.yaml` TBD alanları dolu
- [ ] KVKK doğrulama testleri 100% pass
- [ ] WebUI FaceBank Builder + smoke
- [ ] Performans hedefleri (1 saatlik klip < 35 dk) gerçek klipte doğrulandı
- [ ] Sprint dokümanı: `docs/SPRINT_5_FACE_V0_4_DONE.md`
- [ ] Production lisans/KVKK askıda kararları operasyonel olarak `FACE_APP_ENV=development` ile kapsam dışı

---

## 15. İmplementasyon Sırası (7 hafta)

| Hafta | İçerik |
|---|---|
| 1 | PostgreSQL + pgvector kurulum, face venv eksik paketler, alembic init, face_bank schema migration, smoke import |
| 1-2 | Engine sınıfları (SCRFD, ByteTrack), Stage 0-3, unit testler |
| 2-3 | Stage 4-6 (quality gate, crop selector, alignment+embedding, intra-track stability, HDBSCAN), unit testler |
| 3 | Bank repository (persons, samples, centroids, audit), seed bulk import, CRUD testler |
| 3-4 | Stage 7-9 (bank match, importance, event emit + CandidateRelation), graceful degradation testler |
| 4 | Stage 10-12, worker entegrasyonu, system event |
| 4-5 | FastAPI routes, FaceBank Builder webui component'leri |
| 5 | Retention scheduler, KVKK delete prosedürü, audit log retention |
| 5-6 | Showcase (Live Track Demo) backend + frontend |
| 6 | Seed yükleme (50-100 kişi), 8 saatlik benchmark seti hazırlama |
| 6-7 | Threshold kalibrasyon Pareto front, eşikleri sabitleme, sprint dokümanı |

---

## 16. Risk Listesi

| Risk | Etki | Azaltma |
|---|---|---|
| buffalo_l lisans red | Production blok | Dev mode'da devam; fallback: ArcFace açık ağırlık + SCRFD bağımsız |
| KVKK retention onayı gecikme | Production deploy blok | Dev mode'da geliştirme; hukuk paralel |
| TRT seed listesi gelmiyor | Banka match çalışmaz | Dev seed (5-10 kişi) ile başla; gerçek seed sonra |
| pgvector performans (50k+) | Lookup yavaş | HNSW index'e geçiş hazır |
| ByteTrack kalabalık | False track ID | BoT-SORT fallback (engine pattern) |
| ArcFace TR yüz | False match yüksek | Threshold kalibrasyon + seed büyütme |
| Eski arşiv (interlaced) | Banka match düşük | Quality gate atar, unknown cluster oluşur |
| GPU OOM | Pipeline fail | load/unload yaşam döngüsü + retry |

---

## 17. Açık Sorular (operatör cevabı bekleyen)

| ID | Soru | Cevap kanalı |
|---|---|---|
| OQ-1 | PostgreSQL kurulu mu? Docker mı native mi? | Geliştirici |
| OQ-2 | FaceBank Builder UI sözleşme uyumu (mevcut webui ile) | Geliştirici + UI cephesi |
| OQ-3 | `buffalo_l` lisans onayı + fallback alternatifi | TRT hukuk/yayın hakları |
| OQ-4 | Seed kişi listesi kim sağlayacak? 50-100 kişi seçim kriteri | TRT içerik/arşiv ekibi |
| OQ-5 | Film `face_presence` event tipi adı onayı | Geliştirici |
| OQ-6 | Audit log retention süresi (1 yıl önerisi) | TRT hukuk/KVKK |
| OQ-7 | Showcase + final GPU exclusivity (tek slot worker önerisi) | Geliştirici |

---

## Ekler

### A. Önerilen TimelineEvent şemaları (face-spesifik payload)

```json
// face_presence
{
  "event_type": "face_presence",
  "module": "face",
  "start_sec": 12.4,
  "end_sec": 19.6,
  "payload": {
    "track_id": "face_track_044",
    "cluster_id": "face_cluster_A4",
    "det_conf_avg": 0.92,
    "bbox_avg": [420, 180, 612, 410],
    "quality_score": 0.87,
    "frame_count": 38
  },
  "confidence": 0.87,
  "status": "raw"
}

// face_cluster_appearance
{
  "event_type": "face_cluster_appearance",
  "module": "face",
  "start_sec": 12.4,
  "end_sec": 25.0,
  "payload": {
    "cluster_id": "face_cluster_A4",
    "total_screen_time_ms": 12600,
    "member_tracks_count": 2,
    "importance_score": 0.71,
    "bucket": "high",
    "match": {
      "person_id": "person_001021",
      "score": 0.87,
      "decision": "auto_matched"
    }
  },
  "confidence": 0.71,
  "status": "raw"
}
```

### B. CandidateRelation şablonları

```json
{
  "relation_type": "face_matches_kj_name_candidate",
  "entity_a": {"type": "face_cluster", "id": "face_cluster_A4"},
  "entity_b": {"type": "kj_text", "id": "ocr_evt_000311"},
  "confidence": 0.82,
  "source_signals": ["face_overlap", "ocr_lower_third"],
  "evidence_ids": ["face_evt_812", "ocr_evt_311"],
  "status": "raw"
}

{
  "relation_type": "speaker_overlaps_face_candidate",
  "entity_a": {"type": "face_cluster", "id": "face_cluster_A4"},
  "entity_b": {"type": "speaker_id", "id": "SPEAKER_01"},
  "confidence": 0.74,
  "source_signals": ["face_overlap", "asr_speaker_turn"],
  "evidence_ids": ["face_evt_812", "asr_evt_120"],
  "status": "raw"
}
```

### C. Karar günlüğü referansı

Plan inşa sürecinde verilen kararlar `docs/MITAS_v0_4_Face_Recognition_Plan_Journey.md` §8.1'de listelendi:

- `DEC-FACE-J-001` Modüler venv + Showcase namespace
- `DEC-FACE-J-002` Pre-Scan profile-conditional + intra-track variance + threshold config
- `DEC-FACE-J-003` source_provenance + production-mode constraint + cross-video config + re-embed
- `DEC-FACE-J-004` Film modu Stage 4 dahil + Pareto kalibrasyon
- `DEC-FACE-J-005` Unified alembic + E2E smoke + vite proxy
- `DEC-FACE-J-006` Embedding gizleme + KVKK JSON şablonu + person_id korunur display_name redacted
- `DEC-FACE-J-007` Benchmark worker job tipi + drift testi v1.x

---

**Bu plan v0.4 dikey diliminin uygulanabilir tek kaynağıdır. Codex/Sonnet'e verildiğinde aşağıdaki sırayla uygulanır:**

1. Bölüm 8 — Setup (10 adım)
2. Bölüm 9 — Dizin/kod yapısı oluştur
3. Bölüm 3 — Stage'leri sırayla implement et (unit testle birlikte)
4. Bölüm 4 — DB schema (alembic migration)
5. Bölüm 5 — Seed + öğrenme döngüsü endpoint'leri
6. Bölüm 10 — Backend API
7. Bölüm 11 — WebUI component'leri
8. Bölüm 12 — KVKK + retention + audit
9. Bölüm 13 — Test + benchmark
10. Bölüm 14 — Kabul kriteri kontrolü

Plan **kod yazmaz**, **karar verir**. Implementasyon Codex/Sonnet'in işidir.
