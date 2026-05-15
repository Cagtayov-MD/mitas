# Sprint 4 — ASR v0.1 Dikey Dilim (DONE)

> Tarih: 2026-05-14
> Sprint çerçevesi: `mutfak/05_AKTIF_GOREV.md` (v0.1 — ASR dikey dilim)
> Sprint kararlar: `mutfak/06_KARARLAR_GUNLUGU.md` Karar 14, 15, 16, 22, 23, 24, 25

Bu doküman ASR v0.1 sprint'inin kapanış arşividir. v0.2'ye (OCR/KJ + Müzik segment) geçmeden önce v0.1 dilimi neyi kapsadı, neyi kapsamadı ve hangi açıklar v0.2'ye devredildi — bunları sabitler.

---

## 1. Sprint hedefi

ASR pipeline'ını dürüstçe, smoke test edilebilir şekilde uçtan uca ayağa kaldırmak. Streaming değil, batch. Tek bir Türkçe TRT örneği üzerinde JSON çıktı üretmek. Model tartışmasını netleştirmek.

---

## 2. Teslim edilenler

### 2.1 Kod katmanı

| Modül | Dosya | Ne yapar |
|---|---|---|
| Normalize | [normalize.py](../core/pipelines/asr/normalize.py) | Video/audio → 16 kHz mono PCM WAV (split kanal desteğiyle) |
| VAD | [vad.py](../core/pipelines/asr/vad.py) | Silero VAD ile konuşma segmentleri + speech_ratio |
| Chunking | [chunking.py](../core/pipelines/asr/chunking.py) | VAD segmentlerini merge edilmiş chunk'lara dönüştürür |
| Transcribe | [transcribe.py](../core/pipelines/asr/transcribe.py) | faster-whisper, `fast_with_fallback` profili, adaptive fallback |
| Quality | [quality.py](../core/pipelines/asr/quality.py) | Segment + result-level safety gates, tail-gap detection |
| Channel analysis | [channel_analysis.py](../core/pipelines/asr/channel_analysis.py) | Stereo girdide L/R korelasyon analizi, mono/split kararı |
| Channel merge | [channel_merge.py](../core/pipelines/asr/channel_merge.py) | Split L/R sonuçlarını birleştir, cross-channel duplicate drop |
| Pipeline | [pipeline.py](../core/pipelines/asr/pipeline.py) | Orkestrasyon, ModuleRun + TimelineEvent + quality_report emit |

### 2.2 Çıktı sözleşmesi

Her pipeline koşumu `outputs/asr_runs/<media>_<ts>_<id>/` altına şu 5 artifact'i yazar:

| Dosya | Şema | İçerik |
|---|---|---|
| `archive.json` | İç yapı | Tam transcript + segmentler + flag'ler + duplicate drops |
| `summary.json` | İç yapı | Pipeline metrikleri + `quality_report` bloğu (Master plan §2.1) + safety diagnostics |
| `module_run.json` | `core.schemas.ModuleRun` | Pydantic strict; job/module_run/medya bağlantısı |
| `timeline_events.json` | `core.schemas.TimelineEvent[]` | Her clean_segment için bir `asr_segment` event |
| `transcript_review.md` | Markdown | Summary + Clean transcript + Verbatim transcript (insan denetimi için) |

### 2.3 Demo

- Üretim scripti: [scripts/asr_v0_1_demo.py](../scripts/asr_v0_1_demo.py) (`asr` venv ile koşulur)
- Klip: **001_h1** — TRT haber kameramanları meslek standardı haberi, 101.739 sn
- Kaynak: `\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav\H1.wav`
- Çıktı dizini: [outputs/asr_v0_1_demo/](../outputs/asr_v0_1_demo/)
- Sonuç: `profile_used=fast` (turbo geçti, fallback yok), 15 clean segment, 166 kelime, 15 TimelineEvent, VAD `speech_ratio=0.849`, `safety_passed=True`, total runtime ~38.5 sn.

### 2.4 Test paketi

55 yeşil (`E:\MITAS\venvs\core\Scripts\python.exe -m pytest`).

| Dosya | Adet | Kapsam |
|---|---|---|
| `tests/test_asr_pipeline.py` | 5 | Pipeline orkestrasyon, channel mode, error path |
| `tests/test_production_transcribe.py` | 7 | Profile dispatch, fallback senaryoları, tail-gap, coverage seçici |
| `tests/test_asr_quality.py` | 24 | Stock artifact, repetition collapse, word density, segment evaluation, result safety |
| `tests/test_asr_channel_merge.py` | 9 | Cross-channel duplicate drop, tag_result_channel |
| `tests/test_asr_v0_1_smoke.py` | 10 | Demo output schema + invariant doğrulaması (golden-file) |

### 2.5 Karar kaydı

Sprint boyunca alınan kararlar `mutfak/06_KARARLAR_GUNLUGU.md` içinde Karar 14-25 olarak kayıtlı. Öne çıkanlar:

- **Karar 23:** ASR default modeli `large-v3-turbo`; `large-v3` selective fallback.
- **Karar 24:** Adaptive fallback — tail-gap tetikleyici + fallback result selector + `selection_reason`.
- **Karar 25:** v0.1 kapatma paketi — TimelineEvent emit, kalite raporu standardizasyonu, smoke test, demo output.

---

## 3. Master plan §2.1 ASR kalite raporu kontratı — karşılaştırma

Master plan §2.1 ASR kalite raporu için 5 zorunlu alan tanımlıyor. v0.1 dilimindeki durum:

| §2.1 zorunlu alan | v0.1 durumu | Konum | Açıklama |
|---|---|---|---|
| word_timestamp_coverage | ⚠️ `not_applicable` | `summary.quality_report.word_timestamp_coverage` | WhisperX `asr` venv'e kurulmadı; `alignment` venv'de subprocess sleeve mevcut ama v0.1 dilimi onu çağırmıyor. v0.2'de açılır. |
| alignment_success | ⚠️ `not_applicable` | `summary.quality_report.alignment_success` | WhisperX bağımlı. word_timestamp_coverage ile aynı v0.2 paketinde açılır. |
| VAD speech ratio | ✅ doğrudan | `summary.quality_report.vad_speech_ratio` + `summary.vad.speech_ratio` | Silero VAD üzerinden. Demo değer: 0.849. |
| diarization durumu | ⚠️ `not_applicable` | `summary.quality_report.diarization` | pyannote `asr` venv'inde kurulu ama v0.1 dilimi `bulten_haber` / `studio_panel` profillerinde çağırmıyor; v0.2/v0.3'te profil bazlı açılır. |
| hata bayrakları | ✅ doğrudan | `summary.quality_report.error_flags` (+ daha zengin form: `summary.safety.diagnostics`, `archive.segments[].flags`, `archive.quality.drop_reasons`) | Segment-level flag'ler + safety failure + drop reason'lar birleşik liste olarak `error_flags`'e toplanır. |

**Sonuç:** 2/5 doğrudan, 3/5 `not_applicable` plak (raporlama disiplini gereği). Hiçbir alan eksik yazılmadı; sözleşme uyumu sağlanmış sayılır.

---

## 4. v0.2'ye devreden bilinen açıklar

### 4.1 WhisperX entegrasyonu (word_timestamp_coverage + alignment_success)

WhisperX `alignment` venv'de subprocess sleeve olarak smoke yeşil ([Karar 9](../mutfak/06_KARARLAR_GUNLUGU.md)). Henüz `pipeline.run_asr_pipeline()` içinden çağrılmıyor. Açılması için:

- `core/pipelines/asr/align.py` (yeni) — alignment venv'e subprocess sleeve çağrısı
- `transcribe()` sonrasında çağrılır, word-level JSON döner
- `quality_report.word_timestamp_coverage` = aligned_word_count / expected_word_count
- `quality_report.alignment_success` = boolean (sleeve return code + minimum coverage)

### 4.2 Diarization (pyannote çağrısı)

pyannote `asr` venv'de kurulu. Profil bazlı açılışı [Karar 15](../mutfak/06_KARARLAR_GUNLUGU.md) öngörüyor: `bulten_haber`, `studio_panel`, `muzik_programi` profillerinde açık; `film`, `belgesel` profillerinde kapalı. Açılması için:

- `core/pipelines/asr/diarize.py` (mevcut iskelet) — pyannote sleeve
- `pipeline.py`'de profil bazlı şartlı çağrı
- `quality_report.diarization` = `{status: "ok"|"degraded"|"failed", speaker_count, runtime_sec}`

### 4.3 Profile dispatch (`bulten_haber` / `studio_panel` / ...)

Mevcut `pipeline.py` tek profil tanır (`fast_with_fallback` model profili). [Karar 14/15](../mutfak/06_KARARLAR_GUNLUGU.md)'te tanımlanan 5 içerik profili (`bulten_haber`, `studio_panel`, `muzik_programi`, `film`, `belgesel`) henüz pipeline parametresine bağlanmadı. v0.2'de:

- `profiles.py` ile profil → davranış matrisi
- `run_asr_pipeline(content_profile=...)` parametresi
- Profile diarization on/off, beam size, model seçimi bağlanır

### 4.4 Persistent worker

[v0.1 İmplementasyon Planı v2](MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md) §1'de persistent worker tasarımı var. Mevcut `pipeline.run_asr_pipeline()` her çağrıda model yüklüyor; `models.load_model()` in-process cache'i bir koşumda işe yarıyor ama process restart'ta sıfırlanıyor. v0.2'de:

- `core/pipelines/asr/worker.py` (mevcut iskelet) — persistent worker
- Model lifecycle: bir kez yükle, çoklu klip işle
- Job queue entegrasyonu (`core/jobs/`)

### 4.5 Eşik kalibrasyonu (TRT verisi geldiğinde)

[Karar 24](../mutfak/06_KARARLAR_GUNLUGU.md) son cümlesinde altı çizildiği gibi:

- `max_uncovered_tail_seconds = 3.0`
- `max_uncovered_tail_ratio = 0.25`
- Coverage seçici toleransları: `coverage_tolerance_seconds = 1.0`, `coverage_tolerance_ratio = 0.05`

Bu sayılar MediaSpeech dış verisinde sınanmış; TRT iç verisi geldiğinde tekrar koşum + kalibrasyon yapılacak. Benchmark scripti `scripts/asr_mediaspeech_benchmark.py` parametrik; TRT WAV/TXT çiftleri için aynı şekilde koşulabilir.

---

## 5. Reprodüksiyon adımları

Bu sprint'in çıktısını sıfırdan üretmek için:

```powershell
# 1. Demo'yu çalıştır (asr venv, ~38 sn)
E:\MITAS\venvs\asr\Scripts\python.exe E:\MITAS\scripts\asr_v0_1_demo.py

# 2. Smoke + tüm ASR testlerini koştur (core venv, ~3 sn)
$env:PYTHONPATH = "E:\MITAS"
E:\MITAS\venvs\core\Scripts\python.exe -m pytest `
  E:\MITAS\tests\test_asr_pipeline.py `
  E:\MITAS\tests\test_production_transcribe.py `
  E:\MITAS\tests\test_asr_quality.py `
  E:\MITAS\tests\test_asr_channel_merge.py `
  E:\MITAS\tests\test_asr_v0_1_smoke.py `
  -v
```

Beklenen sonuç: **55 passed**. Demo dizini: `E:\MITAS\outputs\asr_v0_1_demo\` (5 artifact).

---

## 6. Sprint sonrası v0.2 kapsamı (özet)

`mutfak/05_AKTIF_GOREV.md` v0.2 sürümüne hazır:

- v0.2 — OCR/KJ + Müzik segment dikey dilim
- ASR ek işleri (4.1-4.4 yukarıda) v0.1.x veya v0.2.x patch sprint'lerinde kapatılır
- TRT transcript havuzu eşik kalibrasyonu (4.5) hemen verinin geldiği gün yapılır

Bu doküman v0.1'i kilitler; bundan sonraki ASR işleri yeni sprint olarak `mutfak/05_AKTIF_GOREV.md`'ye yazılır.
