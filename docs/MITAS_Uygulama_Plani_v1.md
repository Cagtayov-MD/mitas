# MITAS Uygulama Planı v1

**Durum:** İlk uygulama planı  
**Temel alınan master:** MITAS_Master_Plan_Denetimli_v5.md  
**Amaç:** Master plandaki kararları kodlamaya geçmeden önce uygulanabilir iş sırasına çevirmek.  
**Kapsam:** Bu doküman şu an yalnızca ilk 3 sprinti detaylandırır. Sonraki sprintler başlık olarak tutulur ve ilerleyen aşamalarda tek tek açılır.

---

## 0. Ana İlke

MITAS’ta önce model kurulumu veya video analizi yapılmayacak. Önce sistemin omurgası kurulacak:

1. Ortak veri sözleşmesi
2. Job / background worker akışı
3. Benchmark ve test seti planı

Bu üç temel kurulmadan model benchmarkına veya vertical slice’a geçilmeyecek.

---

# 1. Sprint 1 — Core Schema

## 1.1 Amaç

MITAS modüllerinin tamamının aynı veri dilini konuşmasını sağlamak.

ASR, OCR/KJ, Audio Activity, Face, Visual Tag ve ileride FilmCreditsParser aynı temel event yapısını kullanacak. Böylece her modül kendi keyfi JSON formatını üretmeyecek.

## 1.2 Neden kritik?

VITOS benzeri eski problemlerden biri, modüllerin ve parser’ların aynı sözleşmeye bağlı çalışmamasıydı. MITAS’ta bu hata tekrar edilmeyecek.

Yanlış örnek:

```json
{
  "start": "00:12:10",
  "end": "00:13:34",
  "confidence": "yüksek"
}
```

Doğru yaklaşım:

```json
{
  "event_type": "song_performance",
  "start_time": 730.0,
  "end_time": 814.0,
  "confidence": 0.86,
  "status": "needs_review"
}
```

Zaman alanları saniye cinsinden `float` olacak. Confidence 0.0–1.0 arası olacak. Status enum olacak. Bu kurallar Pydantic Strict modellerle korunacak.

## 1.3 Bu sprintte oluşturulacak modeller

### 1.3.1 MediaItem

İşlenen medya dosyasını temsil eder.

Zorunlu alanlar:

```text
media_id
file_path
duration_sec
fps
width
height
created_at
```

### 1.3.2 TimelineEvent

Timeline’a yazılan bütün eventlerin ortak gövdesidir.

Zorunlu alanlar:

```text
event_id
media_id
event_type
subtype
start_time
end_time
confidence
status
source_module
payload
evidence_ids
created_at
```

İlk event_type değerleri:

```text
asr_segment
screen_text
audio_activity
song_announcement
song_recognition_match
song_performance
face_track
face_cluster
visual_tag
credit_event
system_event
```

İlk status değerleri:

```text
auto
needs_review
confirmed
rejected
ignored
failed
partial
```

### 1.3.3 Evidence

Bir event’in hangi kanıta dayandığını gösterir.

Zorunlu alanlar:

```text
evidence_id
media_id
source_module
time_sec
frame_id
artifact_path
text
bbox
confidence
metadata
created_at
```

Not: `artifact_path` sadece kalıcı saklanacak evidence/review parçalarını gösterecek. Geçici frame/crop/audio chunk burada kalıcı evidence yapılmayacak.

### 1.3.4 CandidateRelation

Kesin kimlik veya kesin metadata değildir. Modüller arası aday ilişkiyi tutar.

Örnekler:

```text
KJ adı ↔ yüz cluster
ASR speaker_id ↔ face track
KJ/ASR ↔ song_performance
fingerprint ↔ song_candidate
screen_text ↔ face_track
```

Zorunlu alanlar:

```text
relation_id
media_id
entity_a_type
entity_a_id
entity_b_type
entity_b_id
relation_type
confidence
source_signals
evidence_ids
status
created_by_module
created_at
```

İlk relation_type değerleri:

```text
face_matches_kj_name_candidate
speaker_overlaps_face_candidate
kj_mentions_song_candidate
asr_supports_song_candidate
fingerprint_supports_song_candidate
screen_text_context_for_face
visual_tag_context_for_scene
```

Kural:

```text
CandidateRelation hiçbir zaman kesin identity olarak yazılmaz.
Kesinleşme için review veya daha güçlü doğrulama gerekir.
```

### 1.3.5 JobRun

Bir işin hangi adımda olduğunu takip eder.

Zorunlu alanlar:

```text
job_id
media_id
pipeline_name
step_name
status
started_at
completed_at
retry_count
error_msg
input_artifacts
output_artifacts
last_successful_step
```

Status değerleri:

```text
pending
running
done
failed
partial
cancelled
skipped
```

### 1.3.6 ModuleRun

Her modül çalışmasının özetidir.

Zorunlu alanlar:

```text
module_run_id
job_id
media_id
module_name
module_version
model_name
model_version
status
started_at
completed_at
runtime_sec
gpu_used
vram_peak_mb
error_msg
output_summary
```

## 1.4 Oluşturulacak dosyalar

Codex’in üretmesi beklenen ilk dosyalar:

```text
core/
  schemas/
    __init__.py
    common.py
    media.py
    timeline.py
    evidence.py
    candidate_relation.py
    job_run.py
    module_run.py

scripts/
  export_json_schema.py

schemas/
  timeline_event.schema.json
  evidence.schema.json
  candidate_relation.schema.json
  job_run.schema.json
  module_run.schema.json

tests/
  test_schema_timeline.py
  test_schema_evidence.py
  test_schema_candidate_relation.py
  test_schema_job_run.py
  test_schema_module_run.py
```

## 1.5 Kabul kriterleri

Bu sprint tamam sayılmak için:

```text
Geçerli örnek JSON’lar kabul edilecek.
Hatalı örnek JSON’lar reddedilecek.
start_time / end_time string verilirse hata alınacak.
confidence 0.0–1.0 dışında verilirse hata alınacak.
status enum dışı verilirse hata alınacak.
CandidateRelation evidence_ids olmadan high confidence veremeyecek.
JSON Schema export alınacak.
pytest testleri geçecek.
```

## 1.6 Codex’e verilecek görev özeti

```text
MITAS V5’e göre Core Schema sprintini uygula.

Model veya video analizi yazma.
Sadece Pydantic v2 strict modelleri, JSON Schema export ve pytest testleri yaz.

Oluştur:
- MediaItem
- TimelineEvent
- Evidence
- CandidateRelation
- JobRun
- ModuleRun

Kurallar:
- Pydantic v2 kullan.
- Strict validation kullan.
- start_time/end_time saniye cinsinden float.
- confidence 0.0–1.0 arası.
- status ve event_type enum.
- payload dict olabilir ama base alanlar strict olacak.
- JSON Schema export script’i yaz.
- valid ve invalid örnek testleri yaz.
```

---

# 2. Sprint 2 — Job / Background Worker

## 2.1 Amaç

Video analiz işlerinin nerede başladığını, hangi adımda olduğunu, nerede patladığını ve nereden devam edebileceğini takip etmek.

Bu sprintte ağır queue mimarisi kurulmayacak. Celery hedef değil. V1 için sade yaklaşım yeterli:

```text
DB job table + single background worker
veya
RQ + Redis
```

## 2.2 Neden kritik?

MITAS işleri uzun sürecek. Örnek:

```text
ASR uzun sürebilir.
OCR/KJ uzun sürebilir.
Face analiz uzun sürebilir.
Visual Tag uzun sürebilir.
```

Bu işler kullanıcı arayüzünü bloke etmemeli. Ayrıca iş yarıda çökerse sistem en son başarılı adımdan devam edebilmeli.

## 2.3 Job status standardı

Kullanılacak status değerleri:

```text
pending
running
done
failed
partial
cancelled
skipped
```

## 2.4 Hata yönetimi kuralları

```text
Transient error için 1 otomatik retry.
OOM için otomatik retry yok; failed_resource_limit yazılır.
Validation fail için failed_invalid_output yazılır.
Bir modül fail olsa bile önceki valid çıktılar korunur.
Partial result kabul edilir ama açık status ile işaretlenir.
```

## 2.5 Minimal job_runs tablo taslağı

```text
job_id
media_id
pipeline_name
step_name
status
started_at
completed_at
retry_count
error_msg
input_artifacts
output_artifacts
last_successful_step
```

## 2.6 Basit worker akışı

```text
1. pending job bul
2. status = running yap
3. step çalıştır
4. çıktı doğrula
5. başarılıysa done
6. hata varsa failed / partial
7. retry_count güncelle
8. last_successful_step yaz
```

## 2.7 Kabul kriterleri

Bu sprint tamam sayılmak için:

```text
Dummy job pending → running → done akışından geçecek.
Dummy failed job failed olarak yazılacak.
retry_count artacak.
last_successful_step tutulacak.
partial result örneği üretilecek.
pytest testleri geçecek.
```

## 2.8 Codex’e verilecek görev özeti

```text
MITAS V5’e göre Job / Background Worker sprintini uygula.

Ağır pipeline yazma.
Model çalıştırma.
Video analizi yazma.

Oluştur:
- JobRun schema kullanarak job state yönetimi
- basit in-memory veya sqlite/postgres uyumlu job repository taslağı
- dummy worker
- dummy step runner
- retry / failed / partial örnekleri
- pytest testleri

Status:
pending, running, done, failed, partial, cancelled, skipped

Hata türleri:
failed_resource_limit
failed_invalid_output
failed_runtime_error
```

---

# 3. Sprint 3 — Benchmark / Test Set Planı

## 3.1 Amaç

Model seçimlerini hissiyata değil, ölçülebilir benchmarklara bağlamak.

Bu sprintte model kurulumu yapılabilir ama ana amaç kurulum değildir. Ana amaç hangi modelin hangi test setiyle, hangi metrikle, hangi geçer/kalır eşiğiyle değerlendirileceğini belirlemektir.

## 3.2 Minimum test seti

V1 öncesi minimum test seti:

```text
20 saat toplam
- 5 saat haber/panel KJ
- 5 saat müzik programı
- 5 saat belgesel/intertitle
- 5 saat film/jenerik
```

V1 sonrası genişletme hedefi:

```text
100 saat
```

## 3.3 Sahiplik

Bu sprintte şu iki rol atanmalıdır:

```text
Test Set Owner
Ground Truth Owner
```

Bu iki rol atanmadan benchmark kapanmış sayılmaz.

## 3.4 Benchmark şablonu

Her benchmark için şu alanlar doldurulacak:

```text
benchmark_id
benchmark_name
module
models_or_tools
test_video_set
ground_truth_owner
metric_list
pass_fail_threshold
target_week
responsible_person_or_team
final_decision
decision_date
notes
```

## 3.5 İlk benchmark listesi

### 3.5.1 OCR/KJ benchmark

Amaç:

```text
OneOCR, PaddleOCR, VITOS baseline, EasyOCR, Tesseract karşılaştırması.
```

Metrikler:

```text
KJ line accuracy
Türkçe karakter doğruluğu
ROI-first başarı oranı
temporal merge başarısı
runtime per minute
false positive oranı
```

Öncelik sırası:

```text
1. OneOCR
2. PaddleOCR / PP-OCRv5 multilingual
3. VITOS baseline
4. EasyOCR
5. Tesseract
```

### 3.5.2 ASR benchmark

Amaç:

```text
faster-whisper large-v3 ana motor
distil-large-v3 / medium fallback
WhisperX timestamp doğruluğu
```

Metrikler:

```text
WER
timestamp drift
word-level alignment success
runtime per minute
VRAM usage
```

### 3.5.3 Audio Activity benchmark

Amaç:

```text
speech / music / applause / silence ayrımı.
```

Metrikler:

```text
music segment precision
music segment recall
speech/music boundary error
runtime per minute
```

### 3.5.4 Face benchmark

Amaç:

```text
SCRFD / ArcFace / HDBSCAN akışında kalite kapılarını test etmek.
```

Başlangıç eşikleri:

```text
min_face_height: 80 px
blur_laplacian_min: 100
pose_yaw_max: 30°
pose_pitch_max: 25°
min_track_duration: 1.5 sn
min_detector_confidence: 0.70
```

Metrikler:

```text
false match rate
missed face rate
cluster purity
review yükü
runtime per minute
```

### 3.5.5 Visual Tag benchmark

Amaç:

```text
YOLO-World / SigLIP kontrollü tag üretimini test etmek.
```

Metrikler:

```text
tag precision
tag recall
scene-level voting success
false positive oranı
runtime per minute
```

## 3.6 Kabul kriterleri

Bu sprint tamam sayılmak için:

```text
Benchmark tablosu oluşturulacak.
Minimum 20 saatlik test seti kategorileri belirlenecek.
Test Set Owner atanacak.
Ground Truth Owner atanacak.
Her benchmark için metrik ve geçer/kalır alanı olacak.
Model kurulumuna geçmeden önce hangi benchmarkın blocking olduğu işaretlenecek.
```

## 3.7 Codex’e verilecek görev özeti

```text
MITAS V5’e göre Benchmark / Test Set Planı taslağı oluştur.

Model çalıştırma yok.
Benchmark koşma yok.
Sadece plan ve tablo yapısı oluştur.

Oluştur:
- docs/MITAS_Benchmark_Plani_v1.md
- benchmark_registry.yaml
- benchmark_templates/
  - ocr_kj_benchmark.yaml
  - asr_benchmark.yaml
  - audio_activity_benchmark.yaml
  - face_benchmark.yaml
  - visual_tag_benchmark.yaml

Her benchmark dosyasında:
- models_or_tools
- test_video_set
- metrics
- pass_fail_threshold
- owner
- target_week
- decision_status
alanları olsun.
```

---

# 4. Sonraki Sprintler — Şimdilik Başlık Düzeyinde

Bu sprintler şimdi detaylandırılmayacak. İlk 3 sprint tamamlandıktan sonra sırayla açılacak.

## 4.1 Sprint 4 — OCR/KJ + Audio Activity Vertical Slice

Hedef:

```text
KJ yazısını oku.
Audio activity ile music/speech aralığını bul.
Timeline’a screen_text ve audio_activity event yaz.
```

## 4.2 Sprint 5 — ASR Bağlantısı

Hedef:

```text
ASR transcript’i timeline’a bağla.
KJ/anons ile ASR destek sinyali üret.
```

## 4.3 Sprint 6 — song_performance Event Üretimi

Hedef:

```text
KJ + ASR + Audio Activity sinyalleriyle song_performance event üret.
```

## 4.4 Sprint 7 — Face Showcase / Face Review

Hedef:

```text
Showcase: ekrandaki yüzü seç ve takip et.
Review: unknown face / face match doğrulama.
```

## 4.5 Sprint 8 — Visual Tag Entegrasyonu

Hedef:

```text
Scene detect + keyframe + YOLO-World/SigLIP ile visual_tag event üret.
```

## 4.6 Sprint 9 — FilmCreditsParser Ayrı İş Paketi

Hedef:

```text
Akan/durağan/giriş/kapanış jeneriğini ayrı kontrollü iş paketi olarak detaylandır.
```

---

# 5. Şimdilik Açılmayacak Konular

Aşağıdaki konular önemli ama bu dokümanın ilk sürümünde detaylandırılmayacak:

```text
Local fingerprint DB
VLM review helper
Gelişmiş Türkçe morfoloji
Visual tag review ekranı
FilmCreditsParser review ekranı
pgvector HNSW tuning
Celery / dağıtık queue
100 saatlik geniş test seti
full model VRAM tuning
```

Bu konular V1’i bloke etmeyecek. Gerekli olanlar ilgili planlarda opsiyonel/ileriki faz olarak takip edilecek.

---

# 6. İlk Uygulama Kararı

Bu dokümandan sonra ilk Codex görevi:

```text
Sprint 1 — Core Schema
```

Model kurulumu, video analizi, OCR, ASR veya Face çalıştırma henüz yapılmayacak.

İlk hedef:

```text
Pydantic Strict schema + JSON Schema export + pytest valid/invalid testleri
```

---

# 7. Kaynak Notları

- Pydantic Strict Mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
- Pydantic JSON Schema: https://docs.pydantic.dev/latest/concepts/json_schema/
- RQ Workers: https://python-rq.org/docs/workers/
