# MITAS — Ortam Değişkeni (Env Flag) Envanteri

> Üretildi: 2026-06-20 · Kaynak: tüm `.py` + `.ps1` üzerinde `os.environ` / `os.getenv` / `$env:` re-grep + `scripts/start_mitas.ps1` (canlı default'lar).
> Bu dosya **salt-dokümandır** — hiçbir kodu değiştirmez. Flag'ler değişince elle güncellenmelidir.

## Nasıl okunur

- **Default**: kodun env yokken kullandığı değer. `start_mitas`'ta ayrı bir default set ediliyorsa o **üretimde geçerli olandır** (kod-default'u değil).
- **Okunduğu yer**: `dosya:satır` — flag'in TÜKETİLDİĞİ asıl nokta (test/probe değil, prod yolu öncelikli).
- **start_mitas'ta?**: `scripts/start_mitas.ps1` flag'i açıkça set ediyor mu? **EVET** = production default'u burada görünür ve denetlenebilir. **HAYIR** = flag yalnız kod-default'una bağlı (gizli — production'ı etkiler ama start script'inde görünmez; bkz. Alt-Liste 1).
- **Durum**:
  - `AKTİF` = production'da varsayılan açık (start_mitas veya kod-default 1).
  - `opt-in` = varsayılan kapalı, elle `=1` ile açılır.
  - `deneysel` = yarım bağlı / yalnız POC / benchmark; production yolunda değil.
  - `ölü` = artık tüketilmiyor veya yalnız tek-kullanımlık script'te.
  - `config` = kalıcı yapılandırma (yol/anahtar/model), aç-kapa değil.

## Flag-hijyeni kuralı

**Her geçici (opt-in/deneysel) flag'in bir KALDIRMA-KOŞULU olmalıdır.** Bir flag eklerken "ne zaman silinecek / hangi karar default'a gömülecek" sorusunun cevabı `Notlar` sütununda yazılı olmalı. Süresiz `opt-in` = teknik borç. `AKTİF` olup uzun süredir 1 olan bayraklar bir sonraki temizlikte default'a gömülüp koddan çıkarılmalıdır (örn. QC2 / QC_BLOCK / CREDIT_DETECT olgunlaştığında flag-gate kaldırılabilir). Kill-switch'ler (NO_*) kalıcı olabilir ama belgelenmelidir.

> **Truthiness sözleşmesi (kodda iki kalıp var, karıştırma):**
> - **Açma-kapama kalıbı (opt-in):** `... in ("1","true","on","yes")` → SADECE bu değerler açar; başka her şey KAPALI.
> - **Kapatma kalıbı (default-AÇIK):** `... not in ("0","false","off","no")` → SADECE bu değerler kapatır; boş/yok = AÇIK.
> Bir flag'in hangi kalıpta okunduğu Default sütununda belirtildi.

---

## (A) QC / Karar

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_QC_BLOCK` | start: `1` (kod-default: kapalı, opt-in kalıbı) | `scripts/credit_qc_block.py:611`(tek_film), `scripts/mitas_pipeline.py:2043`, `scripts/tek_film_kunye.py:611` | Birleşik künye QC bloğu: çöp-ele + KB-floor doldur + Latin-dışı çevir + ONAYLI/KONTROL karar (OCR-otorite invariant). | EVET (`=1`) | AKTİF | Olgunlaşınca flag-gate kaldır, default'a göm. |
| `MITAS_QC2` | start: `1` (kod: opt-in) | `scripts/mitas_pipeline.py:1953`, `scripts/tek_film_kunye.py:471` | Künye temizleme/doğrulama: garble-kapısı + yönetmen KB-fill + web/köprü kimlik. | EVET (`=1`) | AKTİF | QC_BLOCK ile örtüşüyor; konsolide edilince biri kaldırılabilir. |
| `MITAS_QC2_WEB` | start: `1` (kod-default: `1`, kapatma kalıbı) | `scripts/tek_film_kunye.py:479` | QC2 içinde web/internet kimlik-teyit adımını aç/kapa. | EVET (`=1`) | AKTİF | Ağ olmayan ortamda `0` ile kapat. |
| `MITAS_QC_DIRECTOR_ANCHOR` | start: `1` (kod-default: `1`, kapatma kalıbı) | `scripts/credit_qc_block.py:490` | Kilitsiz filmde OCR-yönetmenden KB'de film-ara (kimlik-çapası). | EVET (`=1`) | AKTİF | PERF: indekssiz principals(98M) sorgusu; büyük batch yavaşlarsa `0`. |
| `MITAS_SES_DIL_KONTROL` | start: `0` (kod: opt-in) | `scripts/mitas_pipeline.py:1877` | Ses/dil/ASR sorununu künye-DIŞI sayıp KONTROL'e yollamama kapısı. | EVET (`=0`) | opt-in (KAPALI) | Çağatay 2026-06-20 kapattı; ses-dil künyeyi etkilemez kararı default olunca kaldır. |
| `MITAS_FUZZY_DBQC` | `1` (kod-default, kapatma kalıbı) | `scripts/tek_film_kunye.py:383` | Künye cast-düzeltme cascade'i (gömülü-pencere matcher + fuzzy-gate + title+year fallback). | HAYIR | AKTİF (gizli) | Default 1; start_mitas'ta görünmüyor → Alt-Liste 1. |
| `MITAS_KB_CAST_ADD` | start: `1` (kod-default: `1`, kapatma kalıbı) | `scripts/tek_film_kunye.py:29` | Kimlik kesinken eksik kadroyu KB'den EKLE (OCR önde, asla ezme). | EVET (`=1`) | AKTİF | — |
| `MITAS_GLOBAL_PERSON_GATE` | `0` (kod-default, kapatma kalıbı ama tabanı 0) | `scripts/tek_film_kunye.py:32` | Yönetmen-dışı rol genel kişi-kapısı filtresi. | HAYIR | opt-in (KAPALI) | Gizli default; doğrulanınca aç veya kaldır → Alt-Liste 1. |
| `MITAS_CREDIT_VALIDATE` | yok (opt-in) | `scripts/mitas_pipeline.py:1667` | credit_validate ek-doğrulama adımı (ADDITIVE: PDF akışını değiştirmez). | HAYIR | opt-in | Forensik: ADDITIVE olduğu için doğru-doğrulanan veri final'e geçmiyor (propagation kök-neden). Davranış düzeltilince yeniden değerlendir. |
| `MITAS_USE_CROSSCHECK` | yok (opt-in) | `scripts/credit_qc.py:334`, `scripts/credit_export.py:78` | Wikidata/IMDb cross-check'i künye QC/export'ta aç. | HAYIR | opt-in | DuckDB yolları (E grubu) gerektirir. |

## (B) OCR / Kredi-okuma (jenerik)

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_CREDIT_DETECT` | start: `1` (kod-default `mitas_pipeline`: kapalı/opt-in) | `scripts/mitas_pipeline.py:1291` | Eski OpusCreditDetector ile jenerik giriş/çıkış sınırını dinamik bul (sabit 180/240s pencereyi genişletir). | EVET (`=1`) | AKTİF | NOT: `mitas_pipeline`'da yeni `MITAS_JENERIK_DETECT` default-açık iken bu eski-yol opt-in; start_mitas eski-yolu `=1` zorluyor → ikisinin etkileşimi gözden geçirilmeli. |
| `MITAS_JENERIK_DETECT` | `1` (kod-default, kapatma kalıbı) | `scripts/mitas_pipeline.py:1290` | YENİ bağımsız jenerik-başlangıç dedektörü (CLIP+sezgisel füzyon). | HAYIR | AKTİF (gizli) | Default 1; start_mitas'ta görünmüyor → Alt-Liste 1. |
| `MITAS_JENERIK_OCR_REFINE` | `1` (kod-default, `!= "0"`) | `scripts/_jenerik_detect.py:85` | Jenerik dedektöründe OCR-geriye inceltme adımı. | HAYIR | AKTİF (gizli) | — |
| `MITAS_CREDIT_DETECT_MINCONF` | `0.60` | `scripts/mitas_pipeline.py:1297` | credit_detect güven eşiği (altı → sabit-varsayılan pencere). | HAYIR | config | — |
| `MITAS_CREDIT_DETECT_LOWCONF_MINCONF` | `0.45` | `scripts/mitas_pipeline.py:1298` | Düşük-güven yolu için ikinci eşik. | HAYIR | config | — |
| `MITAS_CREDIT_DETECT_LOWCONF_MIN_DUR` | `180` (s) | `scripts/mitas_pipeline.py:1299` | Düşük-güven yolunda min pencere süresi. | HAYIR | config | — |
| `MITAS_OCR_MIN_LINES` | `30` | `scripts/mitas_pipeline.py:1488` | OCR çıktısı bu satırın altındaysa eskalasyon tetiği. | HAYIR | config | — |
| `MITAS_CREDIT_TEXT_MODEL` | `qwen3.6:35b-a3b` | `scripts/credit_text_read.py:29,945` | Künye-metin ayıklayıcı (kredi-okuma) ollama modeli. | HAYIR | config | Benchmark kazananı; 23GB VRAM. |
| `MITAS_CREDIT_MODELS` | `gemma4:26b,qwen2.5vl:7b` | `scripts/credit_video_read.py:52` | Video-kredi (VL) modelleri (virgül-ayrık). | HAYIR | config | — |
| `MITAS_CREDIT_CAST_BLOCK_FAST` | `0` (opt-in) | `scripts/credit_text_read.py:969` | Cast-bloğu hızlı-mod (ayrıntıyı atla). | HAYIR | opt-in | Re-render batch'lerinde `1` kullanıldı. |
| `MITAS_CREDIT_PARSE_V2` | yok (opt-in) | `OCR-worktree/pdf-mitas/credit_parse.py:260` | Künye parse v2 yolu. | HAYIR | deneysel | Olgunlaşınca v1 kaldır. |
| `MITAS_VL_CAST` | `0` (opt-in) | `scripts/_pipe_credit_vl.py:157` | VL-fallback'te cast da doldur (default sadece yönetmen). | HAYIR | opt-in | QC1-RED'de zaten açılıyor (fill_cast). |
| `MITAS_VL_TEMP` | `0` | `scripts/credit_video_read.py:153` | VL sıcaklık (yönetmen deterministik için greedy). | HAYIR | config | — |
| `MITAS_VL_TOPP` | `1` | `scripts/credit_video_read.py:154` | VL top-p. | HAYIR | config | — |
| `MITAS_OCR_GLM_CONSENSUS` | start: `0` (kod-default: `1`, kapatma kalıbı) | `scripts/_pipe_ocr.py:565` | GLM ile OCR consensus okuması. | EVET (`=0`) | opt-in (KAPALI) | Doymuş ollama'da 15dk darboğaz → production'da kapalı. start_mitas kod-default'unu (1) EZER. |
| `MITAS_OCR_PADDLE` | `0` (opt-in) | `scripts/_pipe_ocr.py:778` | PaddleOCR yan-kanalını aç (`paddle_kunye.txt`). | HAYIR | deneysel | Benchmark'ta GPU'da güçlü; production-kapalı. |
| `MITAS_MASTER_PNG` | `` (opt-in) | `scripts/_pipe_ocr.py:508` | Jenerik→tek master-PNG derleme (görsel yarısı). | HAYIR | deneysel | Tesisat hazır, uçtan-uca ölçülmedi; rol-etiket gürültüsü çözülünce aç. |
| `MITAS_TEXTMASK` | (probe set eder) | `outputs/credit_structure_master_scroll_probe.py:987` | compose_hybrid'de koşullu text-mask. | HAYIR | deneysel | Yalnız probe; prod'da `_pipe_ocr` içinden gelir. |
| `MITAS_FRAMEGATE` | (probe set eder) | `outputs/credit_structure_master_scroll_probe.py:989` | compose_hybrid frame-gate. | HAYIR | deneysel | Yalnız probe. |
| `OCR_SCROLL_FALLBACK` | `auto` | `core/pipelines/ocr/unified_credit_pipeline.py:452` | Scroll-fallback modu (auto/on/off). | HAYIR | config | — |
| `OCR_TEXT_MASK_MODE` | `current` | `core/pipelines/ocr/text_layer_row_reconstruct.py:888` | Text-mask modu (current/...). | HAYIR | config | — |
| `OCR_CARD_GROUPING` | `gap` | `core/pipelines/ocr/box_tracker.py:552` | Kart-gruplama stratejisi. | HAYIR | config | — |
| `OCR_HAKIM_SHADOW` | `0` (opt-in) | `core/pipelines/ocr/text_layer_row_reconstruct.py:426` | Hakim gözlemci gölge-modu. | HAYIR | ölü/deneysel | Pilot KAPANDI (2026-05-29), kalıcı pasif. Silinebilir. |
| `USE_LEGACY_CREDIT_PIPELINE` | yok (`== "1"`) | `core/pipelines/ocr/credit_experiment.py:977` | Eski kredi pipeline'ına geri dön. | HAYIR | opt-in | Geçiş tamamlanınca kaldır. |
| `USE_BOX_TRACK_PIPELINE` | yok (`== "0"` ile kapanır) | `core/pipelines/ocr/credit_experiment.py:980` | Box-track pipeline'ını kapat (default açık). | HAYIR | config | — |

## (C) ASR / Dil

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_ASR_FOREIGN_BEAM` | `1` | `scripts/_pipe_asr.py:166` | Yabancı-film large-v3 ASR beam genişliği. | HAYIR | config | Eski 5→1 düzeltmesi; default'a gömüldü. |
| `MITAS_LANGUAGE_INTELLIGENCE` | `off` | `core/pipelines/asr/language_intelligence.py:221` | Dil-zekası modu (off/...). | HAYIR | opt-in (KAPALI) | — |
| `MITAS_LANGUAGE_INTELLIGENCE_DEVICE` | `cuda` | `core/pipelines/asr/language_intelligence.py:227` | Dil-zekası cihazı. | HAYIR | config | — |
| `PYANNOTE_TOKEN` | yok | `core/pipelines/asr/diarize.py:26,74` | Diarization (pyannote) HF token'ı. | HAYIR | config (secret) | Yoksa diarize atlar. |
| `MITAS_ASR_TIMEOUT` | `7200` (s) | `scripts/mitas_pipeline.py:770` | ASR alt-adım subprocess timeout. | HAYIR | config | — |

## (D) Render / PDF / Özet

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_FAST_NO_POSTER` | yok (varlık-kontrolü) | `outputs/kunye_fix/fix_kunye.py:221` (set: `apply_one.py:99`, `render_in_place.py:28`) | Ağır/asılabilen afiş fetch'ini atla (re-render hızlandırma). | HAYIR | araç-içi | Yalnız kunye_fix araçları set eder. |
| `MITAS_OZET_OLLAMA_MODEL` | `gemma4:26b` | `scripts/mitas_pipeline.py:1028` | Özet (ollama fallback) modeli. | HAYIR | config | — |
| `MITAS_OZET_RETRIES` | `3` | `scripts/mitas_pipeline.py:1085` | Özet rate-limit/503 tekrar tur sayısı. | HAYIR | config | — |
| `MITAS_OZET_RETRY_BACKOFF` | `6` (s) | `scripts/mitas_pipeline.py:1100` | Özet tekrarları arası backoff. | HAYIR | config | — |
| `MITAS_GEMINI_MODEL` | `gemma-4-31b-it` (pipeline kod-default `gemini-2.5-flash`) | `scripts/_gemini.py:83`, `scripts/mitas_pipeline.py:947` | Özet gemini/gemma modeli. | HAYIR | config | İki yerde FARKLI kod-default (`_gemini.py`=gemma-4-31b-it, `mitas_pipeline.py:947`=gemini-2.5-flash) — dikkat. |
| `MITAS_DEEPSEEK_MODEL` | `deepseek-chat` | `scripts/mitas_pipeline.py:1016` | Özet DeepSeek fallback modeli. | HAYIR | config | — |
| `MITAS_PDF_TIMEOUT` | `1800` (s) | `scripts/mitas_pipeline.py:771` | PDF render alt-adım timeout. | HAYIR | config | — |
| `MITAS_TESSERACT_LANG` | `tur+eng` (simple.py); `default_lang` (credit_experiment) | `core/pipelines/ocr/simple.py:225`, `credit_experiment.py:567` | Tesseract dil paketi. | HAYIR | config | — |

## (E) KB / Veri-yolu / Timeout-altyapı

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_KB_DUCKDB` | `Y:\DIGER\Mitas_Files\MitaData\mitas.duckdb` | `scripts/credit_validate.py:30` | Künye KB (kadro/yönetmen) DuckDB yolu. | HAYIR | config | — |
| `MITAS_WIKIDATA_DUCKDB` | `X:\DIGER\Mitas_Files\MitaData\mitas.duckdb` | `scripts/credit_crosscheck.py:20` | Wikidata DuckDB yolu. | HAYIR | config | — |
| `MITAS_IMDB_DUCKDB` | `Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb` | `scripts/credit_crosscheck.py:21`, `credit_video_read.py:53`, `kok_neden_lock_olcum.py:21` | IMDb DuckDB yolu. | HAYIR | config | — |
| `MITAS_PDFMITAS_DIR` | `E:\MITAS\OCR-worktree\pdf-mitas` | `scripts/credit_qc_block.py:68` | pdf-mitas modül dizini. | HAYIR | config | — |
| `MITAS_PROJECT_ROOT` | `` (boş→otomatik) | `core/pipelines/asr/normalize.py:19` | Proje kök yolu override. | HAYIR | config | — |
| `MITAS_OCR_PYTHON` | `` (boş→otomatik) | `core/api/tedial/job_runner.py:307` | OCR alt-süreç için python yolu. | HAYIR | config | — |
| `MITAS_FFMPEG` | `` (boş→PATH) | `core/pipelines/ocr/simple.py:237`, `credit_experiment.py:3597` | ffmpeg binary yolu. | HAYIR | config | — |
| `MITAS_FFMPEG_DLL_DIR` | `DEFAULT_FFMPEG_BIN` | `scripts/alignment_subprocess.py:19` | ffmpeg DLL dizini. | HAYIR | config | — |
| `FFMPEG_EXECUTABLE` | yok | `core/pipelines/ocr/dynamic_window.py:330` | ffmpeg exe override (OCR-içi). | HAYIR | config | — |
| `FFPROBE_EXECUTABLE` | yok | `core/pipelines/ocr/_video_meta.py:18` | ffprobe exe override. | HAYIR | config | — |
| `MITAS_OCR_TIMEOUT` | `3600` (s) | `scripts/mitas_pipeline.py:769` | OCR alt-adım subprocess timeout. | HAYIR | config | — |
| `MITAS_V4_TIMEOUT` | `900` (s) | `scripts/mitas_pipeline.py:772` | v4-final alt-adım timeout. | HAYIR | config | — |
| `MITAS_VIDEO_CREDIT_TIMEOUT` | `1800` (s) | `scripts/mitas_pipeline.py:773` | Video-kredi alt-adım timeout. | HAYIR | config | — |
| `MITAS_VL_FALLBACK_TIMEOUT` | `900` (s) | `scripts/mitas_pipeline.py:774` | VL-fallback alt-adım timeout. | HAYIR | config | — |

## (F) LLM / Model + API-key

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | yok | `scripts/mitas_pipeline.py:899`, `asr_server.py:2995,3126` | Sonnet özet için Anthropic anahtarı. | EVET (User env yüklenir, satır 17) | config (secret) | start_mitas `ANTHROPIC_*` User env'lerini yükler. |
| `MITAS_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | `mitas_pipeline.py:902`, `asr_server.py:3129`, `_summary_smoke.py:8` | Özet Anthropic modeli. | dolaylı (User env) | config | — |
| `OPENAI_API_KEY` | yok | `asr_server.py:3174` | OpenAI özet anahtarı (yedek). | EVET (User env, satır 17) | config (secret) | — |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | `asr_server.py:3179` | OpenAI uyumlu endpoint. | dolaylı | config | — |
| `MITAS_SUMMARY_MODEL` / `OPENAI_SUMMARY_MODEL` | yok | `asr_server.py:3175` | OpenAI-uyumlu özet modeli. | dolaylı | config | İkisi de boşsa yerel extractive özete düşer. |
| `MITAS_TMDB` / `TMDB_API_KEY` | yok | `mitas_pipeline.py:1142`, `poster_fetch.py:189`, `credit_identity.py:75`, `asr_server.py:1086` | TMDB anahtarı (afiş + kimlik). | dolaylı (User env) | config (secret) | `MITAS_TMDB` öncelikli. |
| `MITAS_OMDB` / `OMDB_API_KEY` | yok | `OCR-worktree/pdf-mitas/poster_fetch.py:236` | OMDb anahtarı (afiş yedek). | dolaylı | config (secret) | — |
| `MITAS_DEEPSEEK` / `DEEPSEEK_API_KEY` | yok | `scripts/_deepseek.py:78`, `name_normalize.py:325` | DeepSeek anahtarı (özet/isim fallback). | dolaylı | config (secret) | — |
| `MITAS_DEEPSEEK_BASE` | `https://api.deepseek.com` | `scripts/_deepseek.py:82` | DeepSeek endpoint. | HAYIR | config | — |
| `MITAS_DEEPSEEK_TIMEOUT` | `120` (s) | `scripts/_deepseek.py:85` | DeepSeek timeout. | HAYIR | config | — |
| `MITAS_GEMINI` / `GEMINI_API_KEY` / `GOOGLE_API_KEY` | yok | `scripts/_gemini.py:62-64` | Gemini/gemma anahtarı (özet). | dolaylı | config (secret) | Üç isim sırayla denenir. |
| `MITAS_GEMINI_BASE` | `https://generativelanguage.googleapis.com` | `scripts/_gemini.py:84` | Gemini endpoint. | HAYIR | config | — |
| `MITAS_GEMINI_TIMEOUT` | `120` (s) | `scripts/_gemini.py:86` | Gemini timeout. | HAYIR | config | — |
| `MITAS_OLLAMA` | `http://127.0.0.1:11434` | `credit_text_read.py:28`, `credit_video_read.py:50`, `mitas_pipeline.py:1029` | Ollama host. | HAYIR | config | — |
| `MITAS_OLLAMA_TIMEOUT` | `300` (s) (credit_text_read: dinamik default) | `scripts/_ollama.py:70`, `credit_text_read.py:291` | Ollama istek timeout. | HAYIR | config | — |

## (G) Tedial / Servis

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_TEDIAL_PASSWORD` | yok | (config.py `_env` üzerinden; bkz. memory) | Tedial auto-login şifresi. | EVET (User env, satır 17) | config (secret) | Tedial şifresi değişince güncelle. |
| `MITAS_TEDIAL_JOB_STORE` | `` (boş→default) | `core/api/tedial/import_queue.py:62` | Tedial iş-kuyruğu deposu yolu. | HAYIR | config | — |
| `MITAS_TEDIAL_SESSION_DIR` | `` (boş→default) | `core/api/tedial/session.py:342` | Tedial oturum dizini. | HAYIR | config | — |
| `MITAS_TEDIAL_DEV_COOKIE_ATTACH` | `` (opt-in) | `core/api/tedial/router.py:1047` | Dev: cookie elle iliştir. | HAYIR | deneysel | Yalnız geliştirme. |
| `MITAS_ASR_TRANSCRIBE_URL` | `http://127.0.0.1:8787/api/asr/transcribe` | `core/api/tedial/router.py:1146` | Tedial→ASR transcribe endpoint'i. | HAYIR | config | — |
| `MITAS_PIPELINE_RUN_URL` | `http://127.0.0.1:8787/api/pipeline/run` | `core/api/tedial/router.py:1192` | Tedial→pipeline run endpoint'i. | HAYIR | config | — |
| `MITAS_ACCESS_SECRET` | `` | `core/api/access.py:174` | Erişim-katmanı paylaşılan sır. | HAYIR | config (secret) | — |
| `MITAS_ACCESS_SECRET_FILE` | `DEFAULT_SECRET_PATH` | `core/api/access.py:178` | Erişim sırrı dosya yolu. | HAYIR | config | — |
| `MITAS_ACCESS_COOKIE_SECURE` | `` (opt-in) | `core/api/access.py:198` | Secure-cookie bayrağı. | HAYIR | config | HTTPS arkasında `1`. |

## (H) Altyapı / OCR-motor / Kill-switch'ler

| Flag | Default | Okunduğu yer | Amaç | start_mitas'ta? | Durum | Notlar / ne zaman kaldırılır |
|---|---|---|---|---|---|---|
| `MITAS_NO_VIDEO_CREDITS` | yok (opt-in) | `scripts/mitas_pipeline.py:1577` | KILL: video-kredi (VL okuma) adımını atla. | HAYIR | kill-switch | Kalıcı; batch hızlandırma. |
| `MITAS_NO_VL_FALLBACK` | yok (opt-in) | `scripts/mitas_pipeline.py:1604` | KILL: VL-fallback adımını atla. | HAYIR | kill-switch | Re-render batch'te `1`. |
| `MITAS_NO_V4_FINAL` | yok (opt-in) | `scripts/mitas_pipeline.py:1787` | KILL: v4-final künye adımını atla. | HAYIR | kill-switch | Re-render batch'te `1`. |
| `MITAS_PADDLEOCR_DEVICE` | `` (boş→otomatik) | `core/pipelines/ocr/credit_experiment.py:601` | PaddleOCR cihazı (cpu/gpu). | HAYIR | config | — |
| `MITAS_PADDLEOCR_USE_REAL_MODELSCOPE` | `` (opt-in) | `core/pipelines/ocr/credit_experiment.py:623` | Gerçek ModelScope modellerini kullan. | HAYIR | deneysel | — |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR` | yok | `scripts/jenerik_tek_png.py:96` | Paddle detection model dizini. | HAYIR | config | — |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR` | yok | `scripts/jenerik_tek_png.py:97` | Paddle recognition model dizini. | HAYIR | config | — |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME` | `PP-OCRv5_mobile_det` (jenerik); `PADDLE_DETECTION_MODEL_NAME` (credit_exp) | `jenerik_tek_png.py:98`, `credit_experiment.py:460` | Paddle detection model adı. | HAYIR | config | — |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME` | `PP-OCRv5_mobile_rec` (jenerik); sabit (credit_exp) | `jenerik_tek_png.py:99`, `credit_experiment.py:461` | Paddle recognition model adı. | HAYIR | config | — |
| `MITAS_OCR_ALLOW_MODEL_DOWNLOAD` | `` (opt-in) | `core/pipelines/ocr/credit_experiment.py:464` (set: `profile_kj_dataset.py:268`, `credit_experiment.py:169`) | OCR model indirmesine izin ver. | HAYIR | config | — |
| `MITAS_TESSERACT_CMD` | `` (boş→PATH) | `core/pipelines/ocr/credit_experiment.py:3612` | Tesseract binary yolu. | HAYIR | config | — |
| `MITAS_ONEOCR_CONFIG_DIR` | `` (boş→default) | `core/pipelines/ocr/credit_experiment.py:3630` | OneOCR config dizini. | HAYIR | config | — |
| `ONEOCR_CONFIG_DIR` | `F:\REPO_GitHub\oneocr` | `mutfak/.../full_pipeline_test.py:45` | OneOCR config (eski mutfak). | HAYIR | ölü | Eski mutfak; OCR-worktree'ye taşındı. |

---

## ALT-LİSTE 1 — Kodda VAR ama start_mitas'ta YOK (gizli default'lar)

Bu flag'ler production davranışını **etkiler** ama `start_mitas.ps1`'te görünmez; yalnız kod-default'larına bağlıdır. Default `1`/açık olanlar özellikle önemli (sessiz-aktif):

| Flag | Kod-default | Etki | Neden riskli |
|---|---|---|---|
| `MITAS_JENERIK_DETECT` | `1` (AÇIK) | Yeni jenerik dedektörü production'da aktif | start_mitas'ta görünmüyor; eski `MITAS_CREDIT_DETECT=1` ile birlikte iki dedektör yolu çakışabilir. |
| `MITAS_JENERIK_OCR_REFINE` | `1` (AÇIK) | Jenerik OCR-inceltme aktif | Görünmez. |
| `MITAS_FUZZY_DBQC` | `1` (AÇIK) | Cast-düzeltme cascade aktif | Görünmez; QC kalitesini doğrudan etkiler. |
| `MITAS_QC2_WEB` | `1` (AÇIK) | start_mitas set ediyor — aslında görünür (satır 23) | (Sınır vaka: hem start hem kod-default 1.) |
| `MITAS_GLOBAL_PERSON_GATE` | `0` (KAPALI) | Kişi-kapısı varsayılan kapalı | Görünmez; açılırsa cast filtrelenir. |
| `MITAS_VL_CAST` | `0` (KAPALI) | VL cast-doldurma kapalı | Görünmez. |
| `MITAS_CREDIT_TEXT_MODEL` | `qwen3.6:35b-a3b` | Ayıklayıcı model seçimi | Görünmez; VRAM/hız etkisi büyük, start'ta override edilmiyor. |
| `MITAS_CREDIT_MODELS` | `gemma4:26b,qwen2.5vl:7b` | VL modelleri | Görünmez. |
| `MITAS_ASR_FOREIGN_BEAM` | `1` | ASR beam | Görünmez; eski 5-regresyonu kod-default'ta düzeltildi. |
| `MITAS_OZET_OLLAMA_MODEL` | `gemma4:26b` | Özet fallback modeli | Görünmez. |
| `MITAS_GEMINI_MODEL` | `_gemini.py`=`gemma-4-31b-it` / `mitas_pipeline.py:947`=`gemini-2.5-flash` | Özet modeli | **İki yerde farklı kod-default** — tutarsızlık riski. |
| `MITAS_OCR_MIN_LINES`, `MITAS_*_TIMEOUT` (OCR/PDF/V4/VC/VL/ASR/OLLAMA) | sabitler | Eskalasyon/timeout eşikleri | Görünmez; uzun filmlerde davranış belirler. |
| `MITAS_CREDIT_DETECT_MINCONF / _LOWCONF_MINCONF / _LOWCONF_MIN_DUR` | `0.60 / 0.45 / 180` | credit_detect güven/pencere eşikleri | Görünmez. |
| Tüm veri-yolu/API-key flag'leri (E ve F grupları) | sabit yollar / boş | DuckDB, ffmpeg, model dizinleri, anahtarlar | Yollar sabit-kodlu default; ortam değişirse sessiz kırılır (API-key'ler User env'den gelir). |

> **Not:** `MITAS_OCR_GLM_CONSENSUS` ve `MITAS_SES_DIL_KONTROL` ve `MITAS_CREDIT_DETECT`/`MITAS_QC2`/`MITAS_QC_BLOCK`/`MITAS_QC_DIRECTOR_ANCHOR`/`MITAS_KB_CAST_ADD` start_mitas'ta AÇIKÇA set edildiği için bu listede DEĞİL — onlar görünür ve denetlenebilir. Özellikle `MITAS_OCR_GLM_CONSENSUS`'ta start_mitas kod-default'unu (`1`) `0`'a EZER — bu doğru ve istenen davranış.

## ALT-LİSTE 2 — Ölü-flag / alias şüphesi

| Flag | Şüphe türü | Kanıt | Öneri |
|---|---|---|---|
| `OCR_HAKIM_SHADOW` | ölü (pilot kapandı) | `text_layer_row_reconstruct.py:426`; pilot 2026-05-29 KAPANDI, kalıcı pasif (memory) | Koddan çıkar veya bilinçli-pasif olarak işaretle. |
| `ONEOCR_CONFIG_DIR` (Latin-ön ek'siz) | ölü/eski-mutfak | yalnız `mutfak/.../full_pipeline_test.py:45` (eski mutfak); prod `MITAS_ONEOCR_CONFIG_DIR` kullanır | Eski mutfak silinince gider. |
| `MITAS_TMDB_TEST` | yalnız-test alias | yalnız `outputs/kunye_fix/_test_sametitle.py:4` | Prod yolunda değil; test-only. |
| `MITAS_FLOW_PARALLEL` | start_mitas'ta YOK + prod-kodunda YOK | yalnız `outputs/test_parallel_dispatcher.py:48` (`setdefault`) | 2-paralel iş GERİ ALINDI (memory: revert `5e8bd9b20d`). Flag prod'da tüketilmiyor → ölü; yeniden denenmezse sil. |
| `MITAS_TEXTMASK` / `MITAS_FRAMEGATE` | yalnız-probe | yalnız `outputs/credit_structure_master_scroll_probe.py` set eder | Prod'da `_pipe_ocr` içinden gelir; bu probe alias. |
| `MITAS_CREDIT_DETECT` vs `MITAS_JENERIK_DETECT` | çift-yol / olası alias | `mitas_pipeline.py:1290-1291` ikisini de okur; start_mitas eski-yolu `=1` zorlar, yeni-yol kod-default `=1` | İkisinin etkileşimi netleştirilmeli; biri diğerinin yerini alacaksa eski-yol (`CREDIT_DETECT`) kaldırılmalı. |
| `MITAS_CREDIT_VALIDATE` | etkisiz-aktif şüphesi | `mitas_pipeline.py:1667` ADDITIVE; "PDF AKIŞINI DEĞİŞTİRMEZ" → açılsa bile final'i değiştirmiyor (forensik propagation kök-neden) | Ölü değil ama amaca hizmet etmiyor; davranışı düzeltilmeli ya da kaldırılmalı. |
| `MITAS_PADDLEOCR_USE_REAL_MODELSCOPE` | deneysel/atıl | `credit_experiment.py:623`; production-kapalı | Paddle yan-kanalı kalıcı kapanırsa sil. |
| `OPENAI_SUMMARY_MODEL` | `MITAS_SUMMARY_MODEL` alias | `asr_server.py:3175` (`or` yedek) | Bilinçli ikinci-isim; kalabilir. |

---

### Toplam

- **Benzersiz flag (MITAS_* + ortak alias'lar + OCR_*/USE_*/FF*_EXECUTABLE/PYANNOTE/API-key'ler): ~95.**
  - Saf `MITAS_*`: **~70**.
  - Ortak/üçüncü-taraf (ANTHROPIC/OPENAI/TMDB/OMDB/DEEPSEEK/GEMINI/GOOGLE/PYANNOTE alias'ları): **~14**.
  - `OCR_*` / `USE_*_PIPELINE` / `FFMPEG_EXECUTABLE` / `FFPROBE_EXECUTABLE` / `ONEOCR_CONFIG_DIR`: **~9**.
- **start_mitas.ps1'te açıkça set edilen:** 9 (`MITAS_QC2`, `MITAS_QC2_WEB`, `MITAS_QC_BLOCK`, `MITAS_SES_DIL_KONTROL`, `MITAS_QC_DIRECTOR_ANCHOR`, `MITAS_CREDIT_DETECT`, `MITAS_KB_CAST_ADD`, `MITAS_OCR_GLM_CONSENSUS`) + tüm `MITAS_/ANTHROPIC_/OPENAI_` User-env'leri toplu yüklenir.
- **HARİÇ TUTULANLAR (flag değil):** `HF_HOME`, `HF_HUB_OFFLINE`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `USE_TF`, `USE_FLAX`, `TQDM_DISABLE`, `PYTHONIOENCODING`, `CUDA_VISIBLE_DEVICES`, `FLAGS_json_format_model`, `FLAGS_enable_pir_api`, `PATH`, `COOKIE`, `USERPROFILE` — bunlar üçüncü-taraf kütüphane/sistem değişkenleridir, MITAS karar-flag'i değildir.
