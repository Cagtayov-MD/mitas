# 05 — AKTİF GÖREV

> Son güncelleme: 2026-06-02
> Son değişen bölüm: §0.1 — 2026-06-02 senkron: Translate pipeline + OCR build-out kayda geçti, test gerçeği, commit temizliği, aktif cephe = OCR bekçi

Bu dosya **şu an aktif olarak üzerinde çalışılan sprinttir**. Her sprint biterken arşivlenir veya tamamen yeniden yazılır. Genellikle tek bir sürümün dikey dilimine odaklanır.

---

## 0. Canlı takip panosu

Bu bölüm "nerede kaldık?" ve "şunu yaptık mı?" sorularının ilk cevabıdır. En üst kural `00_BURADAN_BASLA.md` §0, ayrıntı protokolü `12_CANLI_MUTFAK_PROTOKOLU.md` içindedir. Her yardımcı iş bitince burayı günceller.

### 0.1 Nerede kaldık? / Şunu yaptık mı?

- **2026-06-02 SENKRON (bu dosya 05-18'de donmuştu, gerçek ilerledi):**
  - Artık **üç canlı pipeline + Tedial** var: ASR (en olgun) · OCR künye (MODEL 1 entegre + MODEL 2
    iskeleti/keşif) · **Translate (MT) — YENİ** (OPUS+NLLB, lehçe, `asr_server /api/translate/segments`).
    Tam tablo + test gerçeği: `03_GUNCEL_DURUM.md` §0.6.
  - **Aktif gerçek cephe = OCR "bekçi"** (film ↔ jenerik ayrımı). Reconstruction 2×2 kapandı;
    yanlış segment (footage) beslenince çöp üretiyor. Aday GÖZ `qwen2.5vl` + `dy`; test seti hazır,
    ground-truth koşumu bekliyor. Detay: `OCR-worktree/ocr-opus-final.md` "BEKÇİ TEST SETİ".
  - **Test gerçeği:** `core` venv `pytest tests/` → 366 passed + 23 ortam-kaynaklı fail (numpy/fastapi
    `core`'da yok; `ocr`/`asr` venv'de geçer). Tek venv'den full-suite koşmuyor — per-modül venv.
  - **Commit temizliği yapıldı:** `.gitignore` genişletildi (generated/scratch/worktree), gerçek
    kaynak 6 mantıklı commit'e bölündü (gitignore/asr/translate/ocr/model2/api+webui/docs). Push yok.
  - Commit'siz bilinçli bırakılanlar: standalone `scripts/*.py` araçları, `OCR-worktree/` keşfi,
    generated `outputs/`. Bunlar in-flight; istenince ayrıca ele alınır.
- ASR v0.1 dikey dilimi kodca büyük ölçüde tamamlandı; ASR derin audit (HIGH-1..HIGH-5, MED-1..MED-6, LOW-1..LOW-3) ana `E:\MITAS` workspace üzerinde kapatıldı, worktree port + Karar 27 tamamlandı.
- Audit kapanış komutu: `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` → 166 passed, 6 skipped (TEST-ASR-AUDIT-001).
- Canonical workspace `E:\MITAS`; `.claude/worktrees/...` altında yapılan işler ana workspace'e otomatik geçmiş sayılmaz.
- Opus/Claude worktree karışıklığı için kalıcı protokol `11_WORKTREE_KOORDINASYON.md` içine yazıldı.
- Mutfak artık canlı kaynak kabul ediliyor; iş/test/karar/erteleme kayıtları bu dosya ve ilgili mutfak dosyalarına işlenecek.
- Kullanıcı "şunu yaptık mı?" diye sorduğunda ilk kontrol bu dosyanın "Son yapılanlar / kapananlar" ve "Sonraya bırakılanlar" bölümleridir; karar gerekiyorsa `06_KARARLAR_GUNLUGU.md` ile doğrulanır.
- Tüm takip maddeleri ID ile tutulur (`PARK-*`, `TASK-*`, `DONE-*`, `TEST-*`, `DEC-*`) ve sabit durum sözlüğü kullanılır: `Açık`, `Ertelendi`, `Karar bekliyor`, `Devam ediyor`, `Yapıldı`, `Test edildi`, `Kapatıldı`, `İptal edildi`.

### 0.1.1 ALTIN NOT — Bir sonraki gerçek kalite sıçraması

ASR+WhisperX tarafında şu an yaptıklarımız güvenli altyapı ve doğru kalite sinyali tarafını sağlamlaştırdı. **Bundan sonraki en büyük gerçek kalite sıçraması** üç işten gelir:

1. Entity sözlüğünü TRT kişi / kurum / program listesiyle büyütmek.
2. Gerçek Qwen evidence hakemini bağlamak: ASR span + WhisperX timestamp + OCR/KJ/frame evidence ile karar verdirmek.
3. Çok-konuşmacılı, insan etiketli diarization benchmark kurmak.

Bu not unutulmayacak: sıradaki "daha iyi kalite" işi model değiştirmekten önce bu üçlüdür.

### 0.2 Sonraya bırakılanlar / açık park listesi

| ID | Tarih | Konu | Neden ertelendi / açık kaldı | Tekrar açma koşulu | Durum |
|---|---|---|---|---|---|
| PARK-ASR-001 | 2026-05-14 | Opus worktree'sindeki 4 ASR düzeltmesini ana `E:\MITAS` workspace'e port etme | Düzeltmeler `.claude/worktrees/awesome-gould-1ee408` altında kaldı; ana workspace'e uygulanmadı | — | Kapatıldı (2026-05-14, DONE-ASR-001) |
| PARK-ASR-002 | 2026-05-14 | ASR `condition_on_previous_text` production default kararı | Audit False öneriyor; mevcut production test True bekliyor; Karar Günlüğü'nde net kayıt yok | — | Kapatıldı (2026-05-14, Karar 27 / DONE-ASR-003) |
| PARK-OCR-001 | 2026-05-21 | OCR çalışma ağacı temizliği ve PaddleOCR GPU hattı | EasyOCR aktif kapsamdan çıkarıldı; `outputs/ocr_credit_experiments/` gibi üretilmiş çıktılar commitlenmemeli, OCR kod/karar değişiklikleri ayrı commitlenmeli | PaddleOCR GPU/cu126 kurulumu öncesi `.gitignore` ve stage planı uygulanır | Açık |

### 0.3 Son yapılanlar / kapananlar

| ID | Tarih | İş | Dosyalar | Kanıt/Test | Durum | Not |
|---|---|---|---|---|---|---|
| DONE-MUTFAK-001 | 2026-05-14 | Worktree karışıklığı için kalıcı koordinasyon notu eklendi | `11_WORKTREE_KOORDINASYON.md`, `00_BURADAN_BASLA.md`, `README.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | Canonical workspace `E:\MITAS` olarak yazıldı |
| DONE-MUTFAK-002 | 2026-05-14 | Canlı Mutfak protokolü kuruldu | `12_CANLI_MUTFAK_PROTOKOLU.md`, `00_BURADAN_BASLA.md`, `README.md`, `05_AKTIF_GOREV.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | Her iş/test/karar/erteleme için kayıt zorunlu hale getirildi |
| DONE-MUTFAK-003 | 2026-05-14 | "Şunu yaptık mı?" sorgusu için canlı pano kuralı eklendi | `12_CANLI_MUTFAK_PROTOKOLU.md`, `05_AKTIF_GOREV.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | İlk kaynak `05_AKTIF_GOREV.md`; gerekirse `06` ve `07` ile doğrulanır |
| DONE-MUTFAK-004 | 2026-05-14 | `00_BURADAN_BASLA.md` en üst otorite yapıldı; `12` ayrıntı kılavuzu olarak netleştirildi | `00_BURADAN_BASLA.md`, `README.md`, `12_CANLI_MUTFAK_PROTOKOLU.md`, `05_AKTIF_GOREV.md`, `06_KARARLAR_GUNLUGU.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | Okuma sırası çelişkisi giderildi: `05` aktif görev, `04` yol haritasından önce okunur |
| DONE-MUTFAK-005 | 2026-05-14 | `00_BURADAN_BASLA.md` akış/organizasyon dosyası olarak yeniden tanımlandı | `00_BURADAN_BASLA.md`, `README.md`, `12_CANLI_MUTFAK_PROTOKOLU.md`, `05_AKTIF_GOREV.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | Diğer mutfak dosyaları içerik dosyası olarak konumlandı |
| DONE-MUTFAK-006 | 2026-05-14 | Canlı pano profesyonel takip standardına geçirildi | `00_BURADAN_BASLA.md`, `12_CANLI_MUTFAK_PROTOKOLU.md`, `05_AKTIF_GOREV.md`, `06_KARARLAR_GUNLUGU.md`, `README.md` | Doküman değişikliği; test koşulmadı | Kapatıldı | ID formatı, sabit durum sözlüğü, tamamlandı kriteri ve zorunlu rapor başlığı eklendi |
| DONE-ASR-001 | 2026-05-14 | Worktree'deki 4 ASR düzeltmesi ana E:\MITAS'a port edildi (HIGH-5 multilingual=True, HIGH-4 _MODEL_CACHE_LOCK, HIGH-2 fallback prefix extend, LOW-3 magic clamp temizliği) | `core/pipelines/asr/models.py`, `core/pipelines/asr/transcribe.py` | TEST-ASR-AUDIT-001 | Kapatıldı | PARK-ASR-001 kapatıldı |
| DONE-ASR-002 | 2026-05-14 | ASR audit 9 fix uygulandı (HIGH-1 _select_fallback_result both-unsafe dürüst raporlama, HIGH-3 tail-gap dinamik eşik, MED-1 error_flags prefix-only, MED-2 _empty_result VAD kwargs, MED-3 evidence_ids=[], MED-4 legacy tail-gap params, MED-6 channel_merge union bound helper, LOW-1 NaN guard, LOW-2 source_chunk_index) + _fallback_failure_reason drop-first sırası + 3 test rebalance | `core/pipelines/asr/transcribe.py`, `core/pipelines/asr/quality.py`, `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/channel_merge.py`, `tests/test_asr_transcribe.py`, `tests/test_production_transcribe.py` | TEST-ASR-AUDIT-001 | Kapatıldı | Audit `_select_fallback_result` yalan logging, kısa klip tail-gap ölü bölge, error_flags içerik sızıntısı vb. tüm gerçek bug'lar kapatıldı |
| DONE-ASR-003 | 2026-05-14 | Karar 27 — production `condition_on_previous_text=False` default | `core/pipelines/asr/models.py`, `tests/test_production_transcribe.py`, `mutfak/06_KARARLAR_GUNLUGU.md` | TEST-ASR-AUDIT-002 | Kapatıldı | PARK-ASR-002 kapatıldı; TRT kalibrasyonu A/B sonucu beklemekte |
| DONE-ASR-004 | 2026-05-14 | v0.1.x Paket 1 — Profile dispatch (5 içerik profili) eklendi. Yeni `profiles.py` (`ContentProfile` + `CONTENT_PROFILES` + `get_content_profile`/`list_content_profiles`). `run_asr_pipeline()` artık `content_profile` (opsiyonel), `model_profile_override`, `diarize_override`, `diarize_required` parametrelerini alıyor. Eski `profile=...` çağrıları backwards-compatible. Resolution mantığı `_resolve_profile_inputs` ile özetlendi; summary'ye `content_profile`, `content_profile_metadata`, `diarize_intent`, `diarize_required` alanları yazılıyor. Diarize çağrısı Paket 2'de wiring edilecek; Paket 1 sadece intent surfacing yapıyor. | `core/pipelines/asr/profiles.py` (yeni), `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/__init__.py`, `tests/test_asr_content_profile.py` (yeni) | TEST-ASR-PD-001 | Kapatıldı | Karar 15 davranış matrisi koda indi; `bulten_haber`/`studio_panel`/`muzik_programi`/`film`/`belgesel`. `beam_size` + `initial_prompt` profile'da tutuluyor ama transcribe propagasyonu Paket 1.x veya 2'de eklenecek (teknik borç). |
| DONE-ASR-005 | 2026-05-15 | v0.1.x Paket 2 — Diarization profil bazlı çağrı entegre edildi. Yeni `merge.py` (`SpeakerMergeConfig` + `merge_speakers_into_segments`); Karar 15 graceful degradation eşiği `min_speaker_overlap_ratio=0.5` ile her TranscriptSegment'e `speaker_id` atanıyor (overlap altı `null`). `pipeline.py`'a `_run_diarization_if_requested` + `_classify_diarization_status` + `_resolve_job_status`/`_resolve_error_message` helper'ları eklendi. `quality_report.diarization` artık gerçek değer (`ok` / `degraded` / `failed` / `skipped` / `not_applicable`) + `speaker_count`/`speakers`/`low_confidence_segments`/`runtime_sec` taşıyor. Karar 16 graceful fail → `JobStatus.partial`; strict mode (`diarize_required=True`) raise eder. Split-channel diarization scope dışı (`skipped:split_channel_unsupported_v0_1_x`). | `core/pipelines/asr/merge.py` (yeni), `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/__init__.py`, `tests/test_asr_merge.py` (yeni), `tests/test_asr_pipeline_diarization.py` (yeni), `tests/test_asr_content_profile.py` (diarize_required testi monkeypatch ile fix) | TEST-ASR-DIAR-001 | Kapatıldı | Karar 15 + Karar 16 davranış matrisi pipeline'a indi. Gerçek pyannote çağrısı sadece content_profile dispatch ile tetikleniyor; split-channel + diarization birleşik akışı sonraki sprint. |
| DONE-ASR-006 | 2026-05-16 | WhisperX ana pipeline'a bağlandı ve Web/API normal yolunda aktif hale geldi. `word_alignment_mode` default'u `whisperx`; API upload default'u `content_profile=bulten_haber`, `diarize=auto`, `channel_mode=auto`, `word_alignment_mode=whisperx`. WhisperX flat `word_segments` artık zaman örtüşmesiyle orijinal ASR segmentlerine dağılıyor; coverage yanlış düşük görünmüyor. Split kanal seçilse bile diarization için ayrıca mono mix üretiliyor. WebUI upload ASR content profile + WhisperX parametresi gönderiyor. | `core/pipelines/asr/align.py`, `core/pipelines/asr/pipeline.py`, `core/api/asr_server.py`, `webui/src/app/asr-api.ts`, `tests/test_asr_alignment.py`, `tests/test_asr_pipeline_diarization.py`, `tests/test_asr_upload_dedup_api.py` | TEST-ASR-WX-001 | Kapatıldı | WhisperX metin doğruluğunu doğrudan artırmaz; kelime timestamp, evidence, timeline ve kalite coverage omurgasıdır. Hybrid kalite kararı için bkz. DEC-ASR-K32-001. |
| DONE-ASR-007 | 2026-05-16 | "Ciddi fark yaratan" ilk 3 ASR kalite yatırımı ürün yoluna alındı: selective quality repair artık `fallback_report` ile hangi chunk'ın neden `large-v3` onarımına gittiğini, hangisinin turbo kaldığını raporluyor; VAD gap repair `vad_gap_uncovered` pencerelerini selective ASR onarımına bağlıyor; entity/özel isim normalizasyonu deterministic lexicon ile `normalized_text`, `normalized_transcript`, `normalized_entities` üretip archive/summary/timeline/review çıktılarına giriyor. | `core/pipelines/asr/transcribe.py`, `core/pipelines/asr/result.py`, `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/channel_merge.py`, `core/pipelines/asr/phase2/entity_normalization.py`, `core/pipelines/asr/__init__.py`, `tests/test_production_transcribe.py`, `tests/test_asr_entity_normalization.py` | TEST-ASR-Q3-001 | Kapatıldı | Entity normalizasyonu ASR metnini ezmez; reviewable ikinci katman olarak kalır. Qwen/kanıt döngüsü sonraki Faz2 işidir. |
| DONE-ASR-008 | 2026-05-16 | Kalan ASR+WhisperX kalite yatırımları ürün yoluna alındı: WhisperX düşük coverage durumda eksik segmentleri bir kez retry eder; diarization+WhisperX birleşimi `quality_report.speaker_word_timeline` bloğuyla speaker+word coverage raporlar; entity önerileri Qwen'e hazırlanacak kanıt paketi (`evidence.source_text`, `normalized_text`, timestamp, speaker/channel, word timestamps varsa) taşır; WebUI timeline seçili/zoomlu segmentlerde word timestamp tick'lerini gösterir. | `core/pipelines/asr/align.py`, `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/phase2/entity_normalization.py`, `tests/test_asr_alignment.py`, `tests/test_asr_pipeline_diarization.py`, `tests/test_asr_entity_normalization.py`, `webui/src/app/asr-api.ts`, `webui/src/app/components/Timeline.tsx` | TEST-ASR-WX-REST-001 | Kapatıldı | Gerçek Qwen hakem çağrısı ve insan etiketli diarization benchmark hâlâ ayrı Faz2/benchmark işidir; burada ürün sözleşmesi ve güvenli ara katman tamamlandı. |
| DONE-ASR-009 | 2026-05-18 | `STOCK_ARTIFACTS` listesi plain English Whisper hallüsinasyon kalıplarıyla genişletildi (`thank you`, `transcript emily beynon`, `subtitles by`, `amara org` vb.). RADYO_G_NLER müzik/sessizlik pencerelerinde üretilen "Thank you", "© transcript Emily Beynon" gibi stok artefaktlar artık `quality_drop:stock_artifact` ile düşer ve transcript'e sızmaz. `normalize_quality_text` noktalama strip'lediği için `thank you` ile `thank you.` aynı; çift varyant yazılmadı. | `core/pipelines/asr/quality.py` | TEST-ASR-RADYO-001 | Kapatıldı | Ezberlenmiş İngilizce hallüsinasyon ailesi domain-agnostik; ileride Türkçe domain hallüsinasyonu görülürse aynı listede genişler. |
| DONE-ASR-010 | 2026-05-18 | Stereo redundancy analyzer eklendi: split mode'da L ve R üzerinde Pearson korelasyon (5 sn pencere) + Mid/Side dB ölçer; `pearson_median ≥ 0.90 AND midside_db ≤ -10.0` redundant kabul edilir. Sonuç `summary.json` `channels.stereo_analysis` bloğuna yazılır; forced split + redundant durumunda `channel_decision_override="forced_split_despite_redundant_stereo"` flag'i + log WARNING basılır. Operatör artık duplicate transkripsiyon riskini summary'den okur. | `core/pipelines/asr/channel_analysis.py`, `core/pipelines/asr/pipeline.py`, `tests/test_asr_stereo_redundancy.py` (yeni) | TEST-ASR-RADYO-001 | Kapatıldı | Karar 35. Eşikler audit-first observable yaklaşımıyla seçildi; gerçek TRT split-kanal kliplerinde kalibre edilecek. |
| DONE-ASR-011 | 2026-05-18 | `run_asr_pipeline()` ve Tedial `_run_asr_pipeline()` default `channel_mode` `"mono"` → `"auto"` çevrildi. Pipeline artık L/R korelasyonuna bakarak mono/split kararını kendi verir; varsayılan davranış olarak iki kanal aynı kaynaktan geliyorsa otomatik mono'ya iner. Eski "mono default" yanıltıcı çünkü stereo girdiler ya sessizce kırpılıyor ya da bilinçsizce split moda zorlanıyordu. | `core/pipelines/asr/pipeline.py`, `core/api/tedial/job_runner.py` | TEST-ASR-RADYO-001 | Kapatıldı | Karar 36. Forced `channel_mode="split"` operatör override'ı olarak kalır; observable katman (DONE-ASR-010) yanlış override'ı yakalar. |
| DONE-ASR-012 | 2026-05-18 | `ContentProfile.beam_size` ve `initial_prompt` parametreleri gerçekten `faster-whisper.model.transcribe()` çağrısına ulaşıyor (DONE-ASR-004 teknik borcu kapandı). `TranscribeParams`'a `beam_size: int \| None = None` alanı eklendi; `transcribe()` yeni `transcribe_params: TranscribeParams \| None` parametresi alır ve 5 `_run_single_pass` çağrı noktasına + `_transcribe_chunk()`'a iletir. `pipeline.py:_build_transcribe_params()` content profile'dan override üretip L, R ve mono `transcribe()` çağrılarının üçüne birden geçirir. Legacy `content_profile=None` çağrıları `DEFAULT_TRANSCRIBE_PARAMS`'a düşer; davranış değişmez. `muzik_programi` artık gerçekten `initial_prompt="Turkce muzik programi"` ile decode eder. | `core/pipelines/asr/models.py`, `core/pipelines/asr/transcribe.py`, `core/pipelines/asr/pipeline.py`, `core/pipelines/asr/profiles.py` | TEST-ASR-RADYO-001 | Kapatıldı | DONE-ASR-004'ün "transcribe propagasyonu Paket 1.x veya 2'de eklenecek (teknik borç)" notu kapatıldı. |

### 0.4 Son gerçek testler

| ID | Tarih | Workspace / cwd | Komut | Sonuç | Not |
|---|---|---|---|---|---|
| TEST-DOC-001 | 2026-05-14 | `E:\MITAS` | Bu protokol değişikliği için test koşulmadı | N/A | Sadece dokümantasyon değişikliği |
| TEST-DOC-002 | 2026-05-14 | `E:\MITAS` | `rg` ile mutfak protokol ifadeleri ve okuma sırası kontrol edildi | N/A | Dokümantasyon tutarlılık kontrolü; pytest koşulmadı |
| TEST-DOC-003 | 2026-05-14 | `E:\MITAS` | `rg` ile ID önekleri, durum sözlüğü ve tamamlandı kriteri kontrol edildi | N/A | Dokümantasyon tutarlılık kontrolü; pytest koşulmadı |
| TEST-ASR-AUDIT-001 | 2026-05-14 | `E:\MITAS` | `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` | 166 passed, 6 skipped | 6 skip = real_media GPU testleri; tüm ASR audit fix + Karar 27 sonrası tam suit yeşil |
| TEST-ASR-AUDIT-002 | 2026-05-14 | `E:\MITAS` | `pytest tests/test_production_transcribe.py tests/test_asr_transcribe.py tests/test_asr_pipeline.py tests/test_asr_quality.py tests/test_asr_channel_merge.py -q` | 50 passed | Karar 27 (`condition_on_previous_text=False`) sonrası ASR core suit yeşil |
| TEST-ASR-PD-001 | 2026-05-14 | `E:\MITAS` | `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` | 187 passed, 7 skipped | v0.1.x Paket 1 sonrası tam suit yeşil; yeni 21 content_profile/dispatch testi eklendi |
| TEST-ASR-DIAR-001 | 2026-05-15 | `E:\MITAS` | `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` | 205 passed, 7 skipped | v0.1.x Paket 2 sonrası tam suit yeşil; +18 yeni test (test_asr_merge.py 11, test_asr_pipeline_diarization.py 7) + Paket 1 test'inde 1 monkeypatch fix |
| TEST-ASR-WX-001 | 2026-05-16 | `E:\MITAS` | `venvs/core/Scripts/python.exe -m pytest tests/test_asr_alignment.py tests/test_asr_pipeline.py tests/test_asr_pipeline_diarization.py tests/test_asr_content_profile.py tests/test_asr_upload_dedup_api.py tests/test_asr_v0_1_smoke.py tests/test_production_transcribe.py -q`; ASR wildcard suite; WebUI `pnpm type-check` + `pnpm build`; gerçek current pipeline gold-probe ölçümü | Hedefli: 65 passed, 2 skipped. ASR wildcard: 136 passed, 9 skipped. WebUI type-check/build passed. Gold-probe current pipeline: WhisperX 3/3 ok coverage 1.0, diarization 3/3 ok, safety 3/3 safe. | Tüm `pytest tests -q` ayrıca denendi: ASR dışı 3 eski baseline fail var (`candidate_count` 24 bekleniyor, manifest 27 görüyor). ASR kapsamı temiz. Kalite raporu: `outputs/asr_current_pipeline_quality_20260516/report.md` |
| TEST-ASR-Q3-001 | 2026-05-16 | `E:\MITAS` | `venvs/core/Scripts/python.exe -m pytest tests/test_asr_entity_normalization.py tests/test_production_transcribe.py tests/test_asr_pipeline.py tests/test_asr_channel_merge.py tests/test_asr_pipeline_diarization.py tests/test_asr_alignment.py -q` | 45 passed | İlk 3 kalite yatırımı doğrulandı: selective repair raporu, VAD gap selective repair, entity normalization archive/summary/timeline/review sözleşmesi, channel merge ve WhisperX/diarization etkileşimi |
| TEST-ASR-WX-REST-001 | 2026-05-16 | `E:\MITAS` | `venvs/core/Scripts/python.exe -m pytest tests/test_asr_entity_normalization.py tests/test_production_transcribe.py tests/test_asr_pipeline.py tests/test_asr_channel_merge.py tests/test_asr_pipeline_diarization.py tests/test_asr_alignment.py -q`; `cd webui && pnpm type-check`; `cd webui && pnpm build` | ASR: 46 passed. WebUI type-check passed. WebUI build passed. | Build yalnız mevcut büyük chunk uyarısını verdi. Kalan kalite yatırımları: WhisperX retry, speaker+word timeline block, entity evidence packet, WebUI word ticks |
| TEST-ASR-WX-RETEST-001 | 2026-05-16 | `E:\MITAS` | ASR hedefli regresyon; ASR wildcard; WebUI type-check/build; full `pytest tests -q`; üç gerçek gold-probe klip current pipeline retest | ASR hedefli: 46 passed. ASR wildcard: 139 passed, 9 skipped. WebUI type-check/build passed. Full suite: 257 passed, 10 skipped, 3 fail (ASR dışı model manifest `candidate_count` 24->27). Gerçek retest: weighted WER 0.1562, CER 0.1122, alignment 3/3 ok, diarization 3/3 ok, transcript eski çıktıyla birebir aynı. | Rapor: `outputs/asr_current_pipeline_retest_20260516/retest_report.md`. Retestte retry ve entity hit tetiklenmedi; speaker+word timeline 2/3 klipte degraded diyerek gerçek güven sinyali üretti. Pipeline toplamı 75.529s -> 83.687s; fark ana olarak diarization runtime varyansı, transcribe süresi aynı kaldı. |
| TEST-ASR-RADYO-001 | 2026-05-18 | `E:\MITAS` | `./venvs/core/Scripts/python.exe -m pytest tests/test_asr_stereo_redundancy.py tests/test_asr_pipeline.py tests/test_asr_channel_analysis.py -x -q` | 16 passed | DONE-ASR-009..012 sonrası hedefli ASR regresyon. Yeni `test_asr_stereo_redundancy.py` 5 birim test (identical channels → redundant, independent freqs → not redundant, silence → insufficient_data, gain difference → still redundant, `to_dict()` JSON serializable) içerir. Gerçek RADYO_G_NLER re-run henüz koşulmadı; üretim sunucusu (asr_server uvicorn, no-reload) elle restart sonrası TRT klibiyle yeniden ölçülecek. |

### 0.5 Son kararlar

| ID | Tarih | Karar | Durum | Kalıcı kayıt |
|---|---|---|---|---|
| DEC-MUTFAK-001 | 2026-05-14 | `mutfak/` canlı kaynak ve takip sistemi kabul edildi; her yardımcı yaptığı işi buraya raporlamakla yükümlü | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 26, `12_CANLI_MUTFAK_PROTOKOLU.md` |
| DEC-MUTFAK-002 | 2026-05-14 | Canonical workspace `E:\MITAS`; izole worktree'deki iş ana workspace'e port edilmeden tamamlandı sayılmaz | Kapatıldı | `11_WORKTREE_KOORDINASYON.md` |
| DEC-ASR-K27-001 | 2026-05-14 | ASR production default `condition_on_previous_text=False`. Hallucination yayılımı azaltma + operasyonel scriptlerle uyum + fallback yükü azaltma. TRT kalibrasyonu A/B ile teyit edilecek. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 27 |
| DEC-ASR-K32-001 | 2026-05-16 | ASR üretim yönü: `large-v3-turbo` default kalır; `large-v3` selective/hybrid kalite onarımıdır. WhisperX metin doğruluğunu değil kelime timestamp/evidence/timeline/coverage kalitesini artırır. Ciddi fark sırası: WhisperX alignment, selective quality repair, VAD gap repair, entity normalization, diarization+WhisperX, coverage-based retry, WebUI word-level kullanım. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 32, `08_TEST_KLIPLER.md` §8.7 |
| DEC-ASR-K33-001 | 2026-05-16 | İlk 3 kalite yatırımı uygulama kapsamı: selective repair ve VAD gap repair üretim ASR içinde kalır ve `fallback_report` ile izlenir; entity normalization otomatik ASR metnini ezmez, reviewable normalized katman üretir. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 33, `08_TEST_KLIPLER.md` §8.7 |
| DEC-ASR-K34-001 | 2026-05-16 | Kalan ASR+WhisperX kalite yatırımları uygulama kapsamı: düşük coverage retry, speaker+word timeline coverage raporu, entity evidence packet ve WebUI word-level timeline görünümü production sözleşmesine alınır. Gerçek Qwen hakemliği ayrı Faz2 motoru olarak kalır. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 34, `08_TEST_KLIPLER.md` §8.7 |
| DEC-ASR-K35-001 | 2026-05-18 | Stereo redundancy detection observable katmanı: split mode'da L ve R üzerinde Pearson + Mid/Side dB ölçülür, `summary.json` `channels.stereo_analysis` bloğuna yazılır; forced split + redundant durumda `channel_decision_override` flag'i + log WARNING basılır. Eşikler audit-first observable yaklaşımıyla seçildi (pearson_median ≥ 0.90 AND midside_db ≤ -10.0); gerçek TRT split-kanal kliplerinde kalibre edilecek. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 35, `08_TEST_KLIPLER.md` §8.8 |
| DEC-ASR-K36-001 | 2026-05-18 | `run_asr_pipeline()` ve Tedial `_run_asr_pipeline()` default `channel_mode` `auto`. Pipeline kendi L/R korelasyonuna bakar; aynı kaynak iki kanala düştüyse otomatik mono'ya iner. Forced `channel_mode="split"` operatör override'ı olarak kalır; DEC-ASR-K35 observable katmanı yanlış override'ı yakalar. | Kapatıldı | `06_KARARLAR_GUNLUGU.md` Karar 36, `08_TEST_KLIPLER.md` §8.8 |
| DEC-OCR-K38-001 | 2026-05-21 | EasyOCR artık ignore edilir; OCR hattı PaddleOCR ile ilerler. `outputs/ocr_credit_experiments/` üretilmiş çıktı kabul edilir ve commitlenmez; gerçek küçük manifestler ayrıca karar verilerek takip edilir. | Açık | `06_KARARLAR_GUNLUGU.md` Karar 38 |

---

## 1. Aktif sürüm

**v0.1 — ASR dikey dilim**

Hedef: ASR pipeline'ını dürüstçe, smoke test edilebilir şekilde uçtan uca ayağa kaldırmak. Streaming değil, batch. Tek bir Türkçe TRT örneği üzerinde JSON çıktı üretmek.

2026-05-13 ek odak: v0.1 ASR çıktılarını ileride besleyecek **Faz2 Üst Denetim Katmanı** planı netleştiriliyor. Bu iş şu an kodlama değil; model seçimi, benchmark seti, schema ve deterministik kapı tasarımıdır. Detaylar `09_UST_DENETIM_KATMANI.md` dosyasındadır.

2026-05-13 ek ASR benchmark notu: `\\depo01cifs.int.trt.net.tr\sas_h264\testset\wav` altındaki 14 WAV dosyası fast (`large-v3-turbo`) ve quality (`large-v3`) profilleriyle koşuldu. Toplam yaklaşık 682 dakika ses işlendi. Çıktılar `outputs/asr_archive_all_wav_benchmark/` altında; toplu rapor `batch_report.md`, fast/quality fark raporu `model_diff_reports/all_films_fast_quality_confidence.md`, hybrid simülasyon raporu `hybrid_simulation_reports/aggregate_hybrid_simulation.md`.

2026-05-14 karar güncellemesi: ASR default modeli `large-v3-turbo`; `large-v3` selective fallback / üst-denetim modeli. MediaSpeech TR üzerinde 20 segmentlik dış transcript benchmark koşuldu. Quality WER/CER olarak çok az önde, turbo hız olarak belirgin önde; bu yüzden production yönü `fast_with_fallback` olarak sabitlendi. TRT transcriptleri gelince eşikler kalibre edilecek.

Bugünkü kodlama kapanışı: `fast_with_fallback` tail-gap / uncovered-tail ile fallback tetikliyor ve fallback sonrası quality sonucunu kör kabul etmiyor. `selection_reason` log alanı eklendi. Gerçek MediaSpeech `430d0aaf...` örneğinde turbo'nun yarım transcript'i artık `tail_gap_uncovered` ile large-v3'e geçiyor.

2026-05-14 ASR v0.1 kapatma paketi: schema bağlantısı (TimelineEvent emit), kalite raporu standardizasyonu (VAD speech ratio dahil), smoke test (`tests/test_asr_v0_1_smoke.py`) ve gerçek demo output (`outputs/asr_v0_1_demo/`) tamamlandı. Klip: 001_h1 — TRT haber kameramanları, 101.7 sn. Sonuç: profile_used=fast (turbo geçti), 15 clean segment, 15 TimelineEvent, VAD speech_ratio=0.849, safety geçti. Test sayısı: 45 mevcut + 9 v0.1 smoke = 54 yeşil.

---

## 2. Sprint çerçevesi

| Madde | Karar |
|---|---|
| Sürüm | v0.1 |
| Hedef video | 1-2 dakikalık net Türkçe TRT haber kesiti (henüz seçilmedi) |
| Backend cephe | Henüz açılmadı |
| UI cephe | Şu sprintte dokunulmuyor |
| Çalışma venv'i | `asr` — birleşik ASR/STT runtime |
| Ana motor | faster-whisper `large-v3-turbo` default; `large-v3` selective fallback / üst-denetim |
| Ek motor (alignment) | WhisperX `alignment` venv'de; subprocess sleeve + word-level smoke yeşil |
| Diarization | pyannote — v1 kapsamında zorunlu bileşen, kalite eşikli uygulanır (Karar 15) |
| Denoise | DeepFilterNet `denoise` venv'de; subprocess sleeve + synthetic smoke yeşil |

---

## 3. Sprint öncesi açık kararlar (önce bunlar)

Sprint kodlamaya başlamadan **çözülmesi gereken** kararlar:

### 3.1 Hangi venv'de koşacak?

- `asr`: faster-whisper + silero-vad + pyannote + FastAPI/uvicorn/websockets var.
- `alignment`: WhisperX word-level alignment sleeve.
- `denoise`: DeepFilterNet denoise sleeve.
- `stt`: legacy; `legacy_stt_venv`, `deprecated_as_primary_runtime`, `do_not_delete_yet`.

Demo cephesi şu an aktif değil. Canlı transcript gerekirse bu artık `ASR > streaming_transcription` alt modu olarak `asr` venv içinde çalışır.

**Karar:** `asr` venv seçildi.

### 3.2 WhisperX kurulsun mu?

faster-whisper segment-level timestamp veriyor. Word-level alignment için WhisperX gerekiyor. Alternatif: stable-ts veya whisper-timestamped.

WhisperX `asr` venv'e kurulmaz; `alignment` venv'de kalır. ASR pipeline ona dosya/JSON tabanlı subprocess sleeve ile konuşur.

**Karar:** WhisperX v0.1 hazırlığında `alignment` venv'de smoke edildi. Word-level timestamp kapsamı v0.1 kalite raporunda `alignment_success` ve `word timestamp coverage` olarak yer alabilir.

### 3.3 Hedef test videosu

Hazırlık smoke'ları için `E:\MITAS\testklipler\erd_test_sound.wav` kullanıldı. v0.1 pipeline smoke için hâlâ 1-2 dakikalık net Türkçe TRT video kesiti seçilmeli.

**Karar:** Hazırlık ses smoke malzemesi var; sprint hedef videosu hâlâ geliştirici seçiminde.

### 3.4 ASR kalite raporu kapsamı

Master plan §2.1'de ASR kalite raporu zorunlu. İçeriği:

- word timestamp coverage
- alignment success
- VAD speech ratio
- diarization durumu
- hata bayrakları

Word timestamp coverage WhisperX yoksa "uygulanmadı" yazılır. Yine de raporlama disiplini sprintin parçasıdır.

**Karar:** Rapor yapısı `core/schemas/` altında zaten var (`module_run.py` ve `evidence.py`). Yeni schema gerekmez. Mevcut sözleşmeye yaslanılır.

---

## 4. Alt görevler

Sıralı çalışma adımları. Her adım sonunda **commit + bu dosyaya işaretleme**.

### 4.1 Sprint öncesi (kodlamadan önce)

- [x] **3.1 venv kararı** — `asr` venv seçildi; STT legacy olarak işaretlendi.
- [x] **3.2 WhisperX kararı** — `alignment` venv'de kalır; subprocess sleeve ile çağrılır.
- [x] **3.3 Hazırlık smoke ses malzemesi** — `E:\MITAS\testklipler\erd_test_sound.wav` kullanıldı. Sprint hedef videosu ayrıca seçilecek.
- [ ] **3.4 Sprint dosya yapısı** — proje ağacının neresinde ASR pipeline kodu duracak? (`core/pipelines/asr/` öneri)

### 4.1A Sprint öncesi runtime hazırlığı

- [x] **FFmpeg full-shared** — Gyan 8.1.1 full-shared PATH'te, shared DLL'ler erişilebilir.
- [x] **Torchcodec smoke** — `asr` decode yeşil; `alignment` torchcodec dormant kabul edildi.
- [x] **Denoise sleeve** — `venvs/denoise` kuruldu, `pip check` temiz, DeepFilterNet3 synthetic smoke yeşil.
- [x] **WhisperX alignment smoke** — word-level alignment JSON üretildi.
- [x] **large-v3 cache/offline smoke** — model lokal cache'e alındı, offline transcribe smoke ağ denemesi olmadan geçti.

### 4.2 Sprint kodlama adımları

- [x] **A. ffmpeg audio extract** — video → 16khz mono wav. Tek fonksiyon, tek test.
- [x] **B. Silero VAD entegrasyonu** — wav → konuşma segmentleri (yine tek fonksiyon).
- [x] **C. faster-whisper transcribe** — VAD segmentleri → segment-level transcript.
- [x] **D. Pyannote diarization** — wav + transcript → speaker_id. v1 kapsamında zorunlu bileşen; güven eşiği altında speaker_id = null yazılır (Karar 15).
- [x] **D2. Adaptive ASR fallback** — tail-gap safety tetikleyici + fallback result selector + `selection_reason` log alanı eklendi.
- [x] **E. Schema'ya bağlama** — `ModuleRun` zaten bağlıydı; `TimelineEvent` emit eklendi (`pipeline.py:_build_timeline_events`, `outputs/.../timeline_events.json`). Her clean_segment → 1 `asr_segment` event, `confidence = exp(avg_logprob)` ile normalize.
- [x] **F. Kalite raporu** — `summary.json` artık `model_name`, `fallback_triggered`, `fallback_reason`, `selection_reason`, `clean_segments`, `quality_drops`, `timeline_event_count`, `vad.speech_ratio`, `safety.diagnostics` (uncovered_tail dahil) alanlarını taşıyor.
- [x] **G. Smoke test** — `tests/test_asr_v0_1_smoke.py` golden-file testi (9 madde, schema + invariant doğrulaması). `core` venv'de pytest ile koşulur, ASR runtime gerekmez.
- [x] **H. Output JSON** — `outputs/asr_v0_1_demo/` altında 5 artifact (`archive.json`, `summary.json`, `module_run.json`, `transcript_review.md`, `timeline_events.json`). Klip: TRT haber kameramanları (001_h1, 101.7 sn). Üretim: `scripts/asr_v0_1_demo.py`.

### 4.3 Sprint sonu (kabul)

- [x] **I. Master plan §2.1 ile karşılaştırma** — `summary.quality_report` bloğu §2.1'in 5 zorunlu alanını taşıyor (2 doğrudan, 3 `not_applicable` plak). Detay: [docs/SPRINT_4_ASR_V0_1_DONE.md §3](../docs/SPRINT_4_ASR_V0_1_DONE.md).
- [x] **J. `06_KARARLAR_GUNLUGU.md`'ye sprint sonu özeti** — Karar 25 olarak yazıldı.
- [x] **K. `03_GUNCEL_DURUM.md`'i güncelle** — §0.2 yeni notu eklendi, §10 güncellendi.
- [x] **L. v0.1 demo raporu** — `docs/SPRINT_4_ASR_V0_1_DONE.md` yazıldı; v0.2'ye devreden 5 açık (WhisperX, diarization, profile dispatch, persistent worker, eşik kalibrasyonu) burada listelendi.

---

## 5. Bu sprintte dokunulmayacak şeyler

Sıkışırsak kapsamı genişletme cazibesi olur. **Bunlar v0.1 dışındadır:**

- ❌ FastAPI / WebSocket backend
- ❌ Streaming ASR (chunk push)
- ❌ Frontend
- ❌ Face detection
- ❌ OCR
- ❌ Visual tag
- ❌ Timeline merge
- ❌ Review UI
- ❌ UI panel düzeltmeleri

Bu liste **sözleşmedir**. Cazip görünse bile dokunmuyoruz; v0.1'i kirletmemek için.

---

## 6. Riskler ve dikkat noktaları

- **WhisperX kararı kararsız kalırsa sprint uzar.** Erken cevaplanmalı.
- **DeepFilterNet'in eski TRT arşivinde fayda/zarar dengesi belirsiz.** Sprint sırasında raw vs denoised karşılaştırma kısa bir alt görev olabilir; smoke aşamasında dürüst kalmak şart.
- **pyannote yavaş çalışıyor olabilir RTX 3090'da.** İlk koşumda timing ölçülür.
- **faster-whisper Türkçe karakter ı/i karmaşası.** Smoke test çıktısında dikkatlice kontrol edilir; gerekirse post-processing kuralı eklenir.

---

## 7. Bir sonraki adım (şu an, somut)

ASR v0.1 dikey dilimi kodca tamam: schema bağlantısı, kalite raporu, smoke test ve gerçek demo output yeşil. Kalan iki sprint-kapatma işi (I, L) ve bir kalibrasyon adımı:

1. **I. Master plan §2.1 ile karşılaştırma** — v0.1 dilimi master plan ASR kalite raporu sözleşmesindeki tüm alanları karşılıyor mu? Sapma varsa Karar Günlüğü'ne yaz.
2. **L. v0.1 demo raporu** — `docs/SPRINT_4_ASR_V0_1_DONE.md` arşivi yazılır; `outputs/asr_v0_1_demo/` çıktısı referans verilir.
3. **TRT transcript havuzu** elimize geçtiğinde:
   - MediaSpeech benchmark şeklini TRT WAV/TXT çiftlerinde tekrar koş.
   - `tail_gap_uncovered` eşiklerini (şu an 3.0 sn AND %25) TRT verisinde kalibre et.
   - `selection_reason`, `fallback_reason`, safety diagnostics ve WER/CER sonuçlarını birlikte değerlendir.
   - TRT desteklerse `large-v3-turbo default + large-v3 selective fallback` kararı kilitlenir.

**Hatırlatma:** Yeni kapsam açmadan önce karar `06_KARARLAR_GUNLUGU.md` içine yazılır.

---

## 7.1 UI Live STT Preview uygulaması (2026-05-14)

- [x] **DEC-UI-LIVE-STT-001** — Karar yazıldı: `06_KARARLAR_GUNLUGU.md` Karar 28.
- [x] **DONE-UI-LIVE-STT-001** — FastAPI WebSocket endpoint'i `/api/stt/preview/ws` eklendi.
- [x] **DONE-UI-LIVE-STT-002** — WebUI Preview, player sesini Web Audio API ile yakalayıp 16 kHz mono PCM16 chunk olarak gönderecek şekilde bağlandı.
- [x] **DONE-UI-LIVE-STT-003** — Preview popup/drawer iptal edildi; canlı transcript sağdaki normal `ASR` sekmesinde `Hazır / Dinliyor / Çözümlüyor / Durakladı / Bağlantı hatası` durumlarıyla gösteriliyor.
- [x] **DONE-UI-LIVE-STT-004** — Live stream aktifken batch `STT Başlat` devre dışı kalıyor.
- [x] **DONE-UI-LIVE-STT-005** — Üst bardaki büyük süre `imleç / toplam süre` formatına alındı.
- [x] **DONE-UI-LIVE-STT-006** — Live satırlar sağ ASR panelinde otomatik alta kayıyor; satırlar harf harf yazılma efekti ve canlı spinner ile gösteriliyor.
- [x] **DONE-UI-LIVE-STT-007** — Preview modunda zaman damgası gizlendi; canlı transcript ayrı satır kartları yerine gecikmeli akan tek metin blokuna çevrildi.
- [x] **DONE-UI-LIVE-STT-008** — Preview akışında kısa/tamamlanmamış son kuyruk tamponlandı; kelime başında bekleme yerine canlı imleç gösteriliyor.
- [x] **DONE-UI-LIVE-STT-009** — Preview overlap kaynaklı tekrarları kelime seviyesinde tekilleştiriyor; tekrar eden cümle başı yerine yalnız devam metni ekleniyor.
- [x] **DONE-UI-LIVE-STT-010** — Preview deneysel rolling-buffer moduna alındı: yaklaşık 1.25 sn decode aralığı, 7 sn context ve 2 sn geriden `publish_until` kelime commit davranışı eklendi.
- [x] **DONE-UI-LIVE-STT-011** — Live backend gerçek `word_timestamps=True` kelime publish moduna alındı; rolling context 10 sn, yazma gecikmesi 3 sn yapıldı ve `erd_test_video.mp4` 29-40 sn doğrudan live simülasyonunda kaybolan "Biliyorum ki..." başlangıcı geri geldi.
- [x] **DONE-UI-LIVE-STT-012** — Preview tempo adaptif yapıldı: yazma gecikmesi sonuç/backlog kalitesine göre 1.6-4.8 sn arasında oynuyor; daktilo efekti karakter kuyruğu uzunsa hızlanıyor.
- [x] **TEST-UI-LIVE-STT-001** — TypeScript kontrolü ve Vite build geçti; backend WebSocket testi core venv'de FastAPI olmadığı için skip-gated, asr venv'de manuel WebSocket smoke önceki koşuda geçti.

---

## 8. Aktif sprint bittiğinde

Bu dosya sıfırlanır ve **v0.2 — OCR/KJ + Müzik segment** sprinti için yeniden yazılır. Eski v0.1 içeriği `docs/SPRINT_4_ASR_V0_1_DONE.md` arşiv dosyasına taşınır.
