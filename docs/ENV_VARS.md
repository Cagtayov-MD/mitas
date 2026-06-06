# MITAS Ortam Değişkenleri (ENV_VARS)

Aşağıdaki tablo, kaynak taramasıyla (`MITAS_`, `ANTHROPIC_`, `OPENAI_`, `USE_TF`) bulunan tüm ortam değişkenlerini listeler.  
**Zorunlu** = ayarlanmazsa ilgili özellik çalışmaz/hata verir. **Opsiyonel** = default davranış var.

---

## Antropik / LLM API

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic Claude API anahtarı (özet + künye üretimi) | — (yok → özet atlanır) | `scripts/mitas_pipeline.py`, `core/api/asr_server.py` |
| `MITAS_ANTHROPIC_MODEL` | Claude model ID (özet için) | `claude-sonnet-4-6` | `scripts/mitas_pipeline.py`, `core/api/asr_server.py` |
| `MITAS_SUMMARY_MODEL` | OpenAI-uyumlu endpoint'te kullanılacak model | — (yok → Anthropic yoluna düşer) | `core/api/asr_server.py` |
| `OPENAI_API_KEY` | OpenAI veya uyumlu API anahtarı (opsiyonel özet yolu) | — | `core/api/asr_server.py` |
| `OPENAI_SUMMARY_MODEL` | `MITAS_SUMMARY_MODEL` yoksa fallback model adı | — | `core/api/asr_server.py` |
| `OPENAI_BASE_URL` | OpenAI uyumlu base URL | `https://api.openai.com/v1` | `core/api/asr_server.py` |
| `MITAS_DEEPSEEK` | DeepSeek API anahtarı (OpenAI-uyumlu chat/completions) | — (yok → DeepSeek atlanır) | `scripts/_deepseek.py` |
| `DEEPSEEK_API_KEY` | `MITAS_DEEPSEEK` yoksa fallback DeepSeek anahtarı | — | `scripts/_deepseek.py` |
| `MITAS_DEEPSEEK_BASE` | DeepSeek base URL | `https://api.deepseek.com` | `scripts/_deepseek.py` |
| `MITAS_DEEPSEEK_TIMEOUT` | DeepSeek HTTP timeout (saniye) | `120` | `scripts/_deepseek.py` |

---

## Metadata / Veri Kaynakları

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `MITAS_TMDB` | TMDB API anahtarı (afiş + internet özeti) | — (yok → TMDB çağrısı atlanır) | `scripts/mitas_pipeline.py`, `scripts/refetch_afis.py` |
| `MITAS_OMDB` | OMDb API anahtarı (IMDb afiş yedek kaynağı) | — (yok → OMDb çağrısı atlanır) | `OCR-worktree/pdf-mitas/poster_fetch.py` |
| `OMDB_API_KEY` | `MITAS_OMDB` yoksa fallback OMDb anahtarı | — | `OCR-worktree/pdf-mitas/poster_fetch.py` |
| `MITAS_WIKIDATA_DUCKDB` | Wikidata DuckDB veritabanı yolu | `X:\DIGER\Mitas_Files\MitaData\mitas.duckdb` | `scripts/credit_crosscheck.py` |
| `MITAS_IMDB_DUCKDB` | IMDb DuckDB veritabanı yolu | `Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb` | `scripts/credit_crosscheck.py`, `scripts/credit_video_read.py` |
| `MITAS_USE_CROSSCHECK` | Wikidata/IMDb çapraz kontrolünü aktifleştirir (`1/true/yes/on`) | kapalı | `scripts/credit_export.py`, `scripts/credit_qc.py` |

---

## Pipeline / ASR

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `MITAS_NO_VIDEO_CREDITS` | Video-künye okuma adımını devre dışı bırakır (`1/true/yes/on`) | kapalı (açık) | `scripts/mitas_pipeline.py` |
| `MITAS_LANGUAGE_INTELLIGENCE` | Dil tespiti modu (`off/mms-lid/…`) | `off` | `core/pipelines/asr/language_intelligence.py` |
| `MITAS_LANGUAGE_INTELLIGENCE_DEVICE` | MMS-LID çalıştırma cihazı | `cuda` | `core/pipelines/asr/language_intelligence.py` |
| `MITAS_PROJECT_ROOT` | Proje kök dizini (normalize için) | Otomatik çıkarım | `core/pipelines/asr/normalize.py` |
| `MITAS_FFMPEG` | ffmpeg binary yolu (OCR/ASR pipeline) | PATH'ten otomatik | `core/pipelines/ocr/credit_experiment.py`, `core/pipelines/ocr/simple.py` |
| `MITAS_FFMPEG_DLL_DIR` | ffmpeg DLL/binary dizini (Windows alignment) | Dahili varsayılan | `scripts/alignment_subprocess.py` |
| `MITAS_OLLAMA` | Ollama API base URL (VLM künye okuma) | `http://127.0.0.1:11434` | `scripts/credit_video_read.py` |
| `MITAS_CREDIT_MODELS` | VLM künye modelleri (virgülle ayrılmış) | `gemma4:26b,qwen2.5vl:7b` | `scripts/credit_video_read.py` |

---

## OCR

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `MITAS_OCR_GLM_CONSENSUS` | GLM çift-motor mutabakatını açar/kapar (`0` = kapalı) | `1` (açık) | `scripts/_pipe_ocr.py` |
| `MITAS_OCR_FALLBACK` | OCR fallback zincirini açar/kapar | açık | `core/pipelines/ocr/fallback_strategy.py` |
| `MITAS_OCR_ALLOW_MODEL_DOWNLOAD` | İlk çalıştırmada model indirmeye izin verir (`1/true/yes`) | kapalı | `core/pipelines/ocr/credit_experiment.py`, `scripts/profile_kj_dataset.py` |
| `MITAS_OCR_PYTHON` | Tedial job runner'ın OCR için kullandığı Python yolu | — (sistem Python) | `core/api/tedial/job_runner.py` |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR` | PaddleOCR detection model dizini | — (otomatik) | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR` | PaddleOCR recognition model dizini | — (otomatik) | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME` | PaddleOCR detection model adı | `PP-OCRv5_mobile_det` | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME` | PaddleOCR recognition model adı | `PP-OCRv5_mobile_rec` | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_DEVICE` | PaddleOCR çalıştırma cihazı (`cpu`/`gpu`) | Otomatik tespit | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_PADDLEOCR_USE_REAL_MODELSCOPE` | ModelScope üzerinden gerçek model kullan (`1/true/yes`) | kapalı | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_TESSERACT_LANG` | Tesseract dil kodu | `tur+eng` | `core/pipelines/ocr/credit_experiment.py`, `core/pipelines/ocr/simple.py` |
| `MITAS_TESSERACT_CMD` | Tesseract binary yolu | PATH'ten otomatik | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_TESSERACT_TESSDATA_DIR` | Tesseract tessdata dizini | Otomatik tespit | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_ONEOCR_CONFIG_DIR` | OneOCR konfigürasyon dizini | — | `core/pipelines/ocr/credit_experiment.py` |

---

## Tedial Entegrasyonu

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `MITAS_TEDIAL_AUTO_LOGIN` | Otomatik oturum açmayı etkinleştirir (`1/true/yes/on`) | `0` (kapalı) | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_USERNAME` | Tedial kullanıcı adı | — | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_PASSWORD` | Tedial şifresi (User env'de saklanmalı) | — | `core/api/tedial/router.py` |
| `TEDIAL_USERNAME` | `MITAS_TEDIAL_USERNAME` yoksa fallback | — | `core/api/tedial/router.py` |
| `TEDIAL_PASSWORD` | `MITAS_TEDIAL_PASSWORD` yoksa fallback | — | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_USERNAME_FIELD` | Login form kullanıcı adı alanı adı | `j_username` | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_PASSWORD_FIELD` | Login form şifre alanı adı | `j_password` | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_LOGIN_PATH` | Tedial login gönderim yolu | `/iTClient/j_security_check` | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_REMEMBER_FIELD` | "Beni hatırla" form alanı adı | `""` (yok) | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_REMEMBER_VALUE` | "Beni hatırla" alanı değeri | `on` | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_DEV_COOKIE_ATTACH` | Geliştirici cookie ekleme modu | — | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_JOB_STORE` | Tedial iş kuyruğu depo dizini | Otomatik | `core/api/tedial/import_queue.py` |
| `MITAS_TEDIAL_SESSION_DIR` | Tedial oturum verisi dizini | Otomatik | `core/api/tedial/session.py` |
| `MITAS_ASR_TRANSCRIBE_URL` | ASR transcribe endpoint URL'si | `http://127.0.0.1:8787/api/asr/transcribe` | `core/api/tedial/router.py` |
| `MITAS_PIPELINE_RUN_URL` | Pipeline çalıştırma endpoint URL'si | `http://127.0.0.1:8787/api/pipeline/run` | `core/api/tedial/router.py` |

---

## Güvenlik / Erişim

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `MITAS_ACCESS_SECRET` | API erişim sırrı (token doğrulama) | `config/.mitas_access_secret` dosyasından okunur | `core/api/access.py` |
| `MITAS_ACCESS_SECRET_FILE` | `MITAS_ACCESS_SECRET` yoksa secret dosya yolu | `config/.mitas_access_secret` | `core/api/access.py` |
| `MITAS_ACCESS_COOKIE_SECURE` | Cookie'yi Secure flag ile gönderir (`1/true/yes/on`) | kapalı | `core/api/access.py` |

---

## Transformers / Framework

| Değişken | Amaç | Default | Kullanan dosya(lar) |
|---|---|---|---|
| `USE_TF` | HuggingFace Transformers TF backend'ini devre dışı bırakır | `"0"` (hard-set, TF↔numpy2 çökmesi önler) | `scripts/_pipe_asr.py`, `scripts/_channel_lang.py`, `scripts/mmslid_test.py` |
| `USE_FLAX` | HuggingFace Transformers Flax backend'ini devre dışı bırakır | `"0"` (hard-set) | `scripts/_pipe_asr.py` |
