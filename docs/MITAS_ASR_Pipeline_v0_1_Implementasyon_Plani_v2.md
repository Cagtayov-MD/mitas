# MITAS — ASR Pipeline v0.1 İmplementasyon Planı (profil-bazlı, v2)

> Hazırlayan: Claude oturumu
> Tarih: 2026-05-11
> Kapsam: v0.1 ASR dikey dilim
> Not: 2026-05-11 tarihli önceki "teknik tercih bazlı" plan bu sürümle ikame edilmiştir. Karar 14, Karar 15, Karar 16 ile uyumludur.

---

## 1. Genel mimari

ASR pipeline'ı persistent worker üzerine kurulu. Worker bir kez ayağa kalkar, faster-whisper ve pyannote modellerini belleğe yükler, gelen klipleri sırayla işler. Karar 14 ile `multilingual=True` sabitlendiği için multi-clip transcribe'da crash riski yok; subprocess pool gerekmiyor.

Pipeline her klip için iki temel girdi alır:

1. Ses dosyası yolu (video ise ses çıkarılır)
2. Profil tipi

Profil tipi diğer tüm davranışları yönetir.

Akış (diarization açık profil):

```text
ses dosyası + profil
  → audio normalize
  → Silero VAD
  → faster-whisper transcribe
  → pyannote diarization
  → segment-speaker merge
  → kalite flag'leri + metrikler
  → output JSON
```

Akış (diarization kapalı profil):

```text
ses dosyası + profil
  → audio normalize
  → Silero VAD
  → faster-whisper transcribe
  → kalite flag'leri + metrikler
  → output JSON (speaker_id alanları null)
```

---

## 2. Profil tanımları ve davranış matrisi

Pipeline beş profil tanır:

| Profil | Diarization default | Tipik içerik |
|---|---|---|
| `bulten_haber` | Açık | Haber bülteni; spiker + röportaj + sokak röportajı |
| `studio_panel` | Açık | Tartışma/talk; 3-5 konuşmacı, hızlı turn-taking, overlap |
| `muzik_programi` | Açık | Host konuşmaları + şarkı segmentleri (şarkı kısmı v0.2 Audio Activity'de işlenir) |
| `film` | Kapalı | Sinema filmi; düz transcript |
| `belgesel` | Kapalı | Belgesel; düz transcript |

**Manuel override:** Her profil için diarization durumu çağrı sırasında `diarize_override=True/False` parametresi ile ezilebilir. Karar 15 bu mekanizmayı gerektiriyor.

**Strict mode:** `diarize_required=True` parametresi ile diarize fail davranışı sertleştirilir; aksi halde graceful degradation (Karar 16) uygulanır.

**Profil zorunluluğu:** Profil parametresi pipeline çağrısında zorunludur. Klip için profil belirlenmemişse pipeline o klibi işlemez; sonuç `{"status": "skipped", "reason": "no_profile_assigned"}` döner. Bu skip hata değildir; batch ilerler. UI/orchestrasyon katmanı skipped klipleri "profil bekliyor" listesinde tutar; toplu seçim akışı bu listeyi besler.

---

## 3. Dosya yapısı

```text
core/pipelines/asr/
├── __init__.py
├── pipeline.py        ← üst seviye orkestrasyon (profil → akış)
├── worker.py          ← persistent worker, model lifecycle
├── normalize.py       ← ffmpeg ile audio normalize
├── vad.py             ← Silero VAD ayrı adım
├── transcribe.py      ← faster-whisper çağrısı
├── diarize.py         ← pyannote çağrısı
├── merge.py           ← segment + speaker birleştirme
├── quality.py         ← kalite flag'leri ve metrikler
└── profiles.py        ← profil tanımları + default davranış matrisi
```

Test:

```text
tests/test_asr_pipeline_v0_1_smoke.py
```

Schema bağlama için ayrı dosya yok — `core/schemas/module_run.py` ve `timeline.py` zaten hazır, pipeline output'u baştan bu modellere uyumlu üretilir.

---

## 4. Worker tasarımı

Worker iki iş yapar: model lifecycle yöneticisi + klip işleme pipe'ı.

**Başlangıç:** Worker ayağa kalktığında faster-whisper large-v3 ve pyannote diarization pipeline modellerini yükler, log'a yükleme süresini yazar (beklenen: faster-whisper ~5 sn, pyannote ~10 sn). Modeller worker bellekte tutulur, klipler arası tekrar yüklenmez.

**Klip işleme:** Worker `process(audio_path, profile, diarize_override=None, diarize_required=False)` çağrısını alır.

- Profil `bulten_haber`, `studio_panel`, `muzik_programi` ise (veya `diarize_override=True` ise): normalize → VAD → transcribe → diarize → merge → quality → output.
- Profil `film` veya `belgesel` ise (veya `diarize_override=False` ile diarization kapatıldıysa): normalize → VAD → transcribe → quality → output. Diarize ve merge atlanır.
- Profil verilmemişse: process başlamaz, skipped sonucu döner.

**Multilingual sabit:** Karar 14 gereği `multilingual=True` her çağrıda. Dil parametresi override edilmez.

**Shutdown:** Worker dışarıdan açıkça kapatılana kadar çalışır. v0.1'de otomatik restart politikası yok; uzun süreli memory davranışı smoke sırasında gözlemlenir, gerekirse sonraki sprintte restart eşiği eklenir.

---

## 5. Audio normalize

Hedef format: **16kHz, mono, 16-bit WAV**.

Araç: **ffmpeg** (PATH'te mevcut). ffprobe ile format kontrolü yapılır; input zaten hedef formatta ise dönüşüm atlanır, original kullanılır. Aksi halde geçici WAV `tmp/` altına yazılır, klip işlenmesi biter bitmez silinir.

Hata: ffmpeg fail ederse klip `{"status": "failed", "stage": "normalize", "error": "..."}` ile bırakılır.

---

## 5.5 Silero VAD

Normalize sonrası, transcribe öncesi ayrı adım olarak çalışır. silero-vad zaten `asr` venv'inde kurulu (6.2.1).

**Çıktı:** Speech region listesi (start, end aralıkları).

**Kullanım:**
1. Silero VAD region listesi faster-whisper'a doğrudan parametre olarak verilmez. Transcribe modülü bu region'ları kullanarak audio chunk/clip üretir, her chunk'ı ayrı işler ve chunk içi timestamp'leri original media timeline'a offset ile geri map eder.
2. `speech_ratio` metriği için: `sum(speech_durations) / total_audio_duration`.

**Süre:** `vad_seconds` olarak module_run'a yazılır.

**Hata:** Silero VAD fail ederse klip `{"status": "failed", "stage": "vad"}` ile bırakılır.

---

## 6. Transcribe

Motor: **faster-whisper large-v3** (Karar M3).

Parametreler:

- `device = "cuda"`
- `compute_type = "float16"`
- `multilingual = True` (Karar 14, sabit)
- `vad_filter = False` (Silero dışta, region'lar feed edilir)
- `word_timestamps = False` — v0.1 ana ASR pipeline segment-level timestamp üretir. WhisperX sistemden çıkarılmamıştır; `alignment` venv içinde opsiyonel word-level alignment katmanı olarak korunur.
- `beam_size = 5` (default)

Çıktı her segment için: `start`, `end`, `text`, `language`, `avg_logprob`, `no_speech_prob`.

**OOM fallback (Karar M3):** large-v3 OOM → distil-large-v3 → o da OOM olursa medium. Smoke öncesi her iki fallback model cache'inin local'de olduğu doğrulanmalı.

---

## 7. Diarize

Motor: **pyannote.audio**. Pipeline versiyonu kurulu olan ne ise o (muhtemelen speaker-diarization-3.1).

Token: `PYANNOTE_TOKEN` env variable'dan okunur. Hardcode yok. Model cache local olduğu için token doğrulama bir kerelik, sonra offline çalışır.

Çıktı her aralık için: `start`, `end`, `speaker_label` (SPEAKER_01, SPEAKER_02, ...).

**Profil koşulu:** Bu adım sadece diarization açık profillerde (veya `diarize_override=True` ile) çalışır.

**Hata davranışı (Karar 16):**

- Default (`diarize_required=False`): diarize fail → klip `status=partial_success`, `needs_review=true`. Transcript üretilir, speaker_id alanları null, `speaker_labels_available=false`, `diarization_status=failed` yazılır.
- Strict (`diarize_required=True`): diarize fail → klip `status=failed`.

---

## 8. Merge

Amaç: faster-whisper segmentlerini pyannote speaker timeline'ı ile birleştirmek.

**Temel kural:** Her ASR segmenti için zaman aralığıyla en çok örtüşen pyannote speaker aralığı bulunur. Örtüşme oranı **%50+** ise speaker atanır, değilse `speaker_id = null`.

**Örnek 1 (temiz):** ASR 0.5–4.2 sn, SPEAKER_01 0.0–4.0 sn. Örtüşme 3.5/3.7 = %95 → SPEAKER_01.

**Örnek 2 (sınır):** ASR 5.0–10.0 sn, SPEAKER_01 4.0–7.5 sn, SPEAKER_02 7.5–11.0 sn. Eşit örtüşme (2.5/2.5) → `speaker_id = null`, `flags = ["speaker_boundary"]`.

**Örnek 3 (zayıf):** ASR 12.0–13.5 sn, SPEAKER_03 12.5–13.0 sn. Örtüşme 0.5/1.5 = %33, eşik altı → `speaker_id = null`, `flags = ["no_speaker"]`.

Diarization kapalı profilde merge çalışmaz; tüm segmentlere `speaker_id = null` atanır, `speaker_boundary` flag'i kullanılmaz.

---

## 9. Kalite metrikleri ve flag'ler

Segment-bazlı flag'ler:

| Flag | Koşul |
|---|---|
| `low_confidence` | `avg_logprob < -0.8` veya `no_speech_prob > 0.6` |
| `short_segment` | süre < 0.5 saniye |
| `lang_switch` | önceki segmentten farklı `language` |
| `no_speaker` | diarization açık ama `speaker_id = null` (örtüşme yetersiz) |
| `speaker_boundary` | iki konuşmacı eşit örtüşme |

Eşik değerleri (-0.8 ve 0.6) başlangıç; smoke sonrası kalibre edilebilir.

Klip-seviyesi metrikler (`module_run` altında):

- `total_segments`
- `speech_ratio` (Silero VAD'den, gerçek değer)
- `low_confidence_ratio`
- `speaker_count` (sadece diarization açıkken)
- `language_distribution`
- `normalize_seconds`, `vad_seconds`, `transcribe_seconds`, `diarize_seconds`, `merge_seconds`, `total_seconds`

---

## 10. Output JSON tam şema

**Durum 1: success** (trt_haber, profile=bulten_haber, diarization açık ve başarılı)

```json
{
  "media_id": "trt_haber_1",
  "audio_path": "samples/trt_haber (1).mp4",
  "pipeline_version": "asr_v0_1",
  "profile": "bulten_haber",
  "diarization_enabled": true,
  "diarize_required": false,
  "status": "success",
  "diarization_status": "completed",
  "speaker_labels_available": true,
  "module_run": {
    "model_id": "large-v3",
    "compute_type": "float16",
    "multilingual": true,
    "total_segments": 12,
    "speech_ratio": 0.78,
    "low_confidence_ratio": 0.08,
    "speaker_count": 3,
    "language_distribution": {"tr": 11, "en": 1},
    "vad_seconds": 0.15,
    "transcribe_seconds": 2.1,
    "diarize_seconds": 4.3,
    "merge_seconds": 0.05,
    "total_seconds": 7.8
  },
  "segments": [
    {
      "index": 0, "start": 0.0, "end": 3.8,
      "text": "İyi akşamlar, Ana Haber bültenine hoş geldiniz.",
      "language": "tr",
      "avg_logprob": -0.18,
      "no_speech_prob": 0.02,
      "speaker_id": "SPEAKER_01",
      "flags": []
    }
  ]
}
```

**Durum 2: partial_success** (diarize fail, transcript var)

```json
{
  "media_id": "panel_clip_X",
  "profile": "studio_panel",
  "diarization_enabled": true,
  "diarize_required": false,
  "status": "partial_success",
  "needs_review": true,
  "diarization_status": "failed",
  "diarization_error": "pyannote pipeline crashed: ...",
  "speaker_labels_available": false,
  "module_run": { "total_segments": 8, "diarize_seconds": null, "...": "..." },
  "segments": [
    {
      "index": 0, "start": 0.0, "end": 3.8,
      "text": "...",
      "speaker_id": null,
      "flags": ["no_speaker"]
    }
  ]
}
```

**Durum 3: skipped** (profil yok)

```json
{
  "media_id": "...",
  "status": "skipped",
  "reason": "no_profile_assigned"
}
```

**Durum 4: failed** (ASR fail veya strict mode + diarize fail)

```json
{
  "media_id": "...",
  "profile": "studio_panel",
  "diarize_required": true,
  "status": "failed",
  "stage": "diarize",
  "error": "pyannote pipeline crashed: ..."
}
```

Çıktı yolu: `outputs/asr_v0_1_{media_id}.json`.

---

## 11. Hata yönetimi

| Stage / hata | Klip durumu | Batch etkisi |
|---|---|---|
| Medya okunamadı | `failed`, stage=normalize | completed_with_warnings |
| ffmpeg fail | `failed`, stage=normalize | completed_with_warnings |
| Silero VAD fail | `failed`, stage=vad | completed_with_warnings |
| faster-whisper OOM | fallback zinciri (distil-large-v3 → medium); başarısız olursa `failed` | completed_with_warnings |
| faster-whisper diğer crash | `failed`, stage=transcribe | completed_with_warnings |
| Pyannote token/cache yok | `diarize_required=False` → `partial_success`; `=True` → `failed` | completed_with_warnings |
| Pyannote crash | `diarize_required=False` → `partial_success`; `=True` → `failed` | completed_with_warnings |
| Merge sırasında hata | `partial_success` (transcript var, speaker_id null) | completed_with_warnings |
| Output JSON yazma fail | `failed`, stage=output | completed_with_warnings |
| Tüm klipler `success` | — | completed |
| Tüm klipler `failed` | — | failed |

Strict mode (`diarize_required=True`) profil davranışını ezmez — sadece diarization fail davranışını sertleştirir.

---

## 12. Test stratejisi

**Smoke seti:** `trt_haber (1).mp4`, `trt_haber (2).mp4`, `trt_haber (3).mp4`. Tümü `profile=bulten_haber` ile koşulur.

**Klip başına kontroller:**

- `status` değeri `"success"` veya `"partial_success"` olabilir. `partial_success` özellikle diarization fail edip transcript üretildiğinde kabul edilir.
- Output JSON üretildi ve şemaya uygun
- `speech_ratio > 0.5`
- `low_confidence_ratio < 0.3`
- `language_distribution`'da çoğunluk `tr`
- `speaker_count >= 2` zorunlu değildir. Smoke, diarization entegrasyonunun çalıştığını ve başarısızsa graceful degradation ürettiğini doğrular; speaker sayısı içerik profiline ve pyannote sonucuna bağlı değerlendirilir.

**Stress kontrolü:** Üç klip arka arkaya tek worker'da koşar, model bir kez yüklenir. Crash yok, memory build-up gözlenir.

**Regression kontrolü:** Karar 14 sonrası bilinen baseline transcript'lerle metin benzerliği kontrolü.

**Smoke kapsam dışı:** `studio_panel` ve `muzik_programi` profilleri bu sette test edilemez (uygun klip yok). Onlar için klip bulununca ek smoke turu koşulur; v0.1'i bloke etmez.

---

## 13. Kapsam dışı (v0.1'e girmeyen)

- Word-level timestamps (Karar O2)
- Cross-session speaker identification (Karar M5)
- Voice enrollment / voice profiles
- Overlap recovery (Karar 15 kabul edilmiş limit)
- Otomatik profil tespiti
- Otomatik ses kalitesi tespiti
- FastAPI / WebSocket endpoint
- Streaming transcribe
- Audio Activity Layer (v0.2)
- Song recognition (v0.2)
- DeepFilterNet denoise (ayrı sprint kararı gerektirir)
- Schema export / DB persistence layer

---

## 14. Bağımlılıklar

- `asr` venv (faster-whisper + pyannote + silero-vad)
- ffmpeg ve ffprobe PATH'te
- CUDA / RTX 3090
- `PYANNOTE_TOKEN` env variable (mevcut)
- Pyannote model cache local (mevcut)
- faster-whisper `large-v3` cache local (mevcut)
- **Smoke öncesi doğrulanmalı:** `distil-large-v3` ve `medium` fallback model cache'leri
- silero-vad model cache (ilk smoke'da otomatik cache'lenir)
- Test klipleri `samples/` altında

---

## Uygulama notları (Codex için)

- Plan adımları sıralı: normalize → VAD → transcribe → diarize → merge → quality → output.
- Her modül ayrı dosyada, tek sorumluluk.
- Pipeline output'u baştan `core/schemas/module_run.py` ve `timeline.py` modellerine uyumlu üretilir; schema bağlamayı sona bırakma.
- Her adım sonunda commit beklenir.
- Smoke testi `tests/test_asr_pipeline_v0_1_smoke.py` altında, `samples/trt_haber*.mp4` klipleri ile koşulur.
