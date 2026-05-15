# ASR v0.1 Sonrası Devreden İşler — Detaylı İnceleme

> Hazırlık tarihi: 2026-05-14
> Bağlam: [docs/SPRINT_4_ASR_V0_1_DONE.md](SPRINT_4_ASR_V0_1_DONE.md) — v0.1 dikey dilim kapandı
> Yol haritası girdi: [mutfak/04_YOL_HARITASI.md](../mutfak/04_YOL_HARITASI.md) §v0.1.x
> Kararlar: [mutfak/06_KARARLAR_GUNLUGU.md](../mutfak/06_KARARLAR_GUNLUGU.md) Karar 14, 15, 16, 23, 24, 25

Bu doküman v0.1 ASR dikey diliminden sonra ASR modülünü production v1.0'a olgunlaştıracak 5 paketin detaylı açıklamasıdır. Her paket için: konsept, mevcut kod hazırlığı, ne yapılacak, niye önemli ve maliyet tahmini yer alır.

> **Not:** Bu işlerin bir kısmı "v0.2'ye devredildi" diye anılır (v0.1 kapanış raporundaki çerçeve) ama içerik olarak v0.2 (OCR/KJ + Müzik) sprint'inden farklı bir eksendir. Yol haritasında **v0.1.x ASR olgunlaşma paketleri** olarak konumlandırıldı; v0.2'den önce de sonra da açılabilirler.

---

## İçindekiler

1. [WhisperX entegrasyonu](#1-whisperx-entegrasyonu)
2. [Diarization profil bazlı çağrı](#2-diarization-profil-bazlı-çağrı)
3. [Profile dispatch (5 içerik profili)](#3-profile-dispatch-5-içerik-profili)
4. [Persistent worker](#4-persistent-worker)
5. [TRT verisi eşik kalibrasyonu](#5-trt-verisi-eşik-kalibrasyonu)
6. [Özet karşılaştırma tablosu](#6-özet-karşılaştırma-tablosu)
7. [Pratik sıralama önerisi](#7-pratik-sıralama-önerisi)

---

## 1. WhisperX entegrasyonu

### Ne demek?

**WhisperX**, OpenAI Whisper'ın üzerine kurulu bir araçtır. İki şeyi yapar:

- **Word-level timestamp** — `large-v3` segment seviyesinde "10.2sn — 14.8sn arası şu cümle" der; WhisperX kelime kelime "10.2 → 10.4 'Kimi'", "10.4 → 10.7 'zaman'", "10.7 → 11.0 'çatışmanın'" diye verir.
- **Forced alignment** — Whisper'ın çıkardığı metni ses dalgasıyla phoneme-level eşler (wav2vec2 modeliyle). Bu, "her kelimenin doğru başlangıç-bitiş zamanını" sağlar.

### Şu an ne var?

- ✅ `venvs/alignment/` ayrı bir venv olarak kurulu, WhisperX 3.8.5 paketli
- ✅ [scripts/alignment_subprocess.py](../scripts/alignment_subprocess.py) — subprocess sleeve mevcut, smoke yeşil
- ✅ Karar 9 ile dormant torchcodec sorunu kabul edildi; alignment yolunda etkili değil
- ❌ `core/pipelines/asr/align.py` **yok** — pipeline'a bağlanmamış
- ❌ `run_asr_pipeline()` WhisperX'i çağırmıyor
- ❌ `summary.quality_report.word_timestamp_coverage` ve `alignment_success` şu an `not_applicable`

### Ne yapılacak?

```
1. core/pipelines/asr/align.py yaz:
   - input: faster-whisper clean_segments + normalized_audio path
   - subprocess: scripts/alignment_subprocess.py + alignment venv
   - output: word-level JSON [{word, start, end, score}, ...]

2. pipeline.py'de transcribe() sonrası align() çağır:
   - aligned_words = align(asr_result.clean_segments, normalized_audio_path)
   - TranscriptSegment'e words: list[WordTimestamp] alanı ekle (opsiyonel,
     post-processing aşamasında doldurulur)

3. Quality report doldur:
   - word_timestamp_coverage = aligned_words / expected_words
   - alignment_success = subprocess return_code == 0 AND coverage > 0.95

4. TimelineEvent payload'ına word_timestamps: list ekle (her event için
   içerdiği kelimelerin start/end zamanları)
```

### Niye önemli?

- **UI**: Video oynatırken karaoke gibi kelime kelime highlight (showcase'in çekiciliği bunda). Mevcut segment-level highlight 3-15 saniyelik bloklar gösterir, kelime-level çok daha akıcı.
- **Evidence**: "Bu kelime 42.7sn'de geçiyor" diye delil çıkarmak için gereklidir. Phase 2 üst denetim katmanı ([mutfak/09_UST_DENETIM_KATMANI.md](../mutfak/09_UST_DENETIM_KATMANI.md)) kelime-bazlı doğrulama yapacak: özel isim hatası, quoted evidence vs.
- **Master plan §2.1**: Sözleşmenin bir parçası — şu an `not_applicable` plak; v0.1.x ile gerçek değer.

### Maliyet

**Yaklaşık 1-2 günlük iş.** Subprocess sleeve zaten yazılmış, sadece:
- Pipeline'a kanca atmak
- Quality report'u doldurmak
- TimelineEvent payload'ına word timestamps eklemek
- 2-3 smoke testi yazmak

### Bağımlılıklar
- Yok (alignment venv kurulu, sleeve smoke yeşil)

---

## 2. Diarization profil bazlı çağrı

### Ne demek?

**Diarization** = "kim ne zaman konuştu" — sesi konuşmacılara göre etiketlemek.
- Output: `SPEAKER_00`, `SPEAKER_01`, ... (anonim ID'ler — kimlik tespiti değil)
- Kullanılan model: **pyannote/speaker-diarization-3.1**
- Kişi kimliği değil; aynı kişi farklı klipte farklı ID alır. Cross-session voice identification v2'ye ertelendi (Karar M5).

**Profil bazlı çağrı** = her içerik için diarization açık/kapalı kararı ([Karar 15](../mutfak/06_KARARLAR_GUNLUGU.md)):

| Profil | Diarization | Sebep |
|---|---|---|
| `bulten_haber` | ✅ açık | Spiker + muhabir + röportaj — çoklu konuşmacı |
| `studio_panel` | ✅ açık | Tartışma programları, 3-5 konuşmacı, hızlı turn-taking |
| `muzik_programi` | ✅ açık | Sunucu + konuk + şarkı kısımları arası geçiş |
| `film` | ❌ kapalı | Diyalog var ama düz transcript yeterli; sinema kişi tanıma yüz tarafında çözülür |
| `belgesel` | ❌ kapalı | Anlatıcı + nadir röportaj — ek değer az |

**Kalite eşiği kuralı** (Karar 15): Diarization açık olsa bile, pyannote bir segmentin konuşmacısından emin değilse `speaker_id = null` yazılır. Hard fail değil, graceful degradation.

### Şu an ne var?

- ✅ `venvs/asr/` içinde pyannote-audio 4.0.4 kurulu
- ✅ [core/pipelines/asr/diarize.py](../core/pipelines/asr/diarize.py) **214 satır gerçek kod**:
  - `diarize_audio()` — ana entry point
  - `DiarizationResult`, `DiarizationSegment` dataclass'ları
  - `PyannotePipelineConfig` — model snapshot path, device, ffmpeg shared DLL bağlanması
  - Windows-spesifik pyannote bug'ı için patch (`_patched_pyannote_get_plda`)
- ✅ [tests/test_asr_diarize.py](../tests/test_asr_diarize.py) — 6 ünit test
- ✅ [tests/test_asr_diarize_real_media.py](../tests/test_asr_diarize_real_media.py) — 2 real-media test (GPU gerekiyor, şu an skip)
- ❌ `pipeline.py` diarize'ı **hiç import etmiyor** — disconnected module
- ❌ Profile bazlı çağrı yok (zaten profile dispatch yok — bkz. Paket 3)
- ❌ Karar 15'in "düşük güven → speaker_id=null" graceful degradation kuralı uygulanmamış
- ❌ Karar 16'nın `partial_success` status'u entegre değil

### Ne yapılacak?

```
1. pipeline.py'de profile bazlı diarization çağrısı:
   if content_profile in {"bulten_haber", "studio_panel", "muzik_programi"} or
      diarize_override is True:
       try:
           diarize_run = diarize_audio(normalized_audio_path)
       except Exception as exc:
           if diarize_required:
               raise
           # graceful degradation: continue without diarization
           diarize_run = None
           diarization_status = "failed"

2. Segment-speaker merge:
   - core/pipelines/asr/merge.py (yeni veya mevcut diarize.py içinde)
   - Her TranscriptSegment için en çok overlap eden speaker turn'ü bul
   - segment.speaker_id = "SPEAKER_00" veya None (eğer overlap < threshold)

3. Quality config:
   - min_speaker_overlap_ratio = 0.5 (Karar 15 graceful degradation eşiği)
   - Pyannote crash ederse safety yine de geçer, transcript korunur

4. Quality report:
   - diarization = {
       "status": "ok" | "degraded" | "failed",
       "speaker_count": N,
       "runtime_sec": X,
       "low_confidence_segments": K  # speaker_id=null bırakılan sayı
     }

5. TimelineEvent payload: speaker_id zaten alan var, doldurulması yeterli

6. ModuleRun status:
   - Diarization fail + Karar 16 → status = "partial"
```

### Niye önemli?

- **Haber içeriği için kritik** — TRT arşivinin büyük kısmı bülten/röportaj formatında; "kim konuştu" bilgisi olmadan transkript yarım kalır
- **Phase 2 candidate relations** — `face_cluster` ↔ `speaker_id` eşleşmesi: yüz tanıma + ses tanıma cross-validation. Bu eşleşmeler `speaker_overlaps_face_candidate` ilişki tipinde toplanır ([RelationType](../core/schemas/common.py))
- **Master plan §2.1**: Sözleşme alanı; şu an `not_applicable` plak
- **Review UI** — Konuşmacı bazlı transcript görünümü için altyapı

### Maliyet

**Yaklaşık 2-3 günlük iş.** Kod hazır, sadece:
- Pipeline entegrasyonu
- Segment-speaker merge mantığı + eşik
- Edge case'ler: pyannote yavaş (RTX 3090'da yaklaşık real-time × 0.3) — Karar 15 zaten bunu öngörüyor
- Karar 16 partial_success akışı
- Smoke test (TRT haber kliplerinden 1 tanesinde)

### Bağımlılıklar
- **Paket 3 (Profile dispatch)** — profil olmadan "ne zaman çağıralım" sorusu cevapsız

---

## 3. Profile dispatch (5 içerik profili)

### Ne demek?

Şu an `profile` parametresinin **iki farklı anlamı karışıyor**:

**Model profili** (var):
- `fast` — sadece large-v3-turbo
- `quality` — sadece large-v3
- `fast_with_fallback` — turbo + adaptive fallback (Karar 24)

**İçerik profili** (yok):
- `bulten_haber`, `studio_panel`, `muzik_programi`, `film`, `belgesel`

İçerik profili → tüm pipeline davranışını yönetir. Sadece diarization açık/kapalı değil, ayrıca:

| Profil | Diarize | Model profili | Denoise | Beam | initial_prompt | Audio activity layer |
|---|---|---|---|---|---|---|
| `bulten_haber` | Açık | fast_with_fallback | Opsiyonel | 5 | None | Speech baskın |
| `studio_panel` | Açık | fast_with_fallback | Hafif | 5 | None | Speech baskın, applause olabilir |
| `muzik_programi` | Açık | fast_with_fallback | Kapalı | 5 | "Türkçe müzik programı" | **Müzik kısımları ayrılır (v0.2)** |
| `film` | Kapalı | fast_with_fallback | Hafif | 5 | None | Diyalog + müzik + efekt |
| `belgesel` | Kapalı | quality | Hafif | 8 | None | Anlatıcı baskın |

**Manuel override** (Karar 15): Her profil için diarization durumu çağrı sırasında `diarize_override=True/False` ile ezilebilir. Strict mode için `diarize_required=True`.

**Profil zorunluluğu** ([v0.1 İmplementasyon Planı §2.6](MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md)): Klip için profil belirlenmemişse `{"status": "skipped", "reason": "no_profile_assigned"}` döner. Skip hata değildir; batch ilerler. UI/orchestrasyon "profil bekliyor" listesinde tutar.

### Şu an ne var?

- ❌ `core/pipelines/asr/profiles.py` **yok**
- ❌ `run_asr_pipeline()` sadece `profile: ProfileName` parametresi alıyor — bu MODEL profili
- ❌ Karar 15'teki davranış matrisi koda inmemiş
- ✅ [docs/MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md §2](MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md) profil tanımları yazılı
- ✅ Karar 15 dokümante

### Ne yapılacak?

```python
# core/pipelines/asr/profiles.py (yeni)

from dataclasses import dataclass
from typing import Literal
from core.pipelines.asr.models import ProfileName  # mevcut MODEL profile

ContentProfileName = Literal[
    "bulten_haber", "studio_panel", "muzik_programi", "film", "belgesel"
]


@dataclass(frozen=True)
class ContentProfile:
    name: ContentProfileName
    model_profile: ProfileName
    diarize: bool
    denoise: bool
    beam_size: int
    initial_prompt: str | None
    notes: str


CONTENT_PROFILES: dict[ContentProfileName, ContentProfile] = {
    "bulten_haber": ContentProfile(
        name="bulten_haber",
        model_profile="fast_with_fallback",
        diarize=True,
        denoise=False,
        beam_size=5,
        initial_prompt=None,
        notes="Spiker + muhabir + röportaj; net stüdyo + bazen saha sesi",
    ),
    "studio_panel": ContentProfile(...),
    "muzik_programi": ContentProfile(...),
    "film": ContentProfile(...),
    "belgesel": ContentProfile(...),
}


def get_content_profile(name: str) -> ContentProfile:
    if name not in CONTENT_PROFILES:
        raise ValueError(f"Unknown content profile: {name}")
    return CONTENT_PROFILES[name]
```

```python
# pipeline.py değişikliği
def run_asr_pipeline(
    input_path,
    *,
    content_profile: ContentProfileName,    # YENİ — zorunlu
    model_profile_override: ProfileName | None = None,
    diarize_override: bool | None = None,
    diarize_required: bool = False,
    ...,
):
    profile = get_content_profile(content_profile)
    model_profile = model_profile_override or profile.model_profile
    diarize = diarize_override if diarize_override is not None else profile.diarize
    # ... rest of pipeline
```

### Niye önemli?

- **TRT arşivinde her dosyaya profil atanması gerekiyor** — Sprint v0.1 İmplementasyon Planı v2 §2 zaten "profil parametresi pipeline çağrısında zorunlu"
- **Yanlış profil = yanlış davranış** — filme diarize çalıştırmak boşa GPU vakti; bültene diarize çalıştırmamak speaker bilgisini kaybeder
- **UI/orchestrasyon**: "profil bekliyor" listesi (toplu seçim akışı). Geliştirici/operatör bir batch klibe topluca profil atayabilir
- **Yeni profil eklemek tek dosyada**: Örneğin `spor_programi` için kolay genişleme
- **Diğer paketlere temel**: Paket 2 (diarization) bu paketin üzerine kurulur

### Maliyet

**Yaklaşık 1 günlük iş.** Davranış matrisi `profiles.py`'de tablo halinde, `pipeline.py`'de dispatch, test parametrize, 1 docstring güncellemesi.

### Bağımlılıklar
- Yok

---

## 4. Persistent worker

### Ne demek?

**Şu anki davranış** ("one-shot"):
1. Process başlat
2. Model yükle (~5 sn — `large-v3-turbo` CTranslate2 ~1.5 GB VRAM)
3. Klibi işle (örn. 30 sn)
4. Process bitir (model VRAM'den düşer)
5. Sonraki klip için 1-4'ü tekrarla

**Persistent worker davranışı**:
1. Process başlat (1 kez)
2. Model yükle (1 kez, sonsuza kadar VRAM'de)
3. Queue'dan iş al
4. İşle
5. 3'e dön (sonsuz döngü)

### Şu an ne var?

- ✅ `_MODEL_CACHE` dict ([core/pipelines/asr/models.py:55](../core/pipelines/asr/models.py)) — process-içi cache var; bir koşumda 2. çağrı modeli yeniden yüklemiyor
- ✅ [core/jobs/worker.py](../core/jobs/worker.py) `DummyWorker` (71 satır) — Sprint 2 state-flow için iskelet, ASR-spesifik değil generic
- ✅ [core/jobs/repository.py](../core/jobs/repository.py), `step_runner.py`, `errors.py` — job lifecycle altyapısı
- ✅ `JobRun` / `JobStatus` schema'ları kullanılabilir durumda
- ❌ ASR-spesifik persistent worker yok
- ❌ Job queue gerçek değil (DB veya Redis bağlantısı yok)
- ❌ `_MODEL_CACHE` thread-safe değil ([derin analiz HIGH-4](#)) — persistent worker concurrency açtığında race condition

### Ne yapılacak?

```python
# core/pipelines/asr/worker.py (yeni — şu an mevcut iskelet kabul edilen dosya)

import time
from threading import Lock

from core.jobs.repository import JobRepository
from core.pipelines.asr.models import FAST_MODEL, QUALITY_MODEL, load_model
from core.pipelines.asr.vad import load_silero_vad_model
from core.pipelines.asr.diarize import load_pyannote_pipeline  # opsiyonel
from core.pipelines.asr.pipeline import run_asr_pipeline


class AsrWorker:
    def __init__(self, repository: JobRepository, *, with_diarization: bool = True):
        self.repository = repository
        self.cache_lock = Lock()
        # Modelleri bir kez yükle — load_model() in-process cache'i kullanır
        self.fast_model = load_model(FAST_MODEL)
        self.quality_model = load_model(QUALITY_MODEL)
        self.vad_model = load_silero_vad_model()
        self.diarize_pipeline = load_pyannote_pipeline() if with_diarization else None

    def run_forever(self):
        while True:
            job = self.repository.find_next_pending()
            if job is None:
                time.sleep(1.0)
                continue
            try:
                result = run_asr_pipeline(
                    job.input_path,
                    content_profile=job.metadata["content_profile"],
                    # ... model/vad/diarize zaten yüklü, function bunları cache'den alır
                )
                self.repository.mark_done(job.job_id, result.module_run)
            except Exception as exc:
                self.repository.mark_failed(job.job_id, str(exc))

    def shutdown(self):
        # GPU release için (gerekirse)
        del self.fast_model
        del self.quality_model
        # ...


# Çalıştırma:
# python -m core.pipelines.asr.worker --queue-backend sqlite
```

**Bonus**: `_MODEL_CACHE` için lock ekle ([derin analiz HIGH-4](#) gediği):

```python
# models.py
import threading

_MODEL_CACHE_LOCK = threading.Lock()


def load_model(config: ModelConfig) -> Any:
    cache_key = (str(config.model_path), config.device, config.compute_type)
    with _MODEL_CACHE_LOCK:
        if cache_key in _MODEL_CACHE:
            return _MODEL_CACHE[cache_key]
        # ... yükle
        _MODEL_CACHE[cache_key] = model
        return model
```

### Niye önemli?

- **TRT arşivi tek seferlik değil** — yüzlerce saat içerik. v0.1 demo 38 sn'de bitti ama bunun ~5 sn'si model yüklemekti. 500 klip × 5 sn = ~42 dakika boşa giderdi.
- **Streaming demo** (Karar M9 streaming) — WebSocket üzerinden canlı transcript için worker zaten ayakta olmalı. Hot start, cold start farkı kullanıcı için 5 saniye gecikme demek.
- **GPU verimliliği** — Model VRAM'de kalır, decode hızı artar (warm vs cold). Ayrıca pyannote yükleme zamanı da ek (~3 sn).
- **Karar 12** ("ASR child process abnormal exit izleniyor") — bu sorunu kalıcı çözmek için worker-level retry / restart politikası gerek.

### Maliyet

**Yaklaşık 2-4 günlük iş.**
- Job lifecycle entegrasyonu (~1 gün)
- Error handling, restart politikası (~1 gün)
- VAD ve pyannote için ayrı cache mekanizmaları (~0.5 gün)
- Smoke test + load test (~0.5 gün)
- HIGH-4 thread-safety lock + test (~0.5 gün)

### Bağımlılıklar
- Yok ama Paket 1, 2, 3 buraya entegre olmuş olmalı (daha güvenli sırada en son yapılır)

---

## 5. TRT verisi eşik kalibrasyonu

### Ne demek?

Tüm eşikler **şu an MediaSpeech TR + 20 segmentlik smoke testten geliyor**. MediaSpeech ≠ TRT arşivi:

| Boyut | MediaSpeech TR | TRT arşivi |
|---|---|---|
| Kayıt yaşı | Modern (2020+) | 1980'lerden günümüze |
| Mikrofon kalitesi | Uniform, temiz | Çok çeşitli (analog band, dijital, telefon hattı) |
| Ortam | Stüdyo + outdoor | Stüdyo + saha + arşiv kasetleri |
| Konuşma stili | Spontan + okuma karışık | Bültenler (formal), filmler (diyalog), eski programlar (çeşitli) |
| Speaker overlap | Az | Bültenlerde + panellerde var |
| Background noise | Az | Eski kayıtlarda kaset tıngırtısı, müzik bedi, sokak gürültüsü, applause |

Şu anki kalibrasyon (bunlar değişebilir):

| Parametre | Şu an | Nereden geldi | Kaynak dosya |
|---|---|---|---|
| `max_uncovered_tail_seconds` | 3.0 | MediaSpeech 430d0aaf örneğinden gözle | quality.py:190 |
| `max_uncovered_tail_ratio` | 0.25 | Aynı örnek | quality.py:191 |
| `max_words_per_second` | 5.0 | Whisper hallucination literature'ündan | quality.py:194 |
| `segment_repetition_min_run` | 20 | beyaz1 disaster örneğinden | quality.py:47 |
| `segment_max_token_length` | 80 | hihihi disaster örneğinden | quality.py:48 |
| `coverage_tolerance_seconds` | 1.0 | Sezgi | transcribe.py:384 |
| `coverage_tolerance_ratio` | 0.05 | Sezgi | transcribe.py:385 |
| `no_speech_hard_threshold` | 0.6 | Whisper default | quality.py:37 |
| `avg_logprob_hard_threshold` | -1.0 | Whisper default | quality.py:38 |

### Şu an ne var?

- ✅ Benchmark scripti hazır: [scripts/asr_mediaspeech_benchmark.py](../scripts/asr_mediaspeech_benchmark.py) — parametrik (audio dir, reference dir, output dir argümanları)
- ✅ MediaSpeech 20-segment baseline mevcut: [outputs/external_turkish_transcripts_asr_smoke_20/benchmark_results.md](../outputs/external_turkish_transcripts_asr_smoke_20/benchmark_results.md)
- ✅ TRT 14 WAV benchmark zaten koşulmuş: [outputs/asr_archive_all_wav_benchmark/](../outputs/asr_archive_all_wav_benchmark/) — ama bu fast/quality karşılaştırması, eşik kalibrasyonu değil. Reference transcripts olmadığı için WER hesaplanamadı.
- ❌ TRT için **reference transcripts (gold metinler) yok** — bu nedenle WER hesaplanamıyor
- ❌ Fallback trigger rate analizi yok
- ❌ False positive / false negative oranları bilinmiyor

### Ne yapılacak (TRT transcriptleri geldiğinde)?

```
1. TRT WAV + TXT çiftlerini hazırla (zaten benchmark altyapısı var)
   - Veri konumu büyük ihtimal: 
     \\depo01cifs.int.trt.net.tr\sas_h264\testset\
   - Ya da yeni gelecek bir transcript havuzu

2. Benchmark koşumu:
   python scripts/asr_mediaspeech_benchmark.py \
       --audio-dir /trt/transcripts/wav/ \
       --reference-dir /trt/transcripts/txt/ \
       --output outputs/trt_calibration_run_1/

3. Üç eksende analiz:
   a) Per-clip WER ve CER ölçümü (fast vs quality)
   b) Fallback tetik istatistiği:
      - tail_gap_uncovered kaç kez fired?
      - Bu trigger'larda fast aslında haklı mıydı, yanlış mıydı?
      - False positive (fast iyi, ama biz fall back ettik) sayısı
      - False negative (fast kötü, ama biz görmedik) sayısı
   c) Quality drop oranları:
      - stock_artifact tetik sayısı
      - repetition_collapse / long_token oranı

4. HIGH önemli gediklerin etkisi:
   - HIGH-2 (very_low_logprob fallback'i tetiklemiyor) gerçek veride ne kadar 
     sorun? Drop count'larıyla bak.
   - HIGH-3 (tail-gap AND-gate dead zone) → kısa/orta TRT kliplerinde örnek 
     yakala, OR-gate veya scaled threshold gerek mi karar ver.

5. Eşik tuning (örn.):
   - Eğer tail_gap %20 false-negative rate gösteriyorsa → 
     max_uncovered_tail_ratio 0.20'ye çek
   - Eğer 10 saniyelik kliplerde sürekli kuyruk kaybı yaşanıyorsa → 
     AND gate'i OR yap (HIGH-3)
   - Eğer fast %5'ten az fallback gerektiriyorsa → 
     eşikleri sıkı tut (zaten az tetikleniyor)
   - Eğer fast %30'dan fazla fall back ediyorsa → 
     belki direkt quality profili daha mantıklı

6. Kararı Karar 24'ün devamı olarak Karar Günlüğü'ne yaz (Karar 26 olabilir):
   - Yeni eşik değerleri + sayısal gerekçe
   - "v1.0 production politikası kilitlendi" notu

7. mutfak/05_AKTIF_GOREV.md / mutfak/03_GUNCEL_DURUM.md güncelle
```

### Niye önemli?

- **v0.1 thresholds eğitimli tahmin, production gerçeği değil** — gerçek başarısızlık oranını bilmiyoruz. Şu an "umutla çalışıyor".
- **Karar 23 hâlâ koşullu**: *"TRT desteklerse `large-v3-turbo default + large-v3 selective fallback` kilitlenir."* Yani şu an karar koşullu. TRT verisi olmadan v1.0 üretime gidemeyiz.
- **HIGH-2 + HIGH-3 bağımlı**: [Derin analiz](#) raporundaki bu iki gediği kapatmadan önce TRT verisine bakmak doğru olur — belki ihtiyaç yok (etkisi küçük), belki gediğin etkisi büyük (önce kapat sonra koş). Bunu data göstersin.
- **Üst denetim katmanı (Phase 2)** TRT veriyle birlikte aktive olacak; eşikler oturduktan sonra üst-denetim modeli için pencere açılır.

### Maliyet

- **TRT transcriptleri gelmeden 0** (bekleyen iş, blocked)
- **Geldikten sonra 2-3 günlük iş**:
  - Benchmark koşumu (~saatler, GPU-bound)
  - Analiz (~yarım gün)
  - Eşik tuning + dokümantasyon (~1 gün)
  - Regression test (~yarım gün)
  - Karar Günlüğü güncellemesi (~1 saat)

### Bağımlılıklar
- **TRT iç transcript havuzu** — geliştirme dışı paydaşa bağlı (TRT içi veri sahibi)

---

## 6. Özet karşılaştırma tablosu

| # | İş | Kod hazırlığı | Eksik | Maliyet | Engelleyen |
|---|---|---|---|---|---|
| 1 | WhisperX entegrasyonu | Subprocess sleeve hazır | `align.py` + pipeline kanca | 1-2 gün | — |
| 2 | Diarization profil bazlı | `diarize.py` 214 satır hazır | Profile dispatch + segment-speaker merge | 2-3 gün | Paket 3 |
| 3 | Profile dispatch | Karar 15 dokümante | `profiles.py` + pipeline parametre | 1 gün | — |
| 4 | Persistent worker | DummyWorker iskelet | ASR-spesifik worker + cache lock | 2-4 gün | — (kısmen Paket 1-3) |
| 5 | TRT kalibrasyonu | Benchmark scripti parametrik | TRT data + gold metinler | 2-3 gün (data sonrası) | **TRT veri** |

**Toplam ASR olgunlaşma süresi:** ~8-13 gün (TRT verisi geldiğinde +2-3 gün). Tek başına çalışan bir geliştirici için 2-3 hafta lık bir sprint paketi.

---

## 7. Pratik sıralama önerisi

**TRT verisini beklerken yapılabilecek sıra:**

```
1. Paket 3 (Profile dispatch)        — 1 gün, diğer her şeye temel
   ↓
2. Paket 2 (Diarization)             — 2-3 gün, kod hazır, demo değeri yüksek
   ↓
3. Paket 1 (WhisperX)                — 1-2 gün, UI showcase için kritik
   ↓
[TRT verisi gelir]
4. Paket 5 (TRT kalibrasyon)         — 2-3 gün, v1.0 için kritik
   ↓
5. Paket 4 (Persistent worker)       — 2-4 gün, production-grade gereklilik
```

**Gerekçeler:**

- **Paket 3 önce** çünkü Paket 2 ona bağımlı, ve Paket 4'ün ASR worker'ı bu API'ye yaslanacak. Hızlı ve kapsayıcı temel.
- **Paket 2 ikinci** çünkü kod %90 hazır; pipeline entegrasyonu nispeten hızlı. Demo değeri çok yüksek — bültende "kim konuştu" görmek showcase'i besler.
- **Paket 1 üçüncü** çünkü UI/showcase için karaoke-style word highlight gerekiyor. Subprocess sleeve hazır, hızlı entegrasyon.
- **Paket 5 dördüncü** çünkü TRT verisi gelmeden yapılamaz; gelince hemen koşulur.
- **Paket 4 son** çünkü production-grade gereklilik; dev sırasında one-shot pipeline çağrısı yeterli. Persistent worker eklerken Paket 1-2-3 koduyla beraber test edilebilir.

**Alternatif sıralama** (eğer TRT verisi yakın zamanda geliyorsa):
```
1. Paket 3 → 2. Paket 5 (gelir gelmez) → 3. Paket 2 → 4. Paket 1 → 5. Paket 4
```

Bu alternatif kalibrasyonu önce yaparak HIGH-2 ve HIGH-3 gediklerinin gerçek veri etkisini erkenden ölçer; sonra Paket 2 (diarization) eklenirken bu gediklerin de iyileştirmesi gelir.

---

## Çapraz referanslar

- [docs/SPRINT_4_ASR_V0_1_DONE.md](SPRINT_4_ASR_V0_1_DONE.md) — v0.1 kapanış raporu
- [docs/MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md](MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md) — Profil tanımları ve davranış matrisi
- [mutfak/04_YOL_HARITASI.md](../mutfak/04_YOL_HARITASI.md) §v0.1.x — Yol haritası girdisi
- [mutfak/06_KARARLAR_GUNLUGU.md](../mutfak/06_KARARLAR_GUNLUGU.md) Karar 14, 15, 16, 23, 24, 25
- [mutfak/05_AKTIF_GOREV.md](../mutfak/05_AKTIF_GOREV.md) — Aktif görev (v0.1 kapandı, v0.2 hazır)
- [mutfak/09_UST_DENETIM_KATMANI.md](../mutfak/09_UST_DENETIM_KATMANI.md) — Phase 2 üst denetim (WhisperX word timestamps gerektiren)
