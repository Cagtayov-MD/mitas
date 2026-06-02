# 15 — KJ Ekran Tarama Servisi — GPT Uygulama Talimatı

**Tarih:** 2026-05-23
**Uygulayıcı:** GPT (Sonnet alt-ajanı)
**Repo:** `E:\MITAS` (Windows, PowerShell, master branch)

---

## Bağlam (oku, geç)

TRT arşivinde ekrana yakılmış (burned-in) kişi altbantları — KJ — bir program/belgesel/stüdyo kaydı boyunca **anlık olarak belirir, 2-4 saniye kalır, bazen hafif kıpırdar, gider**.

Görev: **bağımsız bir KJ tarama servisi** kur. Bu servis:
- ASR'a bağlı **değil**. ASR çalışmıyorken de çalışır.
- Bir video alır, **düşük FPS ile (1 fps başlangıç) sürekli tarar**, KJ'leri yakalar, JSON döndürür.
- Sonradan ASR sonucuyla **birleştirilebilir** ama bu işin **kapsam dışı**.
- Her videoda otomatik çalışmaz. Tetikleme kullanıcı/batch tarafından yapılır (Aşama 3).

**Tarama alanı (sabit, ileride değişebilir):** Ekranın **orta %90'ı** (y ekseninde 0.05–0.95). Üst %5 ve alt %5 göz ardı edilir (logo, kanal saati, ticker, watermark bölgeleri).

**Panel/şerit:** KJ'lerin çoğunda arka panel olur. Olmayan örnekler de gelecek. Panel **zorunlu değil, sadece bonus sinyal**. Tespit ensemble (çoklu sinyal) ile çalışır, hiçbir sinyal tek başına karar vermez.

---

## Mimari — Bağımsız servis

```
core/pipelines/kj/                           # YENİ paket (ASR'dan bağımsız)
  ├─ __init__.py
  ├─ dictionaries.py                         # YAML loader
  ├─ parser.py                               # OCR satırları → {name, title, role, organization}
  ├─ rescue.py                               # qwen35local LLM rescue
  ├─ event_detector.py                       # KJ event tespiti (ensemble skor)
  └─ scanner.py                              # Servis giriş noktası: video → kj_scan_result.json

config/kj_dictionaries.yaml                  # Türkçe unvan/kurum/reject sözlükleri
config/kj_scanner.yaml                       # Servis konfigürasyonu (FPS, ROI, eşikler)

scripts/kj_scan.py                           # CLI: tek video veya klasör tara
scripts/evaluate_kj_parser.py                # Aşama 1 gate
scripts/evaluate_kj_events.py                # Aşama 2 gate

core/api/kj_router.py                        # YENİ — FastAPI router: /api/kj/scan
```

**Hiçbir mevcut ASR/OCR dosyasına `import core.pipelines.kj` yazılmaz.** Bu servis kendi yolunda çalışır. ASR pipeline'ı değiştirilmez.

---

## YAPILACAKLAR — Aşama 0 (Dataset Profilleme)

**Hedef:** Çağatay'ın vereceği KJ golden set'i açıp **eşikleri veriden öğren**. Plan içindeki tüm "0.45 skor eşiği", "panel skor ağırlığı", "minimum süre" gibi rakamlar bu adımda **veriden gelir**, modellerden değil.

### 0.1 — Dataset'i yerleştir

Çağatay şu dosyaları sağlayacak:
- `tests/fixtures/kj_golden_set.json` — parser golden set (raw OCR satırları + beklenen JSON)
- `tests/fixtures/kj_video_segments/` — event detector için video kesitleri (panel'li ve panel'siz örnekler dahil)
- `tests/fixtures/kj_video_segments_manifest.yaml` — her kesit için: video_path, start, end, beklenen KJ event listesi (start/end/name/role/organization)

### 0.2 — Profilleme scripti

Yeni dosya: `scripts/profile_kj_dataset.py`.

Yapacağı iş:
- Her golden KJ event için **şu metrikleri ölç ve dağılımını çıkar**:
  - `y_center_ratio`, `y_top_ratio`, `y_bottom_ratio` (KJ'nin ekrandaki dikey konumu)
  - `width_ratio`, `height_ratio`
  - `duration_seconds`
  - `line_count`
  - Panel var/yok (manuel etiket, manifest'ten)
  - OCR confidence (PaddleOCR çalıştırıp ölç)
  - Frame-to-frame motion (px/s)
- Çıktı: `outputs/kj_dataset_profile.json`
  - Her metrik için: `min, p5, p25, median, p75, p95, max, mean, std`
  - Panel'li vs panel'siz alt dağılımları ayrı

Bu çıktıdan eşikler türetilir:
- `min_duration_sec` ≈ `duration.p5`
- `max_duration_sec` ≈ `duration.p95 * 1.3`
- Panel skor ağırlığı = panel'li/panel'siz F1 farkına göre

**Bu adım Aşama 1 başlamadan tamamlanmalı.** Aksi halde parser/event detector eşiklerini yine uyduracağız.

### 🚦 AŞAMA 0 GATE

```powershell
.\venvs\core\Scripts\python.exe scripts\profile_kj_dataset.py `
    --golden tests\fixtures\kj_golden_set.json `
    --segments tests\fixtures\kj_video_segments_manifest.yaml `
    --output outputs\kj_dataset_profile.json
```

**Geçer:** `outputs/kj_dataset_profile.json` üretilmiş ve Çağatay tarafından gözden geçirilmiş. Eşikler insan-okunur özet halinde `outputs/kj_dataset_profile_summary.md`'ye yazılmış.

---

## YAPILACAKLAR — Aşama 1 (Parser + Sözlük + Rescue)

**Hedef:** OCR'dan gelmiş ham satırları structured KJ'ye çeviren standalone parser. Gate: golden set üzerinde **field-level F1 ≥ %85**.

### 1.1 — `config/kj_dictionaries.yaml`

```yaml
schema_version: 1

turkish_titles:
  - "PROF DR"
  - "PROF. DR."
  - "DOÇ DR"
  - "DOÇ. DR."
  - "DR ÖĞR ÜYESİ"
  - "DR. ÖĞR. ÜYESİ"
  - "DR"
  - "AV"
  - "AV."
  - "UZM"
  - "UZM."
  - "BAKAN"
  - "GENEL MÜDÜR"
  - "BAŞKAN"
  - "EDİTÖR"
  - "MUHABİR"
  - "EKONOMİST"
  - "SİYASET BİLİMCİ"
  - "GENEL KOORDİNATÖR"
  - "PROGRAM SUNUCUSU"
  - "YAZAR"
  - "GAZETECİ"
  - "ANALİST"
  - "MİLLETVEKİLİ"
  - "BELEDİYE BAŞKANI"

organization_markers:
  - "ÜNİVERSİTESİ"
  - "BAKANLIĞI"
  - "DERNEĞİ"
  - "VAKFI"
  - "A.Ş."
  - "LTD."
  - "TV"
  - "HABER"
  - "GRUBU"
  - "KURUMU"
  - "MERKEZİ"
  - "ENSTİTÜSÜ"
  - "PARTİSİ"

reject_patterns:
  - "^CANLI$"
  - "^SON DAKİKA"
  - "^\\d{1,2}:\\d{2}"
  - "^HAFTA"
  - "^BUGÜN"
  - "^DÜN"
  - "^BREAKING"
  - "^LIVE$"
```

Bu listeler **başlangıç**. Aşama 0 profilleme sırasında golden set'te kaçırılan unvan/kurum varsa buraya eklenir.

### 1.2 — `core/pipelines/kj/__init__.py`

Boş paket dosyası.

### 1.3 — `core/pipelines/kj/dictionaries.py`

```python
@dataclass(frozen=True)
class KJDictionaries:
    turkish_titles: frozenset[str]
    organization_markers: frozenset[str]
    reject_patterns: tuple[re.Pattern, ...]
    schema_version: int

def load_dictionaries(path: Path) -> KJDictionaries:
    """YAML oku, schema_version==1 doğrula, frozen dataclass döndür.
    @lru_cache(maxsize=4) + mtime-based invalidation."""
```

### 1.4 — `core/pipelines/kj/parser.py`

```python
def parse_lower_third(
    lines: list[str],
    *,
    dictionaries: KJDictionaries,
    bbox: list[int] | None = None,
    ocr_confidence: float = 0.0,
    enable_rescue: bool = True,
) -> ParsedKJ:
```

**Adımlar:**

1. **Normalize:** TR-fold, punctuation cleanup, whitespace. **Reuse:** `text_layer_descroll.py`'da `normalize_text` varsa import et.
2. **Reject:** `dictionaries.reject_patterns` ile satır filtrele.
3. **Satır sınıflandır** (`_classify_line`):
   - Title prefix → `{type: "title_name", title, name_candidate}`
   - Org marker → `{type: "organization"}`
   - `upper_ratio > 0.75 AND 1 ≤ word_count ≤ 4` → `{type: "name"}`
   - Küçük harf ağırlıklı, ≤ 5 kelime → `{type: "role"}`
   - Diğer → `{type: "unknown"}`
4. **Format şablonu** (`_apply_format_template`):
   - 1 satır: title_name varsa ayır; `|` veya `/` separator varsa böl
   - 2 satır A: isim üstte, role/org altta
   - 2 satır B: title üstte, isim altta (Prof. Dr., Av. başlangıcı)
   - 3 satır: isim + role + org
5. **Confidence** (`_compute_parser_confidence`):
   - **Pattern reuse:** [text_layer_descroll.py:567-577](core/pipelines/ocr/text_layer_descroll.py:567)'deki `_pair_confidence` paternini kopyala, **dikey-layout için adapte et** (KJ'de y delta var, x delta yok; scroll'da tersi).
   - Formül: `0.55*name_score + 0.25*role_score + 0.20*format_consistency`
6. **Rescue:** `enable_rescue=True AND confidence < 0.70` → `kj.rescue.via_qwen(raw_lines, parsed_so_far)`. Dönüş varsa override (`source="qwen_rescue"`), dönüş `None` ise rule kalır.

```python
@dataclass(frozen=True)
class ParsedKJ:
    name: str | None
    title: str | None
    role: str | None
    organization: str | None
    confidence: float
    raw_lines: list[str]
    parser_version: str  # "kj_parser_v1"
    source: str          # "rule" | "qwen_rescue"
    needs_review: bool
```

### 1.5 — `core/pipelines/kj/rescue.py`

**Pattern reuse:** [core/api/asr_server.py:1757-1904](core/api/asr_server.py:1757)'teki `_summarize_with_openai`'yi kopyala, KJ için adapte et:

- Env: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MITAS_SUMMARY_MODEL` (yoksa `None` döndür)
- HTTP: `urllib.request`, `URLError + TimeoutError` yakala
- `temperature=0.1`, `max_tokens=200`, timeout `10s`
- Post-process: `_clean_model_output` reuse veya kopyala
- Parse: `json.loads`; başarısız → `None`

Prompt (sabit):

```python
SYSTEM_PROMPT = (
    "Sen TV altbantı (lower-third) satırlarını analiz edip kişi adı, "
    "unvanı, rolünü ve kurumunu çıkaran bir asistansın. "
    "Sadece satırlarda açıkça geçenleri yaz; tahmin yapma. "
    "Cevabını sadece geçerli JSON olarak ver, başka metin yazma."
)

def _build_user_prompt(raw_lines: list[str]) -> str:
    return (
        "Aşağıdaki altbant satırlarından kişi bilgilerini çıkar:\n\n"
        f"Satırlar:\n{chr(10).join(raw_lines)}\n\n"
        "Çıktı formatı (geçerli JSON, başka metin yok):\n"
        "{\n"
        '  "name": "ad soyad veya null",\n'
        '  "title": "akademik/profesyonel unvan veya null",\n'
        '  "role": "görev/sıfat veya null",\n'
        '  "organization": "kurum veya null",\n'
        '  "confidence": 0.0\n'
        "}"
    )
```

### 1.6 — Unit test'ler

`tests/test_kj_parser.py` — Cover et:
- Tek satır + title prefix
- 2 satır A ve B formatları
- 3 satır (isim + role + org)
- Reject pattern'lar
- Org marker tespiti
- Separator `|` ve `/`
- Rescue mock (başarılı/başarısız)
- `enable_rescue=False` ile rule-only davranış

`tests/test_kj_dictionaries.py` — Schema validation, hot reload, malformed YAML.

### 🚦 AŞAMA 1 GATE

```powershell
.\venvs\core\Scripts\pytest.exe tests\test_kj_parser.py tests\test_kj_dictionaries.py -v
.\venvs\core\Scripts\python.exe scripts\evaluate_kj_parser.py `
    --golden tests\fixtures\kj_golden_set.json `
    --output outputs\kj_parser_f1.json
```

**Geçer:** Tüm test'ler pass + `field_f1.overall >= 0.85`.

---

## YAPILACAKLAR — Aşama 2 (Event Detector — Ensemble Skor)

**Hedef:** Ekrandaki KJ'leri tespit eden, panel olmasa da çalışan, çoklu sinyal ensemble. Gate: video kesitlerinde event precision ≥ %80, recall ≥ %75 (panel'li ve panel'siz örnekler ayrı raporlanır).

### 2.1 — `core/pipelines/kj/event_detector.py`

```python
def detect_kj_events(
    ocr_records: list[dict],
    box_tracks: list[dict],
    track_states: list[dict],
    *,
    frame_width: int,
    frame_height: int,
    sample_fps: float,
    config: KJDetectorConfig,
) -> list[KJEvent]:
```

**KJ tespiti — 5 sinyal, ensemble (panel zorunlu değil):**

| # | Sinyal | Ne ölçer | Nasıl |
|---|---|---|---|
| 1 | **Konum sinyali** | KJ orta %90'da mı | `y_center_ratio ∈ [0.05, 0.95]` (config'ten) |
| 2 | **Statiklik sinyali** | Track stabil mi | [text_track_state.py:68-147](core/pipelines/ocr/text_track_state.py:68) `state == "STATIC"` |
| 3 | **Süre sinyali** | KJ-tipi süre mi | duration eşikleri Aşama 0 profilden (`min/max_duration_sec`) |
| 4 | **Reject sinyali** | Subtitle/ticker/watermark değil mi | aşağıda |
| 5 | **Panel sinyali (BONUS)** | Arka panel/şerit var mı | aşağıda |

**Reject (zorunlu — geçemezse KJ değil):**
- **Subtitle:** tek satır + `width_ratio > 0.85` + `text_change_rate > 0.3` (her 1-3 sn değişiyor)
- **Ticker:** `horizontal_velocity > config.max_horizontal_velocity_px_s`
- **Watermark/logo:** `duration > config.watermark_min_duration_sec`
- **Reject pattern'a uyan tek satır** (config.reject_strict_mode=True ise)

**Panel sinyali (`_compute_panel_score`):**
- Text bbox'ın arkasındaki dikdörtgen bölgenin **luminance varyansı** ve **kontrast** ölçülür (OpenCV `cv2.morphologyEx` ile dilate + mean luminance delta)
- Yarı saydam panel: text bölgesi arka plandan **belirgin farklı luminance** + **düşük varyans** (düz renk)
- Skor 0.0–1.0. Yoksa 0.0 — **cezalandırma yok**, sadece bonus puan yok.

**KJ skor formülü:**

```
score = w1*konum + w2*statik + w3*süre + w4*ocr_conf + w5*multi_line + w6*panel
      - subtitle_penalty - ticker_penalty - watermark_penalty
```

**Ağırlıklar (w1..w6) ve eşik (score_threshold) Aşama 0 profilleme çıktısından türetilir.** Hardcoded değildir. Başlangıç tahmini değerleri `config/kj_scanner.yaml`'ye konur, golden set üzerinde grid search ile ayarlanır.

**Panel'siz KJ'ler:** `w6*panel = 0` olur ama diğer 5 sinyal yüksekse hâlâ KJ kabul edilir. Eşik altında kalanlar `needs_review=True` ile işaretlenir (atılmaz).

```python
@dataclass(frozen=True)
class KJEvent:
    event_id: str
    start_seconds: float
    end_seconds: float
    bbox: tuple[int, int, int, int]
    text_track_ids: list[str]
    kj_score: float
    signal_breakdown: dict   # {konum, statik, süre, ocr_conf, multi_line, panel}
    reject_flags: list[str]
    needs_review: bool
    evidence: dict
```

### 2.2 — `config/kj_scanner.yaml`

```yaml
schema_version: 1

scan:
  # FPS — mevcut credit_experiment.py:36 DEFAULT_KJ_FPS = 2.0 ile uyumlu.
  # KJ minimum 2 sn olduğundan 2 fps'de garantili 4-8 frame yakalanır.
  sample_fps: 2.0                  # 1. tarama (tüm video, sürekli)
  refinement_fps: 5.0              # 2. tarama (sadece KJ aday event civarı ±1 sn)
  refinement_enabled: true

  # ROI — orta %90 tara, üst %5 ve alt %5 göz ardı (logo/saat/ticker bölgesi)
  roi_y_top: 0.05
  roi_y_bottom: 0.95
  roi_x_top: 0.0
  roi_x_bottom: 1.0

  # OCR motorları — credit_experiment.py:29 DEFAULT_ENGINES'i reuse et
  ocr_engines: ["paddle", "oneocr", "tesseract"]
  primary_engine: "paddle"         # PaddleOCR PP-OCRv5, GPU varsa otomatik
  agreement_required: true         # 2+ motor aynı text → güven yüksek
  agreement_min_engines: 2

detector:
  # Aşağıdaki değerler Aşama 0 profilleme sonrası güncellenecek.
  min_duration_sec: 1.5
  max_duration_sec: 25.0
  max_horizontal_velocity_px_s: 3.0
  watermark_min_duration_sec: 45.0
  score_threshold: 0.45
  needs_review_threshold: 0.30     # 0.30 ≤ score < 0.45 → review setine düşer
  weights:
    konum: 0.20
    statik: 0.20
    sure: 0.15
    ocr_conf: 0.15
    multi_line: 0.15
    panel: 0.15                    # Bonus; yoksa 0 olur, ceza yok
  subtitle_penalty: 0.25
  ticker_penalty: 0.30
  watermark_penalty: 0.35

rescue:
  enabled: true
  confidence_threshold: 0.70
  timeout_seconds: 10.0
```

### 2.3 — `core/pipelines/kj/scanner.py` — SERVİSİN ANA GİRİŞİ

```python
@dataclass(frozen=True)
class KJScanResult:
    video_path: str
    scan_started_at: str           # ISO timestamp
    scan_finished_at: str
    duration_seconds: float
    sample_fps: float
    kj_events: list[KJEvent]
    needs_review_events: list[KJEvent]
    scanner_version: str           # "kj_scanner_v1"
    config_snapshot: dict

def scan_video(
    video_path: Path,
    *,
    config: KJScannerConfig,
    output_dir: Path | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> KJScanResult:
    """
    Video baştan sona düşük FPS ile taranır.
    1. Frame extract (config.sample_fps)
    2. ROI uygula (y: 0.05-0.95, x: full)
    3. OCR çalıştır (PaddleOCR primary, OneOCR fallback)
    4. box_tracker.build_text_tracks REUSE
    5. text_track_state.classify_text_track_states REUSE
    6. credit_experiment.group_temporal_records REUSE
    7. event_detector.detect_kj_events
    8. Her event için temporal_fusion REUSE (median veya variance)
    9. Her event için parser.parse_lower_third
    10. needs_review_events ayrı listede tutulur
    11. Çıktı: output_dir / "kj_scan_result.json"
    """
```

**Reuse referansları (zorunlu):**
- Frame extraction: [credit_experiment.py](core/pipelines/ocr/credit_experiment.py) içindeki helper
- OCR çağrısı: mevcut PaddleOCR/OneOCR wrapper'ları
- [box_tracker.py:189-261](core/pipelines/ocr/box_tracker.py:189) `build_text_tracks`
- [text_track_state.py:68-147](core/pipelines/ocr/text_track_state.py:68) `classify_text_track_states`
- [credit_experiment.py:223-306](core/pipelines/ocr/credit_experiment.py:223) `group_temporal_records`
- [temporal_fusion.py:19-127](core/pipelines/ocr/temporal_fusion.py:19) `run_temporal_median_fusion`, `run_temporal_variance_masking`

**Bunlar `core.pipelines.ocr.*`'tan import edilir. Yeniden yazılmaz.** Ama servis kendisi `core.pipelines.kj.*` paketinde durur, OCR/ASR boru hatlarına bağımlı değildir.

### 2.4 — `scripts/kj_scan.py` — CLI

```powershell
# Tek video tara
.\venvs\core\Scripts\python.exe scripts\kj_scan.py `
    --video "F:\REPO_GitHub\DATABASE\program_X\episode_01.mp4" `
    --config config\kj_scanner.yaml `
    --output outputs\kj_scans\episode_01\

# Klasör tara (batch)
.\venvs\core\Scripts\python.exe scripts\kj_scan.py `
    --input-dir "F:\REPO_GitHub\DATABASE\programlar\" `
    --config config\kj_scanner.yaml `
    --output outputs\kj_scans\ `
    --workers 2
```

Her video için: `outputs/kj_scans/<video_name>/kj_scan_result.json` üretilir.

### 2.5 — Integration test

`tests/test_kj_event_detector.py` — Mock OCR records ile:
- Konum: orta %90 dışında → reject
- Subtitle vs KJ ayrımı
- Ticker vs KJ ayrımı
- Watermark vs KJ ayrımı
- Panel'li ve panel'siz KJ ikisi de tespit
- `needs_review` doğru set ediliyor

`tests/test_kj_scanner.py` — Kısa video kesitiyle e2e (golden set'ten 30 sn).

### 🚦 AŞAMA 2 GATE

```powershell
.\venvs\core\Scripts\pytest.exe tests\test_kj_event_detector.py tests\test_kj_scanner.py -v
.\venvs\core\Scripts\python.exe scripts\evaluate_kj_events.py `
    --manifest tests\fixtures\kj_video_segments_manifest.yaml `
    --output outputs\kj_event_metrics.json
```

**Geçer:** `precision >= 0.80 AND recall >= 0.75` (genel) **VE** `recall_no_panel >= 0.65` (panel'siz alt-küme). Panel'siz recall özellikle önemli.

---

## YAPILACAKLAR — Aşama 3 (Servis Entegrasyonu + UI)

**Hedef:** Servis API'den ve UI'dan tetiklenebilir hale gelsin. Hiçbir ASR pipeline değişikliği yok.

### 3.1 — `core/api/kj_router.py` — FastAPI router

```python
@router.post("/api/kj/scan")
async def kj_scan(payload: KJScanRequest) -> KJScanResponse:
    """
    Tek video taraması. Background task olarak başlar, job_id döndürür.
    """

@router.get("/api/kj/jobs/{job_id}")
async def kj_job_status(job_id: str) -> KJJobStatus:
    """Job durumu: queued | running | completed | failed."""

@router.get("/api/kj/jobs/{job_id}/result")
async def kj_job_result(job_id: str) -> KJScanResult:
    """Tamamlanmış job sonucu."""

@router.post("/api/kj/batch")
async def kj_batch_scan(payload: KJBatchRequest) -> KJBatchResponse:
    """Klasör batch tarama."""
```

[core/api/asr_server.py](core/api/asr_server.py) içinde router include edilir:

```python
from core.api.kj_router import router as kj_router
app.include_router(kj_router)
```

Bu **tek bir satır eklemedir**, ASR router'ı değiştirmez.

### 3.2 — UI'da KJ Tarama tetikleme + sonuç görüntüleme

[webui/src/app/components/](webui/src/app/components/) içinde yeni component: `KJScanWorkspace.tsx`.

İşlevler:
- Video seç (mevcut video listesinden veya path gir)
- "KJ Tara" butonu → `POST /api/kj/scan` çağırır, job_id alır
- Job durumu polling (`GET /api/kj/jobs/{job_id}`)
- Tamamlanınca KJ event listesi göster:

```tsx
<section className="kj-scan-results">
  <h3>KJ Olayları ({result.kj_events.length} kabul + {result.needs_review_events.length} review)</h3>
  <ul>
    {result.kj_events.map(ev => (
      <li key={ev.event_id}>
        <span>{formatTime(ev.start_seconds)}–{formatTime(ev.end_seconds)}</span>
        <strong>{ev.name ?? '—'}</strong>
        {ev.role && <em>{ev.role}</em>}
        {ev.organization && <span>{ev.organization}</span>}
        <span className="score">skor: {ev.kj_score.toFixed(2)}</span>
      </li>
    ))}
  </ul>
  <h4>Review gerektiren ({result.needs_review_events.length})</h4>
  {/* aynı liste, badge ile */}
</section>
```

[webui/src/app/asr-api.ts](webui/src/app/asr-api.ts) yanına yeni dosya: `webui/src/app/kj-api.ts`. ASR API'sini değiştirme.

[webui/src/app/components/Sidebar.tsx](webui/src/app/components/Sidebar.tsx)'a "KJ Tarama" sekmesi ekle.

### 3.3 — Servisin "hangi videoda çalış" kararı

Servis **kararı kendi vermez**. Karar şuradan gelir:
- **CLI:** Kullanıcı `--video` ya da `--input-dir` ile söyler
- **API:** İstek body'sinde video path verilir
- **UI:** Kullanıcı seçer

Yani "filmde KJ aramayacaksın" kuralı **kullanıcının sorumluluğu**. Servis kendisi profil bilmez. Bu sade ve doğru — servis "tarama motoru", "policy engine" değil.

### 3.4 — E2E test

`tests/test_kj_api.py` — FastAPI test client ile:
- `POST /api/kj/scan` → job_id döner
- Job tamamlanır, result alınır
- Sonuç şeması doğru

### 🚦 AŞAMA 3 GATE

```powershell
.\venvs\core\Scripts\pytest.exe tests\test_kj_api.py -v
.\venvs\core\Scripts\pytest.exe tests\test_asr_pipeline.py -v   # ASR regresyon — değişmemeli
```

**Manuel doğrulama:**
1. ASR sunucu restart
2. UI'da KJ Tarama sekmesine git, bir program videosu seç, "Tara" bas
3. Sonuç listesi gelmeli (kabul + review ayrı)
4. ASR akışı bağımsız çalışmaya devam etmeli (yan etki yok)

---

## ZORUNLU KURALLAR (ihlal = PR reddi)

1. **ASR pipeline dokunulmaz.** `core/pipelines/asr/` altındaki hiçbir dosya değiştirilmez. `ContentProfile`'a alan eklenmez. Pipeline'a hook eklenmez. KJ servisi tamamen bağımsız.

2. **Tek mevcut-dosya değişikliği:** Sadece `core/api/asr_server.py`'ye **1 satır** (`app.include_router(kj_router)`). Başka hiçbir mevcut dosya değişmez.

3. **Reuse zorunlu (yeniden yazılmaz):**
   - [text_layer_descroll.py:567-577](core/pipelines/ocr/text_layer_descroll.py:567) `_pair_confidence` paterni → parser (dikey adapte)
   - [asr_server.py:1757-1904](core/api/asr_server.py:1757) `_summarize_with_openai` paterni → rescue
   - [temporal_fusion.py:19-127](core/pipelines/ocr/temporal_fusion.py:19) doğrudan çağrı
   - [box_tracker.py:189-261](core/pipelines/ocr/box_tracker.py:189) doğrudan çağrı
   - [text_track_state.py:68-147](core/pipelines/ocr/text_track_state.py:68) doğrudan çağrı
   - [credit_experiment.py:223-306](core/pipelines/ocr/credit_experiment.py:223) `group_temporal_records` doğrudan çağrı

4. **Adapte edilecek (sadece kopya değil):** `text_layer_descroll.py`'deki name/role pairing yatay scroll için. KJ dikey. Açıkça yorumla, mantığı uyarla.

5. **Hardcoded sözlük yasak.** Türkçe unvan / kurum / reject sadece `config/kj_dictionaries.yaml`'da. Python dosyalarında liste literal yazılmaz.

6. **Hardcoded eşik yasak.** Konum, süre, skor ağırlıkları **Aşama 0 profilleme** sonucundan türetilir, `config/kj_scanner.yaml`'ye yazılır. Modül kodunda magic number olmaz.

7. **Panel zorunlu değil.** Panel skoru bonus, yoksa 0 — ceza yok. Panel'siz KJ'ler de tespit edilebilmeli (Aşama 2 gate'inde `recall_no_panel ≥ 0.65` koşulu var).

8. **VLM yasak (MVP).** Görüntü-girdili LLM çağrısı yok. Sadece text-only `qwen35local` rescue.

9. **Servis bağımsız.** `core/pipelines/kj/*` hiçbir yerden `core.pipelines.asr.*` import etmez. Servis ASR çalışmıyorken de çalışır.

10. **Sıra zorunlu.** Aşama 0 → 1 → 2 → 3. Aşama 0 (dataset profilleme) yapılmadan parser yazılmaz. Aşama 1 gate'i geçmeden Aşama 2'ye geçilmez.

11. **Master branch.** Worktree açma, branch oluşturma. Commit yalnızca Çağatay isterse.

12. **PowerShell + doğru venv.** Windows. Repoda 13 venv var (`venvs/asr`, `venvs/core`, `venvs/face`, `venvs/ocr`, `venvs/vlm`, vs.). KJ servisi için **`.\venvs\core\Scripts\python.exe`** kullanılır (memory: `project_mitas` venv haritası). `.\venv\Scripts\` ya da `.venv\` YOK — kullanma. Bash idiom yok.

---

## ÇIKTI BEKLENTİSİ (Aşama 0-3 tamamlandığında)

**Yeni dosyalar (10):**
- `config/kj_dictionaries.yaml`
- `config/kj_scanner.yaml`
- `core/pipelines/kj/__init__.py`
- `core/pipelines/kj/dictionaries.py`
- `core/pipelines/kj/parser.py`
- `core/pipelines/kj/rescue.py`
- `core/pipelines/kj/event_detector.py`
- `core/pipelines/kj/scanner.py`
- `core/api/kj_router.py`
- `webui/src/app/components/KJScanWorkspace.tsx` + `webui/src/app/kj-api.ts`

**Yeni script'ler (3):**
- `scripts/profile_kj_dataset.py`
- `scripts/kj_scan.py`
- `scripts/evaluate_kj_parser.py` + `scripts/evaluate_kj_events.py`

**Yeni testler (5):**
- `tests/test_kj_dictionaries.py`
- `tests/test_kj_parser.py`
- `tests/test_kj_event_detector.py`
- `tests/test_kj_scanner.py`
- `tests/test_kj_api.py`

**Mevcut dosya değişiklikleri (2):**
- `core/api/asr_server.py` — 1 satır router include
- `webui/src/app/components/Sidebar.tsx` — KJ Tarama sekmesi (1 link)

**Gate çıktıları:**
- `outputs/kj_dataset_profile.json` + `outputs/kj_dataset_profile_summary.md` (Aşama 0)
- `outputs/kj_parser_f1.json` (Aşama 1, F1 ≥ 0.85)
- `outputs/kj_event_metrics.json` (Aşama 2, precision ≥ 0.80, recall ≥ 0.75, recall_no_panel ≥ 0.65)
- Manuel UI doğrulama (Aşama 3)

**Tahmini süre:** 12-18 gün (≈ 2.5-3 hafta).
