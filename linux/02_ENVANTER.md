# 02 · Envanter — Windows'a Bağlı Her Nokta

> "Ne değişecek" defteri. 2026-07-10'da `E:\MITAS` kodu tarandı. Her satır gerçek dosya:satır.
> Sınıflandırma: çoğu **mekanik** (env-tohumu zaten var), az sayıda **gerçek kod** (Windows API),
> bir tane **mimari** (OneOCR).

**Özet hüküm:** Kodun ~%85-90'ı olduğu gibi taşınır. Gerçek iş 5 kalemde: (A) yol/env, (B)
Windows-API, (C) fontlar, (D) servis başlatma/ps1, (E) OneOCR + 18 venv yeniden kurulum.

---

## A · Sabit Windows yolları

**İyi haber:** Üretim modülleri yolları zaten `os.environ.get("MITAS_...", r"E:\...")` tohumuyla
okuyor. Yani env doğru kurulunca kod değişmeden çalışır. Sabit fallback'lerin çoğu tek-seferlik
debug script'inde (production değil) — onlara dokunmaya gerek yok.

### A1 — Env-tohumlu yol değişkenleri (yalnız env ayarla, kod değişmez)

Bunları Linux'ta `mitas.env` içinde tanımla (bkz. [07](07_SERVISLER_SYSTEMD.md)):

| Env değişkeni | Windows değeri (örnek) | Linux hedefi (örnek) |
|---|---|---|
| `MITAS_PROJECT_ROOT` | `E:\MITAS` | `/opt/mitas` |
| `MITAS_FFMPEG` / `MITAS_FFPROBE` | `E:\MITAS\tools\...\ffmpeg.exe` | `/usr/bin/ffmpeg` / `/usr/bin/ffprobe` |
| `MITAS_FFMPEG_DLL_DIR` | ffmpeg shared bin | (Linux'ta gereksiz — sistem ffmpeg) |
| `MITAS_KB_DUCKDB` | `Y:\DIGER\Mitas_Files\MitaData\mitas.duckdb` | `/data/mitas/MitaData/mitas.duckdb` |
| `MITAS_IMDB_DUCKDB` | `Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb` | `/data/mitas/IMDB/db/imdb.duckdb` |
| `MITAS_WIKIDATA_DUCKDB` | `X:\DIGER\...\mitas.duckdb` | `/data/mitas/MitaData/mitas.duckdb` |
| `MITAS_PDFMITAS_DIR` | `E:\MITAS\OCR-worktree\pdf-mitas` | `/opt/mitas/OCR-worktree/pdf-mitas` |
| `MITAS_ONEOCR_CONFIG_DIR` | OneOCR config | (K1 sonrası kalkar) |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR` | Paddle model | `/opt/mitas/models/ocr/paddle/...` |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR` | Paddle model | `/opt/mitas/models/ocr/paddle/...` |
| `MITAS_TESSERACT_TESSDATA_DIR` | `C:\Program Files\Tesseract-OCR\tessdata` | `/usr/share/tesseract-ocr/*/tessdata` |
| `MITAS_OLLAMA_URL` | `http://127.0.0.1:11434` | (aynı) |
| `MITAS_SERILER_ROOT` | dizi kök | `/data/mitas/seriler` |
| `MITAS_WEB_CACHE_DIR` | web cache | `/opt/mitas/cache/web` |
| `MITAS_DUCKDB_CACHE` | duckdb cache | `/opt/mitas/cache/duckdb` |
| `MITAS_FLOW_STAGING` | `E:\MITAS\cache\staging` | `/opt/mitas/cache/staging` |

> **İş:** Faz 0'da bu env dosyasını yaz ve doğrula. Kod fix DEĞİL, konfigürasyon.

### A2 — Env-tohumu OLMAYAN sabit yollar (kod düzeltmesi gerekir)

Bunlar üretim yolunda ama env okumadan sabit yazılmış → env-tohumuna çevrilecek. Tam liste ve
düzeltme [05](05_KOD_DEGISIKLIKLERI.md)'te. Başlıcalar:

- `core/api/asr_server.py:161` — Python exe sabit (`C:\Users\TRT03\...\python.exe`)
- `core/api/asr_server.py:696,714` — `MITAS_FLOW_STAGING` var ama `Path("E:\\").stat().st_dev` cihaz-kontrolü Windows'a özgü
- `core/api/asr_server.py:1184-1185` — `nvidia-smi` sabit yolları (ilk aday PATH'ten `"nvidia-smi"` — Linux'ta kendiliğinden çalışır, düşük risk)
- `core/pipelines/ocr/jenerik_frame_pool_detector.py:385` — `JENERIK_PADDLE_MODEL_ROOT` tohumu VAR, yalnız default Windows
- `core/pipelines/ocr/credit_experiment.py:3619-3675` — Tesseract exe + tessdata sabit yolları
- `scripts/credit_crosscheck.py:20-21` — `X:\`, `Y:\` DuckDB (env-tohumu var, default Windows)

### A3 — Tek-seferlik debug/test script'leri (TAŞINMASINA GEREK YOK)

`.tmp/`, `_dbg_*.py`, `_vlm_*`, `outputs/*.py`, `mutfak/`, `Mitas_Files/*/scripts/` altındaki
sabit yollar üretim değil. Linux'ta çalıştırılmayacaklar → yok say. (Toplam 148 eşleşmenin
çoğunluğu bu sınıfta.)

---

## B · Windows API çağrıları (gerçek kod düzeltmesi)

Yalnız 3 nokta, hepsi `scripts/mitas_pipeline.py` içinde. Tam ikame kodu [05](05_KOD_DEGISIKLIKLERI.md)'te.

| Yer | Ne yapıyor | Linux ikamesi |
|---|---|---|
| `mitas_pipeline.py:2106-2118` | `ctypes.windll.kernel32.GlobalMemoryStatusEx` — ASR-ön-sübap için commit-boş RAM | `/proc/meminfo` (`MemAvailable`+`SwapFree`) veya `psutil` |
| `mitas_pipeline.py:2362-2368` | PowerShell ile öksüz `llama-server.exe` temizliği | `pkill -f llama-server` + systemd (öksüz sorunu Linux'ta büyük ölçüde yok) |
| `mitas_pipeline.py:2372-2374` | `ollama.exe serve` başlatma (`creationflags=0x08000000`) | `systemctl start ollama` (Linux'ta ollama systemd servisi) |

> Not: `nvidia-smi` (asr_server) A2'de; pynvml zaten platform-nötr, fallback yolu düzeltilir.

---

## C · Font bağımlılıkları (PNG/PDF kompozisyon)

`C:\Windows\Fonts\arial.ttf` (+ arialbd, segoeui, calibri) ~6 dosyada. Künye PNG/PDF çizimi
kullanıyor. **Üretim PDF hattı `_pipe_pdf.py` font-yolu İÇERMİYOR** (düşük risk).

- `scripts/_prototype_credits_pdf_build.py:89-96`, `compose_*`, `compose_credits_png_batch.py:29`
- `core/pipelines/ocr/text_layer_descroll.py:1268`, `poc_llm_reconciler/render_clean_sheet.py:16`
- `scripts/ocr_model_healthcheck.py:117-119`, `scripts/_info_card.py:15-16`

**İkame:** `ttf-mscorefonts-installer` (gerçek Arial) veya Liberation Sans (Arial metrik-uyumlu).
Font yolunu bir env-tohumuna bağla. Detay [05](05_KOD_DEGISIKLIKLERI.md).

---

## D · PowerShell / servis başlatma

Üretimde etkin gerçek script'ler (node_modules/venv Activate.ps1'leri hariç):

| Script | Görev | Linux ikamesi |
|---|---|---|
| `scripts/start_mitas.ps1` | 8787 (asr_server) + 8765 (tedial) uvicorn başlat, User env yükle, port temizle | systemd birimleri `mitas-asr.service`, `mitas-tedial.service` ([07](07_SERVISLER_SYSTEMD.md)) |
| `scripts/startup_mitas_all.ps1` | Windows logon autostart (backend+WebUI) | systemd `WantedBy=multi-user.target` |
| `scripts/mitas_103_watchdog.ps1`, `outputs/gece_nobetci.ps1` | watchdog/nöbetçi | systemd `Restart=always` + timer, veya `nobetci_daemon.py` (Python, taşınabilir) |
| `scripts/collect_103_pdfs.ps1`, gece batch ps1'leri | tek-seferlik toplu iş | bash script'e çevir (gerekirse) |

> WebUI: `http://localhost:5173` (Vite dev) + backend uvicorn — Node/Vite Linux'ta değişmeden çalışır.

---

## E · OneOCR + 18 venv (en büyük emek)

### E1 — OneOCR çağrı noktaları (K1 ile değişecek)

| Yer | Rol | Kritiklik |
|---|---|---|
| `scripts/_pipe_ocr.py:349-351` | **ham-OCR okuma — künyenin ANA kaynağı** | KRİTİK |
| `core/pipelines/ocr/jenerik_oneocr_detector.py:50-52` | jenerik onset detektörü (Plan B) | Orta |
| `core/pipelines/ocr/credit_experiment.py:511-519,742` | credit deney motoru | Orta |
| `core/pipelines/ocr/simple.py:195-200` | basit OCR yolu | Düşük |

İkame stratejisi ve golden-kapısı: [08](08_ONEOCR_IKAME.md).

### E2 — 18 venv (Python 3.10.11)

`alignment, asr, audio, core, denoise, face, ina, internvl, locateanything, minicpmv, nemo,
ocr, stt, tag, translate, tts, visual, vlm` — hepsi Linux'ta yeniden kurulacak. Merkezi
`requirements.txt` YOK (venv'ler ad-hoc). Reçete çıkarma + kurulum + duman testi: [06](06_VENV_KURULUM.md).

**Not:** Tüm kütüphaneler (torch, PaddleOCR, transformers, vLLM, NeMo, faster-whisper, pyannote,
ffmpeg, DuckDB, FastAPI) Linux'ta mevcut — çoğu orada daha sorunsuz. Bu bir "port" değil,
"yeniden kur + sürüm-pinle + duman-test" işi.
