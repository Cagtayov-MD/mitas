# 03 — GÜNCEL DURUM

> Son güncelleme: 2026-06-02
> Son değişen bölüm: §0.6 — 2026-06-02 durum senkronu: üç canlı pipeline (ASR/OCR/Translate), test gerçeği, commit temizliği

Bu dosya **şu an nerede olduğumuzu** anlatır. Yapılmış olanlar, eksik kalanlar, açık kararlar, riskler. Her gelişme ile güncellenir.

---

## 0.6 2026-06-02 durum senkronu — üç canlı pipeline, test gerçeği, commit temizliği

Bu dosya 2026-05-18'de (§0.5) donmuştu; aradaki ~2 haftada gerçek ilerledi. Bu bölüm
gerçeği yakalar.

**Artık üç üretim pipeline'ı + Tedial entegrasyonu var** (eskiden "sadece ASR" idi):

- **ASR — 🟢 en olgun.** `core/pipelines/asr/` (19 modül) + `asr_server.py` + WebUI.
  v0.1 + derin audit + WhisperX hizalama + 5 içerik profili + diarization + stereo/channel
  auto + entity normalizasyon + canlı STT preview. Yeni modüller: `align.py`,
  `language_intelligence.py`, `word_timing.py`, `version.py`.
- **OCR (künye/jenerik) — 🟡 yoğun POC, yarısı entegre.** İki paralel hat (Karar: MODEL 1/2
  karışmasın). **MODEL 1 (frame-first)** `core/pipelines/ocr/`: text-first göç + K-BoxTrack
  + slit-scan + credit motion state machine + mosaic yöntemleri + V2.1 OneOCR fallback.
  **MODEL 2 (panorama-first)** `model2/` paket iskeleti + `E:\MITAS\OCR-worktree/` keşif alanı
  (kanonik `ocr-opus-final.md`). Reconstruction 2×2 matrisi **kapandı**; tek açık gerçek iş
  **"bekçi"** (film ↔ jenerik ayrımı, GÖZ `qwen2.5vl` + `dy`). En taze iş 2026-06-01:
  panorama + qwen_transcribe + consensus (OCR-worktree, commit'siz keşif).
- **Translate (MT) — 🟢 YENİ, çalışır, entegre.** `core/pipelines/translate/` (8 modül, ~930 satır).
  OPUS-MT EN→TR hızlı yol + NLLB-3.3B çok-dilli; Arapça/Levanten lehçe tespiti (`dialect.py`);
  izole `translate` venv'de subprocess; `asr_server` `/api/translate/segments` endpoint'ine bağlı.
  Bu pipeline 05-18 dokümanında hiç yoktu.
- **Tedial — 🟡 PoC.** `core/api/tedial/` arşiv arama+izleme; router artık fastapi'yi sert import ediyor.

Henüz **yazılmamış** (§5.1 hâlâ geçerli): Face, Audio Activity, Song Recognition, Visual Tag,
Timeline merge, Review UI backend. (Face için v0.4 planı yazıldı: `docs/MITAS_v0_4_Face_Recognition_Plan_Final.md`.)

**Test gerçeği (dürüst):** Proje per-modül venv mimarisinde; **tek venv'den tüm suite koşmuyor.**
`core` venv'de `pytest tests/` → 366 passed, 37 skipped, **23 "failed" — hepsi ortamsal**
(numpy/fastapi `core` venv'de yok). Doğrulandı: OCR row-reconstruct testleri `ocr` venv'de 21/21
geçiyor; translate/tedial testleri `asr` venv'de (fastapi) geçer. Tedial paketi artık `core`
venv'de collect bile olmuyor (fastapi import zinciri). Yani kod yeşil ama suite venv'e göre bölünmüş.

**Commit temizliği (2026-06-02):** Çalışma ağacında ~250 untracked + 56 modified birikmişti
(çoğu generated). `.gitignore` genişletildi (Karar 38 / PARK-OCR-001: `outputs/_*`, experiment
dizinleri, scratch `scripts/_*`, data dump'ları, `OCR-worktree/`, GORSELLER). Gerçek kaynak 6
mantıklı commit'e bölündü: gitignore, asr, translate, ocr (MODEL 1), model2 iskeleti, api+webui,
docs. Push yapılmadı.

---

## 0. 2026-05-13 hızlı durum notu

ASR tarafı 2026-05-11 envanterinden ileridedir: `core/pipelines/asr/` altında production wrapper, profile routing, quality guard, channel split/merge ve Phase 2 hook iskeletleri bulunuyor. `core/pipelines/asr/phase2/` şu an bilinçli olarak stub durumunda: speaker merge ve entity normalization için kapı açıldı ama çalışan Qwen/VLM entegrasyonu yok.

Bugünkü ana fikir: Phase 2 sadece "transcript düzeltme" değil, **MITAS Üst Denetim Katmanı** olacak. Model, ASR/OCR/metadata çıktısına yukarıdan bakacak; özel isim hatası, quoted evidence, tabela/fiş/kart, tarihsel anakronizm, OCR/ASR çelişkisi ve bağlam kırığı gibi durumlarda kanıt isteyebilecek.

Yeni referans dosyası: `mutfak/09_UST_DENETIM_KATMANI.md`.

Geçici model sıralaması:
- Default text üst-denetim adayı: `google/gemma-4-26b-a4b`
- Kalite lideri / ikinci görüş: `qwen/qwen3.6-27b`
- Alternatif Qwen adayı: `qwen/qwen3-30b-a3b-2507`
- Audit/hakem: `meta/llama-3.3-70b`
- Görsel kanıt / OCR crop / frame review: `nvidia/nemotron-3-nano-omni` ve ayrıca ayrı testte `qwen/qwen2.5-vl-7b`

Önemli prensip: Model karar verici hakim değildir; **kanıt isteyen denetçidir**. `replace_allowed=true` yalnızca normal konuşma ASR hatası, dolu canonical, uygun confidence ve deterministik kapı onayı varsa geçerlidir.

---

## 0.2 2026-05-14 ASR v0.1 kapatma paketi (smoke geçti)

ASR dikey diliminin v0.1 kalan dört maddesi tamamlandı:

- **Schema bağlantısı:** `TimelineEvent` emit eklendi. Her clean_segment artık bir `asr_segment` event'i olarak `outputs/.../timeline_events.json` içine yazılıyor. `confidence = exp(avg_logprob)` ile normalize, `source_module="asr"`, `evidence_ids=[module_run_id]`. `ModuleRun` zaten bağlıydı.
- **Kalite raporu standardı:** `summary.json` artık `model_name`, `fallback_triggered`, `fallback_reason`, `selection_reason`, `clean_segments`, `quality_drops`, `timeline_event_count`, `vad.speech_ratio` (+ speech_seconds, segment_count), `safety.diagnostics` (uncovered_tail dahil) alanlarını taşıyor.
- **Smoke test:** `tests/test_asr_v0_1_smoke.py` golden-file testi yazıldı — 9 madde, ModuleRun ve TimelineEvent schema doğrulaması dahil. `core` venv'de pytest ile koşuyor (ASR runtime gerekmeden).
- **Demo output:** `outputs/asr_v0_1_demo/` altında 5 artifact üretildi. Klip seçimi: 001_h1 (TRT haber kameramanları, 101.7 sn, `\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav\H1.wav`). Sonuç: profile_used=fast (turbo geçti, fallback yok), 15 clean segment, 15 TimelineEvent, VAD speech_ratio=0.849, safety geçti. Üretim: `scripts/asr_v0_1_demo.py` (asr venv ile koşulur).

Test sayısı: 45 mevcut + 9 v0.1 smoke = 54 yeşil.

Sıradaki: TRT transcript havuzu gelince benchmark + tail-gap/coverage eşik kalibrasyonu. Ayrıca sprint kapatma (I — master plan §2.1 karşılaştırması, L — `docs/SPRINT_4_ASR_V0_1_DONE.md` arşiv raporu) açık.

---

## 0.3 2026-05-14 ASR audit kapanışı (worktree port + 9 fix + Karar 27)

ASR modülü için derinlemesine audit (HIGH-1..HIGH-5, MED-1..MED-6, LOW-1..LOW-3) ana `E:\MITAS` workspace üzerinde kapatıldı. İş üç parçaya ayrıldı:

- **Worktree port (DONE-ASR-001):** Önceki turda `.claude/worktrees/awesome-gould-1ee408` altında kalan 4 düzeltme (`multilingual=True` Karar 14, `_MODEL_CACHE_LOCK`, `CRITICAL_FALLBACK_DROP_PREFIXES` extend, `speech_seconds` magic clamp temizliği) ana workspace'e taşındı.
- **Audit fix (DONE-ASR-002):** 9 gerçek bug kapatıldı.
  - HIGH-1: `_select_fallback_result` "iki taraf da unsafe" yalan loglama → `degraded_both_unsafe` dalı, daha uzun coverage'lı taraf seçilir.
  - HIGH-3: Tail-gap AND-gate ölü bölgesi → `effective_max_tail = min(3.0, expected_speech_end * 0.15)` dinamik eşik.
  - MED-1: `error_flags` literal içerik sızıntısı → kategorik prefix (`drop.reason.split(":", 1)[0]`).
  - MED-2: İkinci `_empty_result` dalında VAD kwargs eksikti → eklendi.
  - MED-3: `evidence_ids=[module_run_id]` semantik yanlıştı → `evidence_ids=[]` (gerçek Evidence v0.2 WhisperX ile gelecek).
  - MED-4: Legacy `transcribe_vad_segments` tail-gap params yoktu → `expected_speech_end` + `transcript_last_end` geçildi.
  - MED-6: `channel_merge.py` `max()` ile `vad_speech_ratio` alt sınır raporluyordu → `_union_ratio_bound(L, R) = min(1.0, L+R)` üst sınır helper'ı, docstring ile bound olarak işaretli.
  - LOW-1: `_segment_confidence(NaN)` 1.0 dönebiliyordu → `math.isfinite` guard.
  - LOW-2: TimelineEvent payload'a `source_chunk_index` eklendi.
  - Yan etki: `_fallback_failure_reason` sıralaması drop-first'e çevrildi (drop sebebi tail-gap'in genelde root cause'u). 3 test senaryosu rebalance edildi.
- **Karar 27 (DONE-ASR-003):** Production `condition_on_previous_text` default `True` → `False`. Operasyonel scriptlerle uyum + hallucination yayılımı kapatma + fallback yükü azaltma. TRT kalibrasyonu A/B sonucu beklemekte.

Doğrulama: `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` → **166 passed, 6 skipped** (TEST-ASR-AUDIT-001). 6 skip = real_media GPU testleri.

Açık takip için: `mutfak/05_AKTIF_GOREV.md` §0 canlı pano, `mutfak/06_KARARLAR_GUNLUGU.md` Karar 27.

---

## 0.4 2026-05-16 WhisperX ana pipeline ve hybrid kalite ölçümü

WhisperX artık ASR ana pipeline'a bağlı: `word_alignment_mode` default'u `whisperx`; API/WebUI normal upload yolu `content_profile=bulten_haber`, `diarize=auto`, `channel_mode=auto`, `word_alignment_mode=whisperx` ile job açıyor. Split kanal seçilse bile diarization için ayrıca mono mix üretiliyor. Flat WhisperX `word_segments`, zaman örtüşmesiyle orijinal ASR segmentlerine dağıtılıyor; coverage yanlış düşük görünmüyor.

Kalite ölçümü küçük gold-probe setinde yapıldı. Üç gerçek referanslı klipte default `bulten_haber`/`large-v3-turbo` weighted WER `16.57%`, CER `12.98%`; `bulten_haber + quality override`/`large-v3` weighted WER `14.24%`, CER `11.35%` verdi. Her iki hatta WhisperX coverage `3/3 ok, min 1.000`, diarization `3/3 ok`, safety `3/3 safe`.

Karar etkisi: `large-v3` bazı kliplerde daha iyi olsa da turbo önceki TRT-domain geniş koşumlarda birçok alanda daha sağlıklı/stabil davrandığı için production yönü değişmedi: `large-v3-turbo` default, `large-v3` selective/hybrid repair modeli. WhisperX metin doğruluğunu doğrudan artıran model değil; kelime timestamp, timeline, evidence, coverage ve repair sonrası yeniden hizalama omurgasıdır.

Ek uygulama: "ciddi fark" listesinin ilk üç kalite işi ürün yoluna alındı. Selective quality repair artık `fallback_report` ile chunk arbitration raporu veriyor; VAD gap repair `vad_gap_uncovered` pencerelerini selective ASR onarımına bağlıyor; entity/özel isim normalizasyonu `normalized_text`, `normalized_transcript`, `normalized_entities` olarak reviewable çıktı üretiyor ve ASR metnini sessizce ezmiyor.

Kalan uygulama: WhisperX düşük coverage durumunda eksik segmentleri tek retry eder; diarization+WhisperX birleşimi `quality_report.speaker_word_timeline` bloğuyla ölçülür; entity önerileri Qwen/üst-denetim için evidence packet taşır; WebUI timeline seçili/zoomlu segmentlerde kelime timestamp tick'lerini gösterir. Gerçek Qwen hakem çağrısı ve insan etiketli diarization benchmark ayrı Faz2/ölçüm işi olarak kalır.

Retest: ASR hedefli regresyon `46 passed`, ASR wildcard `139 passed, 9 skipped`, WebUI type-check/build geçti. Full `pytest tests -q` `257 passed, 10 skipped, 3 failed`; fail'ler ASR dışı model manifest sayaç beklentisi (`candidate_count` 24 yerine 27). Üç gerçek gold-probe current pipeline retestinde clean transcript eski çıktıyla birebir aynı kaldı; weighted WER `0.1562`, weighted CER `0.1122`, alignment `3/3 ok`, diarization `3/3 ok`. Transcribe süresi aynı seviyede kaldı; toplam runtime artışı ana olarak diarization varyansından geldi. Rapor: `outputs/asr_current_pipeline_retest_20260516/retest_report.md`.

Altın not: ASR+WhisperX tarafında şu an yapılanlar güvenli altyapı ve doğru kalite sinyali tarafını sağlamlaştırdı. Bir sonraki gerçek kalite sıçraması entity sözlüğünü TRT kişi/kurum/program listesiyle büyütmek, gerçek Qwen evidence hakemini bağlamak ve çok-konuşmacılı insan etiketli diarization benchmark kurmaktır.

Referanslar:
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 32
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 33
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 34
- `mutfak/08_TEST_KLIPLER.md` §8.5-§8.7
- `outputs/asr_current_pipeline_quality_20260516/report.md`

---

## 0.5 2026-05-18 RADYO_G_NLER kalibrasyonu — stock artifact, stereo redundancy, channel_mode default, content profile wire

Bir radyo müzik programı klibinde (`RADYO_G_NLER.mp4`) üç somut sorun çıktı: müzik/sessizlik üzerine üretilen İngilizce stok hallüsinasyonlar (`Thank you`, `© transcript Emily Beynon`), L ve R kanallarının neredeyse %99 aynı çıkması (aynı sesin iki kez transkribe edilmesi) ve `muzik_programi` content profile'ında tanımlı `initial_prompt="Turkce muzik programi"` + `beam_size=5` parametrelerinin Whisper'a hiç ulaşmaması. Bu üç sorun bu turda kapatıldı, her üçü de `master` üzerinde.

Yapılanlar:

- **STOCK_ARTIFACTS genişletildi:** `quality.py:STOCK_ARTIFACTS` listesine plain English Whisper hallüsinasyon kalıpları eklendi (`thank you`, `transcript emily beynon`, `subtitles by`, `amara org`, vb.). Normalize sonrası eşleştiğinden `thank you.` gibi noktalama varyantı eklenmez. Bu hallüsinasyonlar artık `quality_drop` olarak düşer ve transcript'e sızmaz.
- **Stereo redundancy analyzer (observable katman):** `channel_analysis.py` içine `analyze_stereo_redundancy()` eklendi. Split mode'da L ve R üzerinde 5 sn pencerelerle Pearson korelasyonu + Mid/Side dB ölçer; `pearson_median ≥ 0.90 AND midside_db ≤ -10.0` olduğunda `is_redundant_stereo=True`. `pipeline.py` bu sonucu summary.json `channels.stereo_analysis` bloğuna yazar; split zorla forced edilmiş (yani `auto_decided=false`) ve aynı zamanda redundant ise `channels.channel_decision_override = "forced_split_despite_redundant_stereo"` flag'ini basıyor ve log'a WARNING düşüyor. Karar 35.
- **`channel_mode` default `mono → auto`:** `run_asr_pipeline()` ve `_run_asr_pipeline()` (Tedial job runner) varsayılan kanal modu `auto` yapıldı. Artık pipeline kendisi L/R korelasyonuna bakarak mono/split kararını veriyor; varsayılan davranış olarak iki kanal aynı kaynaktan geliyorsa otomatik mono'ya iniyor. Karar 36.
- **Content profile parametre propagasyonu (DONE-ASR-004 teknik borç kapanışı):** `TranscribeParams` dataclass'ına `beam_size: int | None = None` alanı eklendi (None = model_config default'u kullan). `transcribe()` artık `transcribe_params: TranscribeParams | None` parametresi alıyor ve tüm `_run_single_pass` çağrı noktalarına (quality / fast / fast_with_fallback fast-first + selective fallback + full-quality eskalasyon, 5 nokta) ile `_transcribe_chunk()`'a iletiyor. `pipeline.py` içine `_build_transcribe_params()` helper'ı eklendi; content profile verildiyse `beam_size` ve `initial_prompt` override'larıyla `TranscribeParams` üretip L, R ve mono `transcribe()` çağrılarının üçüne birden geçiriyor. Legacy `content_profile=None` çağrıları `None` aldığından `DEFAULT_TRANSCRIBE_PARAMS`'a düşer, mevcut davranış değişmez. `muzik_programi` artık gerçekten `initial_prompt="Turkce muzik programi"` ile decode ediyor.

Test durumu: Bu turda hedefli ASR regresyonu `tests/test_asr_stereo_redundancy.py tests/test_asr_pipeline.py tests/test_asr_channel_analysis.py` → 16 passed. Gerçek RADYO_G_NLER re-run henüz koşulmadı; üretim sunucusu (asr_server uvicorn, no-reload) elle restart sonrası TRT klibiyle yeniden ölçülmesi gerekiyor.

Referanslar:
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 35 (stereo redundancy observable katman)
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 36 (channel_mode default auto)
- `mutfak/08_TEST_KLIPLER.md` §8.8

---

## 0.1 2026-05-14 ASR model / fallback checkpoint

Bugün ASR model politikası netleştirildi: production default decode `large-v3-turbo`; `large-v3` ise selective fallback / üst denetim modeli. Eski "large-v3 ana motor" mirası karar günlüğünde revize edildi.

Dış Türkçe transcript kaynakları indirildi ve incelendi:
- MediaSpeech Turkish / OpenSLR108: `E:\MITAS\cache\external_datasets\mediaspeech_tr\`; 2,513 WAV + 2,513 TXT, yaklaşık 10 saat. Bugün için en değerli geçici ASR prob seti.
- Common Voice Turkish 25.0: `E:\MITAS\cache\external_datasets\common_voice_tr_25\`; 126,510 MP3, yaklaşık 135 saat. Ana TRT-domain karar seti değil, yardımcı kısa-utterance Türkçe kontrol korpusu.

20 MediaSpeech segmentlik benchmark sonucu:
- `fast / large-v3-turbo`: WER 0.1853, CER 0.0966, decode 14.098 sn.
- `quality / large-v3`: WER 0.1775, CER 0.0961, decode 48.773 sn.
- Örnek bazında: 8 quality galibiyeti, 6 fast galibiyeti, 6 eşitlik.

Kod tarafında `fast_with_fallback` adaptif hale getirildi:
- Tail-gap / uncovered-tail safety tetikleyicisi eklendi.
- Fallback sonrası `large-v3` sonucu kör kabul edilmiyor; quality unsafe veya coverage olarak belirgin kötüyse turbo korunuyor.
- Seçim nedeni `selection_reason` ile archive/summary tarafına taşınıyor.

Gerçek doğrulama: MediaSpeech `430d0aaf-8f12-4a09-964d-aa75f4157100` klibinde eski kod turbo ile 14.8 sn sesin 7.42 sn'sinde kalıyordu. Yeni kod `tail_gap_uncovered` ile fallback tetikledi ve `large-v3` 14.04 sn kapsama verdi.

Referanslar:
- `outputs/external_turkish_transcripts_review.md`
- `outputs/external_turkish_transcripts_asr_smoke_20\benchmark_results.md`
- `mutfak/06_KARARLAR_GUNLUGU.md` Karar 22-24.

---

## 1. Tek paragrafta durum

Sözleşme katmanı (Pydantic + JSON Schema), job runner skeleton (worker / repository / step_runner / errors), modüler venv altyapısı, dokümantasyon ve output raporları hazır. Master plan v5 ve uygulama planı v1 yazıldı. ASR tarafında production wrapper ve kalite/channel altyapısı oluştu; **diğer production pipeline'lar henüz yok**: face, OCR/KJ, visual tag, WebSocket bridge ve frontend backend bağlantısı bekliyor. UI panel iskelet halinde (Figma export, mock data).

Sonraki çekirdek odak: **v0.1 — ASR dikey dilim**. Düzgün şekilde ayağa kaldırılacak.

---

## 2. Hazır altyapı

### 2.1 Sözleşme katmanı (TAMAM)

`core/schemas/`:
- `candidate_relation.py`
- `common.py`
- `evidence.py`
- `job_run.py`
- `media.py`
- `module_run.py`
- `timeline.py`

`schemas/` altında JSON Schema export'ları:
- `candidate_relation.schema.json`
- `evidence.schema.json`
- `job_run.schema.json`
- `media_item.schema.json`
- `module_run.schema.json`
- `timeline_event.schema.json`

### 2.2 Job runner skeleton (TAMAM)

`core/jobs/`:
- `errors.py`
- `repository.py`
- `step_runner.py`
- `worker.py`

### 2.3 Test seti (47 test)

`tests/` altında schema testleri, job retry / partial / repository testleri, smoke testleri.

### 2.4 Dokümantasyon (22 doküman)

`docs/` altında öne çıkanlar:
- `MITAS_Master_Plan_Denetimli_v5.md` (kök dizinde)
- `MITAS_Uygulama_Plani_v1.md` (kök dizinde)
- `MITAS_3_5_Karar_Dokumanlari_Denetim_Raporu.md`
- `MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md`
- `MITAS_ASR_Torch_Env_Lock_v1.md`
- `MITAS_Benchmark_Plani_v1.md`
- `MITAS_Environment_Lock_Health_Check_v1.md`
- `MITAS_Faster_Whisper_Env_Lock_NoDownload_Guard_v1.md`
- `MITAS_Faster_Whisper_Import_Smoke_v1.md`
- `MITAS_GPU_CUDA_Driver_Kesfi_v1.md`
- `MITAS_Karar_Denetim_Checklist_v1.md`
- `MITAS_Lightweight_Paket_Kurulum_Raporu_v1.md`
- `MITAS_Model_Env_Inventory_v1.md`
- `MITAS_Model_Manifest_ve_Smoke_Test_Plani_v1.md`
- `MITAS_Model_Smoke_Test_Raporlama_v1.md`
- `MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md`
- `MITAS_Pip_Dryrun_Raporlama_v1.md`
- `MITAS_Profile_Routing_Kaba_Kararlar_v1.md`
- `MITAS_Requirements_Denetim_ve_Kurulum_Sirasi_v1.md`
- `MITAS_Requirements_Taslaklari_v1.md`
- `MITAS_Torch_CUDA_ASR_Smoke_v1.md`
- `SPRINT_1_CORE_SCHEMA_DONE.md`
- `SPRINT_2_JOB_WORKER_DONE.md`
- `SPRINT_3_BENCHMARK_PLAN_DONE.md`

### 2.5 Benchmark şablonları

`benchmark_templates/`:
- `asr_benchmark.yaml`
- `audio_activity_benchmark.yaml`
- `face_benchmark.yaml`
- `ocr_kj_benchmark.yaml`
- `visual_tag_benchmark.yaml`

`benchmark_registry.yaml` kökte.

### 2.6 Output raporları (34 dosya)

`outputs/` altında kurulum / smoke / env lock / pip dryrun JSON raporları. Bunlar her bir setup adımının audit kaydıdır.

### 2.7 Setup scripts (21 script)

`scripts/` altında:
- `asr_emergency_transcribe.py`
- `asr_pyannote_pipeline.py`
- `export_json_schema.py`
- `inspect_gpu_cuda.py`
- `inspect_model_envs.py`
- `install_faster_whisper_smoke.py`
- `install_lightweight_packages.py`
- `install_torch_cuda_asr.py`
- `lock_and_check_envs.py`
- `lock_asr_torch_env.py`
- `lock_faster_whisper_env.py`
- `run_model_smoke_tests.py`
- `run_pip_dryrun_reports.py`
- `validate_benchmark_yaml.py`
- `validate_model_manifest.py`

---

## 3. venv envanteri

9 primary venv ve 1 legacy venv, her biri `venvs/` altında.

| Venv | Yol | Amaç | Ana paketler | Eksik |
|---|---|---|---|---|
| **core** | `venvs/core` | Schema/test | pydantic 2.13.4, pytest 9.0.3, PyYAML 6.0.3 | AI paketleri yok |
| **asr** | `venvs/asr` | Birleşik ASR/STT runtime | faster-whisper 1.2.1, silero-vad 6.2.1, pyannote-audio 4.0.4, librosa 0.11.0, torch+CUDA, fastapi 0.136.1, uvicorn 0.46.0, websockets 16.0, onnxruntime 1.23.2 | whisperx yok; DeepFilterNet artık primary denoise yolu değil |
| **alignment** | `venvs/alignment` | WhisperX word-level alignment sleeve | whisperx 3.8.5, torch/torchaudio 2.8.0+cu126, torchcodec 0.7.0 | torchcodec direct decode FFmpeg 8 ile uyumsuz ama alignment yolunda dormant |
| **denoise** | `venvs/denoise` | DeepFilterNet denoise sleeve | DeepFilterNet 0.5.6, DeepFilterLib 0.5.6, numpy 1.26.4, torch/torchaudio 2.8.0+cu126, soundfile 0.12.1 | Python 3.10 fallback; 3.11 sistemde yok |
| **stt** | `venvs/stt` | Legacy STT venv | legacy_stt_venv, deprecated_as_primary_runtime, do_not_delete_yet | primary runtime değil |
| **ocr** | `venvs/ocr` | OCR | oneocr 1.0.12, paddleocr 3.5.0, paddlepaddle 3.3.1, pytesseract 0.3.13, opencv 4.13 | EasyOCR ignore edildi; sistem `tesseract.exe` yok |
| **face** | `venvs/face` | Yüz tespit/track | insightface 0.7.3, onnxruntime-gpu 1.23.2, supervision 0.28.0, opencv 4.13, hdbscan 0.8.42, pgvector 0.4.2, torch+CUDA | fastapi yok |
| **visual** | `venvs/visual` | Görsel tag | ultralytics 8.4.48, transformers 5.8.0, scenedetect 0.7, torch+CUDA | GroundingDINO, RAM paket olarak yok |
| **audio** | `venvs/audio` | Ses sınıflandırma | tensorflow 2.21.0, tensorflow-hub 0.16.1, librosa, soundfile, pydub | torch yok (TF tabanlı) |
| **tag** | `venvs/tag` | Türkçe NLP | zeyrek 0.1.3, nltk 3.9.4, rapidfuzz 3.14.5, regex | — |

Her venv için `locks/{venv}.freeze.txt` ve `locks/{venv}.inspect.json` dosyaları mevcut.

---

## 4. Sistem araçları

| Araç | Durum | Not |
|---|---|---|
| ffmpeg | ✅ PATH'te | Gyan 8.1.1 full-shared build; torchcodec için shared DLL'ler erişilebilir |
| ffprobe | ✅ PATH'te | Gyan 8.1.1 full-shared build |
| nvidia-smi | ✅ Erişilebilir | NVIDIA driver mevcut, GPU görünür |
| fpcalc | ✅ PATH'te | Chromaprint binary (Song Recognition için) |
| tesseract | ❌ Binary yok | `pytesseract` Python paketi var ama backend olmadan kullanılamaz |
| chromaprint kütüphane | ❌ Pip paketi yok | `fpcalc` binary mevcut, bu yeterli olabilir |

GPU/CUDA durumu: `docs/MITAS_GPU_CUDA_Driver_Kesfi_v1.md` içinde kayıtlı.

---

## 5. Henüz yazılmamış olanlar

### 5.1 Üretim pipeline kodu

Hiçbir modülün gerçek pipeline kodu yok:

- ❌ ASR pipeline (orchestration: VAD → faster-whisper → WhisperX → diarization → kalite raporu)
- ❌ Face pipeline (orchestration: detector → tracker → clustering → bank lookup)
- ❌ OCR/KJ pipeline (ROI-first → OCR → temporal merge → event)
- ❌ Audio Activity Layer pipeline
- ❌ Song Recognition pipeline
- ❌ Visual Tag pipeline
- ❌ Timeline merge layer
- ❌ Review UI backend

### 5.2 Demo / showcase

- ❌ FastAPI + WebSocket backend skeleton
- ❌ Streaming ASR akışı (chunk → push)
- ❌ Streaming face tracking
- ❌ Tıkla-seç-takip showcase logic'i
- ❌ Frontend (HTML + canvas overlay)

### 5.3 Veri tarafı

- 🟡 Ham test klip havuzu var: `E:\MITAS\testklipler\` (envanter: `mutfak/08_TEST_KLIPLER.md`)
- 🟡 Dış transcript probu var: MediaSpeech TR ve Common Voice TR 25 `cache/external_datasets/` altında. MediaSpeech geçici gold/probe; Common Voice yardımcı korpus.
- ❌ TRT iç transcript havuzu henüz workspace'e bağlanmadı; final ASR kararının gerçek gold kaynağı o olacak.
- 🟡 Benchmark sprint'lerinin ilk dış veri koşumu tamamlandı; TRT verisinde tekrar koşulacak.

### 5.4 UI

- 🟡 UI panel iskelet halinde — Figma export, mock data
- ❌ Backend bağlantısı yok
- ❌ Sözleşme uyumsuzlukları var (Bkz. `MITAS_Gorsel_Tagleme_Plani.md`'deki notlar ve dün yapılan UI eleştirisi)

---

## 6. Aktif açık kararlar

Detay: `06_KARARLAR_GUNLUGU.md`'de listelenir, burada özet:

1. **Demo backend için venv stratejisi** — canlı transcript `ASR > streaming_transcription` olarak `asr` venv içinde ele alınır; face tarafı ayrı karar bekler.
2. **Sunum hedefi** — axle.ai bağlamı nedeniyle 3-5 günde stream demo planlanmıştı; geliştirici "acele kararları geri çekiyorum, önce ASR'yi düzgün ayağa kaldırmak" dedi. Sunum hâlâ ileride ama bu klasör artık demo değil ana proje takibi.
3. **OCR motoru seçimi** — PaddleOCR hattıyla ilerlenir; OneOCR/Tesseract sadece karşılaştırma/fallback bağlamında kalır. EasyOCR 2026-05-21 kararıyla aktif test/benchmark kapsamından çıkarıldı. Tesseract binary yok, fallback için kurulması gerekir.
4. **WhisperX / alignment** — karar verildi: `asr` venv'e kurulmaz, `alignment` venv'de subprocess sleeve olarak çalışır. Word-level alignment smoke yeşil.
5. **Pyannote** — `asr` venv'inde var. Torchcodec/FFmpeg hazırlığı tamamlandı; v0.1 smoke'da kullanımı sprint başlangıcında yeniden değerlendirilecek.
6. **ASR model politikası** — karar verildi: default `large-v3-turbo`; `large-v3` selective fallback / üst-denetim modeli. TRT transcriptleri gelince eşik kalibrasyonu yapılacak.

---

## 7. Geliştirici durumu (10 Mayıs 2026 akşamı)

- 26 saatlik tek oturum bitti (8-9 Mayıs); 15 saat uyku ile resetlendi.
- 10 Mayıs akşamı 22:00 itibarıyla yeni çalışma dönemine geçildi.
- Bundan sonraki tempo: günde 10-12 saat, gece kesin uyku.
- Bu klasör tam bu dönüm noktasında — "acele 3 günlük demo" çerçevesinden "ana projeye geri dön" çerçevesine geçişte — oluşturuldu.

---

## 8. UI panel durumu

Güncel UI takip dosyası açıldı:

- `mutfak/10_UI_NOTLARI.md`

Aktif çalışma dizini:

- `E:\MITAS\.claude\worktrees\wonderful-vaughan-884d20\webui\`

İlk kaynak: geliştiricinin paylaştığı **Medya_Yapay_Zeka_Kontrol_Paneli.zip** / Figma export iskeleti.

İçerik:
- React + Vite + Tailwind + shadcn/ui
- İki ana sekme: Analysis Workstation + FaceBank Builder
- Header, VideoPlayer, Timeline, Sidebar (Uyarılar/ASR/Yüzler/Etiketler/OCR/Bilgi/Kanıt)
- ASR API proxy'si mevcut: `/api` → `http://localhost:8787`
- UI artık gerçek ASR job sonucunu `segments`, `summary`, `archive.quality` alanlarından gösteriyor.

2026-05-14 UI davranış düzeltmeleri:

- Upload artık otomatik ASR başlatmıyor. Dosya sadece hazırlanıyor; ASR kullanıcı `ASR Başlat` dediğinde çalışıyor.
- Dosya seçilince görünür hazır mesajı basılıyor: `erd_test_sound.wav ASR için hazır`.
- `DEMO MODU` rozeti kaldırıldı.
- `İnceleme bekliyor` dili kaldırıldı; sağ panel `Uyarılar`, segment güveni `yüksek/orta/düşük güven` şeklinde.
- Klavye: `Space`/`K` play-pause, `J` 10 sn geri, `L` 10 sn ileri.
- Timeline-ASR çift yönlü senkronlandı: timeline segmenti sağ ASR satırını, ASR satırı timeline/video konumunu seçiyor ve vurguluyor.
- Doğrulama: `tsc --noEmit` ve `vite build` geçti; `http://127.0.0.1:5173/` 200 döndü.

ASR/UI sözleşme kararı:

- ASR modeli/pipeline değişip API sözleşmesi aynı kalırsa UI değişmez.
- Endpoint, response şekli, gönderilen profil/parametre veya yeni görsel özellik değişirse UI da güncellenir.

Tespit edilen sözleşme/disiplin sapmaları:
- Mock'ta yabancı ünlü face match örnekleri (Michael Jordan) — vizyonla çelişiyor, kaldırılmalı.
- Status vocabulary master plan ile uyumsuz (approved/pending/rejected vs raw/auto/needs_review/confirmed).
- Audio Activity ve Song Performance track'leri yok.
- Speaker / Face cluster / Person ID ayrımı net değil.
- Tag review queue item'ı var (v1.1'de olmalı).
- Türkçe / İngilizce karışıklığı.
- Job status göstergesi yok.
- CandidateRelation kavramı UI'da temsil edilmiyor.

Not: Bu listenin bir kısmı 2026-05-14 UI düzeltmeleriyle kapandı. Detay ve yeni UI işleri artık `mutfak/10_UI_NOTLARI.md` içinde tutulacak. Kalıcı ürün kararları `06_KARARLAR_GUNLUGU.md` içine ayrıca geçirilecek.

---

## 9. Risk notları

- **Tek kişi olmak:** Tüm rol tek kişide — yorgunluk birikimi en büyük risk.
- **Demo baskısı geri çekildi ama sunum gündemi hâlâ var:** Şu an karar verildi, ASR ana odak. Ama sunum geri gelirse hızlı bir batch demo (önceden işlenmiş video + UI panel'de gösterim) yedek plan olarak hazırlanabilir.
- **Lisans kontrolü askıda:** InsightFace / buffalo_l, YOLO-World, OneOCR production lisansları hâlâ doğrulanmadı.
- **KVKK retention sayıları taslak halde:** 30 gün gibi rakamlar avukatla doğrulanmadan production'a sızmamalı.

---

## 10. Şimdiki adım

ASR v0.1 dikey dilimi kodca tamam (bkz. §0.2): schema bağlantısı, kalite raporu, smoke test, demo output yeşil. 54 test geçiyor. Sonraki adım: TRT transcript havuzu gelince aynı benchmark şeklini TRT-domain WAV/TXT çiftlerinde koşup tail-gap (3.0 sn AND %25) ve coverage seçici eşiklerini kalibre etmek; ardından sprint kapatma (master plan §2.1 karşılaştırması + `docs/SPRINT_4_ASR_V0_1_DONE.md`).
