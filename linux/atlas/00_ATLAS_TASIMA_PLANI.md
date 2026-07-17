# 00 · ATLAS → WSL Ubuntu (F:) Taşıma Planı

> **Talimat (Çağatay, 2026-07-12):** ATLAS projesini Windows'tan izole bir Linux (WSL Ubuntu)
> ortamına — F: diskine — taşı. MITAS taşıması ŞABLON ([12](../12_WSL_F_SIFIRDAN_KURULUM.md),
> [06](../06_VENV_KURULUM.md), [02](../02_ENVANTER.md)). **Bu belge PLAN'dır** — keşif
> 2026-07-12'de salt-okuma yapıldı, hiçbir kurulum/kopyalama YAPILMADI. Uygulama onay bekler.

**Kaynak durum (ölçüldü, 2026-07-12):**
- ATLAS kökü: `E:\ATLAS` (2026-07-12'de F:→E: taşındı, `E:\ATLAS\TASINMA_NOTU_2026-07-12.md`).
- Bare repo: `E:\ATLAS_git\atlas.git` (origin; aktif dal `feat/atlas-content-analytics`) + bundle yedeği.
- Yedekler: `E:\ATLAS_backups`.
- Ollama modelleri: `E:\OllamaModels` (MITAS'la paylaşımlı depo; ATLAS'a özel `*-atlas1` + `qwen35-35b-test`).
- Toplam ağaç ~57 GB / 447k dosya. Kırılım: venvs 24.8 · Ornek Video 18 · outputs 4.4 ·
  models 1.8 · yüzbankası 1.8 · hf-cache 1.2 · tools 0.4 · webui/node_modules 0.3 · .git 0.3 GB.

---

## 1 · ATLAS nedir (keşif özeti)

ATLAS, tamamen yerel (on-prem, **KVKK**: bulut LLM/servis YOK, ağ yalnız localhost Ollama),
web arayüzlü bir **Türkçe TV-yayını analiz sistemi** (pilot kanal: TRT Haber). 24 saatlik yayını
kategorilere ayırır (haber/reklam/kamu spotu/program), bültenleri bireysel haberlere böler
(timecode'lu), Türkçe transcript (ASR+diyarizasyon) ve KJ (alt bant başlık) metni çıkarır,
haberleri taksonomiye eşler ve **konu/aktör-airtime** (share-of-voice, dakika) raporu üretir.
Çıktı: PDF (ReportLab) + React webui (+ semantik arama).

**Omurga:** `scripts/process_clip.py` — 23-aşamalı, hata-izolasyonlu DAG orkestratörü
(DEC-049). Her aşama ayrı script'i **ayrı venv'in python'ıyla** subprocess olarak koşturur:

| Aşama grubu | Script → venv |
|---|---|
| scan (ROI OCR: saat+KJ) | `scan_clip_fast.py` → **ocr** (motor: **OneOCR** — Windows-only!) |
| kj (çok-kare KJ okuma) | `kj_read.py` → **visual** (glm-ocr:atlas1 + OneOCR guard) |
| audio/asr | ffmpeg + `asr_full.py` → **asr** (faster-whisper large-v3-turbo + pyannote 3.1) |
| embed | `embed_segments.py` → **core** (bge-m3:atlas1, Ollama /api/embed) |
| proxy/scene/layer_a | `make_proxy.py`, `scene_detect.py` (PySceneDetect), `layer_a.py` → **visual/core** |
| jenerik | `jenerik_detect.py` → **ocr** (BULMA=OneOCR, OKUMA=glm-ocr:atlas1) |
| structural/bulletins/seg | → **core** (story_segmenter: bge-m3 vadi + qwen35 arbiter) |
| topic/ingest/chunk/digest | → **core** (chunk_digest: qwen35-35b-test map-reduce) |
| faces | `face_timeline.py` → **face** (insightface buffalo_l + yüzbankası vektörleri) |
| airtime/actor/db_airtime | → **core** |
| reconcile/ner/evidence | `ner_enrich.py` → **nlp** (GLiNER); kalanlar **core** |
| facets/db_facets | `enrich_facets.py` → **core** (qwen35 hakem) |

**Servisler:** `search_server.py` (stdlib http.server, **:8789**, core venv — semantik arama +
onay-kuyruğu API) · webui (vite dev, **:8420**, pnpm) · ~~streamlit~~ (`run_ui.ps1` **BAYAT**:
`src/atlas/ui/app.py` artık yok, taşınmaz).

**DB:** SQLite `atlas.db` (3.3 MB, WAL, `PRAGMA foreign_keys`) + SQLAlchemy 2 + **Alembic**
(10 migration, `alembic/versions/`). DuckDB YOK (MITAS'tan fark). Vektörler dosyada:
`outputs/scan/<clip>/segment_emb.npy` (bge-m3 1024-d) + `yüzbankası/vektorler` (512-d insightface).

**Konfig:** `src/atlas/config/paths.py` **tamamen göreli** (`PROJECT_ROOT=parents[3]`) —
taşınabilir. `settings.py` pydantic-settings, `ATLAS_` env prefix + `.env` (repo'da `.env` yok,
default'lar kullanılıyor). `config/*.yaml` (13 dosya) + `config/profiles/trt_haber*.yaml` (ROI'ler).

---

## 2 · Kararlar (öneri — onaya sunulur)

### K-A1 — AYRI WSL dağıtımı: `ATLAS` (F:\wsl\ATLAS), /opt/atlas
**Öneri:** MITAS dağıtımının İÇİNE `/opt/atlas` DEĞİL; **ayrı `ATLAS` dağıtımı**.
**Gerekçe:**
1. MITAS WSL dağıtımı **yarın bare-metal göçünün provası** — imajı dondurulacak/göçecek.
   ATLAS'ı içine gömmek ATLAS'ın yaşam döngüsünü MITAS imajına bağlar (export/import/silme birlikte).
2. İzolasyon ilkesi (MITAS kurulumunda da geçerliydi): iki projenin apt/venv/systemd evrimi
   birbirini kirletmesin; "üretime dokunma" garantisi dağıtım sınırıyla bedava gelir.
3. Maliyeti düşük: pyenv/apt kurulum scriptleri zaten hazır şablon (`/opt/mitas/linux/setup/`).
**Teknik dikkat (WSL2 gerçeği):** Tüm WSL2 dağıtımları AYNI sanal makinede çalışır —
**localhost/port uzayı ORTAKTIR**. İki dağıtım da 11434 dinleyemez. Bu yüzden:
### K-A2 — ATLAS kendi ollama'sı, port 11435
ATLAS dağıtımında kendi ollama systemd servisi, `OLLAMA_HOST=127.0.0.1:11435`,
`OLLAMA_MODELS=/opt/atlas/models/ollama`. Kod/config'teki `localhost:11434` default'ları
`ATLAS_OLLAMA_URL` env-tohumuna bağlanır (bkz. §4 fix listesi). Böylece MITAS-WSL ollama'sıyla
port çakışması yok, runtime bağı SIFIR. (Alternatif — MITAS dağıtımındaki ollama'yı paylaşmak —
izolasyonu bozar, ELENDİ. GPU zaten tek RTX 3090: iki proje aynı anda ağır model koşturamaz;
bu Windows'ta da böyleydi, davranış değişmiyor.)
### K-A3 — OneOCR ikamesi ZORUNLU (MITAS K1'in ATLAS kopyası)
OneOCR Linux'ta ÇALIŞMAZ. ATLAS'ta OneOCR MITAS'takinden daha merkezi: `scan` aşamasının
(saat-çapası + KJ ROI) **TEK motoru**. İkame adayları: PaddleOCR (saat/KJ ROI — deterministik,
ocr venv'de zaten kurulu) + glm-ocr:atlas1 (zaten OKUMA otoritesi). Geçiş köprüsü ve kapı: §6 Faz F.
### K-A4 — Model ayrımı: özel = blob-kopya, standart = taze pull
`*-atlas1` ve `qwen35-35b-test` etiketleri **registry'de YOK** (yerel özel modeller) →
`E:\OllamaModels`'tan blob-kopya (MITAS Faz E kanıtlı desen, `copy_custom_models.sh`).
Standart taban gerekirse (`qwen3:8b`, `bge-m3:latest`) taze pull MÜMKÜN ama üretim pinleri
atlas1/test etiketleri olduğundan kopya esastır (davranış-nötr göç).
### K-A5 — Davranış-nötr göç + golden kapısı
MITAS K4/01 ilkesi aynen: göç davranışı DEĞİŞTİRMEZ. Kapı ölçüsü: `pytest tests/` (40 test,
`tests/golden_search_trt0604.json` dahil) Windows'la aynı geç/kal + 1 klip uçtan-uca çıktı
karşılaştırması. Tek meşru fark: OneOCR→ikame (o da Faz F kapısında ayrıca ölçülür).
### K-A6 — ffmpeg sürümü
ATLAS Windows'ta **ffmpeg 8.1 shared** taşıyor (`tools/ffmpeg-shared`). Ubuntu 24.04 apt
ffmpeg'i 6.x'tir. Öneri: önce apt ffmpeg ile koş (asr/av zinciri `av` wheel'iyle kendi ffmpeg'ini
taşır; DLL-kayıt kodu `os.name=='nt'` korumalı → Linux'ta no-op). scan/scene/proxy çıktısında
fark görülürse statik ffmpeg 8.x binary'si `/opt/atlas/tools/ffmpeg`'e konur (env-tohumla seçilir).
Karar ölçümle — varsayım değil.
### K-A7 — Test verisi kapsamı (Çağatay kararı GEREKLİ)
MITAS kararında test verisi kopyalanmadı ("sıfırdan koşacağız"). ATLAS için öneri:
**tek klip paketi** — `Ornek Video/TRT HABER HD_null2026-06-04T15_00_20.000Z.mp4` (trt1500
kaynağı ~4.5 GB) veya trt0604 kaynağı + `outputs/scan/trt0604/` (golden-search referansı) +
`atlas.db`. Böylece izole-çalışma kanıtı F'de alınır; 18 GB'lık tüm örnekler KOPYALANMAZ.

---

## 3 · Envanter — Windows'a bağlı her nokta (dosya:satır)

MITAS'taki gibi hüküm: kodun ~%90'ı olduğu gibi taşınır (paths.py göreli, settings env-tabanlı).
Gerçek iş 5 kalem: (A) OneOCR, (B) ffmpeg.exe yolları, (C) venv `Scripts\python.exe` yolları,
(D) Ollama URL default'ları, (E) 8 venv yeniden kurulum.

### A — OneOCR (mimari iş; Faz F)

| Yer | Rol | Kritiklik |
|---|---|---|
| `scripts/scan_clip_fast.py:10,70-80` (`_winit` worker) | **scan aşamasının TEK motoru** — saat + KJ ROI, multiprocessing CPU | **KRİTİK** |
| `src/atlas/ocr/kj_ocr.py:13` (`ONEOCR_DIR=E:\ATLAS\tools\oneocr`), `:34-36` (`import oneocr`) | KJ satır OCR sınıfı (scan'in motoru) | **KRİTİK** |
| `src/atlas/analyze/jenerik.py:7,132-157` | jenerik kart **BULMA** ayağı (OKUMA zaten glm-ocr) | Yüksek |
| `src/atlas/analyze/kj_read.py:11,63,273-381` | glm-okumasına karşı OneOCR **guard/yedek** (diakritik koruması, `clip_scan.oneocr.json`) | Yüksek |
| `scripts/kj_ocr_ensemble.py`, `scripts/_card_oneocr_probe.py`, `ocr_shootout.py` | deney/probe scriptleri | Düşük (taşınmaz) |
| `src/atlas/ocr/text_group.py:239` | OneOCR'a özgü C→R düzeltme yorumu (ikame sonrası gözden geçir) | Düşük |

### B — ffmpeg.exe sabit yolları (env-tohuma çevrilecek)

| Yer | İçerik |
|---|---|
| `scripts/process_clip.py:59-62` | `FFMPEG_EXE = tools/ffmpeg-shared/.../bin/ffmpeg.exe` |
| `src/atlas/segment/vlm_arbiter.py:33` | `FFMPEG_DEFAULT = r"E:\ATLAS\tools\ffmpeg-shared\...\ffmpeg.exe"` (mutlak!) |
| `scripts/make_proxy.py:24-25` | aynı desen |
| `scripts/segment_stories.py:42-43` | aynı desen |
| `scripts/jenerik_discover.py:28-29` | `FFBIN`/`FFMPEG` + PATH'e ekleme (audfprint bare `ffmpeg` çağırır) |
| `scripts/asr_full.py:38,62-76` | ffmpeg-shared **DLL kaydı** — `os.name=='nt'` korumalı → Linux'ta kendiliğinden no-op, fix gerekmez |

**Fix deseni:** `ATLAS_FFMPEG` env-tohumu (`os.environ.get("ATLAS_FFMPEG", <mevcut Windows yolu>)`),
Linux'ta `/usr/bin/ffmpeg` (veya K-A6 statik binary).

### C — venv python yolları (platform dalı)

| Yer | İçerik |
|---|---|
| `scripts/process_clip.py:64-69` | `OCR_PY/ASR_PY/CORE_PY/FACE_PY/VISUAL_PY/NLP_PY = venvs/<p>/Scripts/python.exe` |
| `scripts/search_server.py:92` | `CORE_PY = venvs/core/Scripts/python.exe`; `:324` `creationflags` (Windows-only bayrak) |
| `scripts/retag.py:54-55` | core python.exe (zaten `exists()` fallback'li) |
| `scripts/db_clip.py:81` | `sys.executable` kullanıyor — SORUNSUZ |

**Fix deseni:** tek yardımcı — `venv_python(profile) = venvs/p/("Scripts/python.exe" if os.name=="nt" else "bin/python")`;
`creationflags`'ı `if os.name=="nt"` dalına al.

### D — Ollama URL/model default'ları (env-tohum eklenir, davranış aynı)

| Yer | Default |
|---|---|
| `src/atlas/llm/ollama_client.py:17` | model `qwen35-35b-test`, host `localhost:11434` |
| `src/atlas/llm/embed.py:50` | `bge-m3:atlas1` |
| `src/atlas/llm/vlm_ocr.py:77` | `glm-ocr:atlas1` |
| `src/atlas/analyze/jenerik.py:58` + `config/jenerik.yaml` (`model`,`host`) | `glm-ocr:atlas1`, `localhost:11434` |
| `src/atlas/visual/production_type.py:50,111` | `glm-ocr:atlas1`, `ocr_host localhost:11434` |
| `src/atlas/analyze/layer_a.py:65` | `glm-ocr:atlas1`, `localhost:11434` |
| `src/atlas/segment/vlm_arbiter.py:50,110` | `qwen35-35b-test` |
| `scripts/enrich_event_tags.py:39,116` | `qwen3:8b-atlas1` |
| `scripts/enrich_facets.py:60-61,304-305`, `chunk_digest.py:50`, `segment_stories.py:266`, `topic_report.py:25`, `apply_hybrid.py:74-105` | `qwen35-35b-test` |

**Fix deseni:** host default'larını `ATLAS_OLLAMA_URL` tohumundan oku (K-A2 portu için tek nokta).
Model adları AYNEN kalır (davranış-nötr).

### E — Kozmetik / taşınmayan

- `scripts/run_ui.ps1` — **BAYAT** (`src/atlas/ui/app.py` mevcut değil; streamlit UI kaldırılmış,
  webui React'e geçilmiş). Taşınmaz; istenirse Linux'ta silinme kararı Çağatay'a.
- Docstring'lerdeki `E:\ATLAS` örnekleri: `asr_full.py:12-14`, `face_timeline.py:11,64`,
  `studio_validate.py:8-21`, `faces.py:43` — kod değil, düzeltme opsiyonel.
- `E:\ATLAS\F:ATLAS_backupsdb` — bozuk isimli artık klasör (eski bir yol-bug'ı); TAŞINMAZ.
- `scratch_*.txt`, `atlas.db.bak.*`, `_backups/`, `GPT/out/` — geçici/yedek; taşınmaz (gitignore'da).
- `.claude/` oturum dosyaları — taşınmaz.

---

## 4 · Bağımlılıklar

### 4.1 Python — 8 venv, HEPSİ 3.10.11 (pyvenv.cfg doğrulandı; MITAS ile aynı pyenv kullanılabilir)

Merkezi requirements yalnız `requirements/core.txt` (kısmi). Gerçek kaynak: **Windows'ta pip
freeze reçetesi dondur** (MITAS 06 Adım 1 birebir) → `E:\MITAS\linux\atlas\reqs\<profil>.txt`.
Keşifte site-packages'tan çıkarılan ana paketler:

| venv | Ana paketler (sürüm, Windows'ta ölçüldü) | GPU | Linux notu |
|---|---|---|---|
| **core** | streamlit 1.58, sqlalchemy 2.0.50, alembic 1.18.4, pydantic 2.13.4, opencv 4.13, reportlab 4.4.10, pandas 2.3.3, plotly, pytest 9, uvicorn | — | düz pip |
| **ocr** | paddleocr 3.5.0, paddlepaddle_gpu 3.3.1, paddlex 3.5.1, opencv(+contrib), `oneocr` (SİLİNİR) | CUDA | **Paddle-index'ten** (MITAS Faz D kanıtı: paddle 3.3.1 + tek-opencv-headless çözümü aynen) |
| **asr** | faster_whisper 1.2.1, ctranslate2 4.7.1, pyannote.audio 4.0.4, torch 2.11.0+cu126, onnxruntime-gpu 1.23.2, speechbrain, librosa | CUDA | torch cu126 index; MITAS asr deseni (legacy-resolver gerekmişti) |
| **visual** | scenedetect 0.7, open_clip_torch 3.3.0, timm, torch 2.11.0+cu126, transformers 5.8 | CUDA | düz + torch cu126 |
| **face** | insightface 0.7.3, onnxruntime-gpu 1.23.2, albumentations, hdbscan, torch 2.11.0+cu126, `pyreadline3` (SİLİNİR) | CUDA | onnxruntime-gpu CUDA/cuDNN uyumuna dikkat |
| **nlp** | gliner 0.2.26, transformers 5.1, torch 2.12.0 (CPU) | — | CPU torch yeter |
| **audio** | librosa 0.11, docopt (audfprint için), scipy, `win32_setctime` (SİLİNİR) | — | düz pip |
| **lab** | sentence_transformers, gliner, decord, torch cu126 | CUDA | DENEYSEL — öncelik DÜŞÜK, en son / istenirse |

**Windows-özgü, Linux'ta reçeteden ÇIKARILACAK:** `oneocr`, `pyreadline3`, `win32_setctime`,
`colorama` (kalabilir, zararsız), `pywin32` türevleri. MITAS'ta kanıtlanan sıra:
**paddle(özel index) → reqs(opencv teke indir + Win-strip) → torch SON (cu126) → import-check**.

### 4.2 Sistem (apt)

`ffmpeg` (K-A6), `build-essential`, `git`, `curl`, `sqlite3`, `libgl1` + `libglib2.0-0` (opencv),
pyenv bağımlılıkları (MITAS Faz B listesi aynen), `nodejs` (≥20 LTS) + `pnpm` (webui;
pnpm store F-içi: `pnpm config set store-dir /opt/atlas/.pnpm-store` — Windows'taki F:\.pnpm-store
kaybı dersinden). Tesseract GEREKMEZ (ATLAS kullanmıyor — MITAS'tan fark).

### 4.3 Node/webui

`webui/` — React 18 + vite 6.3.5 + tailwind 4, pnpm-lock mevcut. `node_modules` KOPYALANMAZ
(pnpm symlink yapısı taşınmaz — E: taşınmasında kanıtlandı); Linux'ta
`pnpm install --frozen-lockfile`. Dev port **8420** (`vite.config.ts`, strictPort). Proxy'ler:
`/api→:8787 (MITAS!)`, `/search-api→:8789`. **Not:** `/api` proxy'si MITAS backend'ine işaret
ediyor (webui MITAS webui'sinden türemiş, `package.json name: mitas-webui`) — ATLAS-WSL'de MITAS
8787 YOK; arama sekmesi yalnız :8789 ister. Bu bağ Faz G'de doğrulanır.

### 4.4 Veritabanı / veri

| Öğe | Ne | Taşıma |
|---|---|---|
| `atlas.db` (3.3 MB) | SQLite + Alembic şeması | dosya kopyası + `PRAGMA integrity_check` + `alembic current` doğrula |
| `outputs/scan/<clip>/` | aşama artefaktları (clip_scan.json, segment_emb.npy, haberler.json...) | K-A7 kapsamına göre yalnız seçili klip |
| `yüzbankası/vektorler` + `kisiler.json` (~çekirdek küçük; klasör toplamı 1.8 GB görsel dahil) | yüz embedding bankası (face_timeline girdisi) | çekirdek kopyalanır (gitignore beyaz-listesi zaten tanımlı) |
| `webui/public/data/` | publish_webui çıktıları | yeniden üretilebilir; kopya opsiyonel |
| `config/*.yaml` + `config/profiles/*` | ROI/kanal/taksonomi | git ile gelir (tracked) |

### 4.5 Dış servis

YOK. KVKK: her şey yerel; `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1` (`asr_full.py:31-33`).
HF token yalnız pyannote'u TAZE indirme yolunda gerekir (kopyalama yolunda gerekmez).

---

## 5 · Model listesi — özel (blob-kopya) vs indirilebilir

### 5.1 Ollama (→ `/opt/atlas/models/ollama`, servis portu 11435)

| Model | Rol (kod kanıtı) | Boyut | Kaynak |
|---|---|---|---|
| `glm-ocr:atlas1` | VLM-OCR otoritesi: KJ okuma, jenerik OKUMA, layer_a adlandırma, CANLI tespiti (`vlm_ocr.py:77`, `jenerik.yaml`, `layer_a.py:65`, `production_type.py:50`) | 2.07 GB | **ÖZEL → blob-kopya** `E:\OllamaModels` |
| `bge-m3:atlas1` | embedding 1024-d: embed_segments, semantic_search, story_segmenter vadi, sinir_fix (`embed.py:50`) | 1.08 GB | **ÖZEL → blob-kopya** |
| `qwen35-35b-test` | **birincil metin-LLM**: OllamaClient default'u — digest, facet hakem, VLM-arbiter, segment/topic (`ollama_client.py:3,17`; K5 2026-07-06: eski qwen3.6:atlas1 tabanı kayıp) | 20.56 GB | **ÖZEL → blob-kopya** (registry'de YOK; kaybedilirse yeri doldurulamaz — önce yedeğini al) |
| `qwen3:8b-atlas1` | event-tag zenginleştirme (`enrich_event_tags.py:39`) | 4.87 GB | **ÖZEL → blob-kopya** (tabanı `qwen3:8b` pull edilebilir ama atlas1 pin'i kopyayla korunur) |

Toplam blob-kopya ≈ **28.6 GB**. Deneysel `qwen36-27b-test`/`qwen36-35b-test` üretimde
KULLANILMIYOR → kapsam DIŞI (MITAS kararı 2 ile aynı ilke: yalnız üretim modelleri).

### 5.2 HF / yerel model dosyaları

| Model | Konum (Windows) | Boyut | Taşıma |
|---|---|---|---|
| pyannote speaker-diarization-3.1 (+segmentation-3.0, wespeaker-voxceleb) | `hf-cache/hub/models--pyannote--*` — snapshot pin `84fd2591...` (`asr_full.py:40-46`) | hf-cache toplam 1.2 GB | **KOPYALA** (offline pin; taze indirme HF token + snapshot uyuşmazlığı riski) |
| laion CLIP-ViT-B-32-laion2B (open_clip) | `hf-cache/hub/models--laion--...` (`studio_detector.py:22`) | (1.2 GB içinde) | KOPYALA (veya taze pull — deterministik ağırlık, ikisi de olur) |
| faster-whisper **large-v3-turbo** (CT2) | `models/asr/faster-whisper/large-v3-turbo` (`asr_full.py:51`) | ~1.6 GB | KOPYALA (Systran'dan taze indirmek de mümkün; kopya = birebir parite) |
| insightface **buffalo_l** (5 onnx) | `models/insightface/models/buffalo_l` (`faces.py:22,43`) | ~0.3 GB | KOPYALA (paths.py göreli — aynen çalışır) |
| PaddleOCR det/rec (clock_ocr) | Paddle varsayılan cache (`~/.paddlex` / paket-içi) | küçük | Linux'ta **TAZE indir** (Paddle official models; MITAS `copy_paddle.sh` deseni de mevcut) |
| yüzbankası vektörleri | `yüzbankası/vektorler`, `kisiler.json` | çekirdek küçük | KOPYALA (üretilmesi emek-yoğun — Model değil VERİ ama model-komşusu) |

---

## 6 · Fazlı plan (MITAS 12 şablonu; her fazın kapısı var)

> Sıra ve desen MITAS F-kurulumunun kanıtlanmış ilerlemesiyle birebir. Scriptler
> `/opt/mitas/linux/setup/` örneklerinden uyarlanır (build_venv3.sh, ollama_install3.sh,
> copy_custom_models.sh). **Hiçbir adım E:\ATLAS'ı DEĞİŞTİRMEZ — E: yalnız salt-okuma kaynak.**

### Faz A — WSL dağıtımı `ATLAS` (F'de)
1. Ubuntu 24.04 rootfs → `wsl --import ATLAS F:\wsl\ATLAS <rootfs> --version 2`.
2. `/etc/wsl.conf` → systemd=true; `wsl --shutdown` + yeniden gir.
3. GPU doğrula: `nvidia-smi` → RTX 3090 (MITAS-WSL'de kanıtlı; sürücü 560.94 = CUDA 12.6 max —
   torch cu126 uyumlu, MITAS Faz F dersi: cu130 isteyen paket ÇALIŞMAZ).
**KAPI A:** dağıtım F'de açılıyor, systemd aktif, GPU görünür.

### Faz B — apt + pyenv Python 3.10.11
4. apt: §4.2 listesi (ffmpeg, build-essential, libgl1, node 20 + pnpm, pyenv bağımlılıkları).
5. pyenv 3.10.11 (MITAS'ta pyenv-PATH sorunu→mutlak-yol dersi geçerli).
**KAPI B:** `python --version`=3.10.11; `ffmpeg -version`; `node --version`; `pnpm --version`.

### Faz C — Kod tohumu (tek seferlik) + atlas.env
6. `E:\ATLAS`'ta `git archive HEAD | tar -x -C /opt/atlas` (MITAS Faz C deseni — .git/venv/
   media kopyalanmaz; gitignore zaten venvs/tools/Ornek Video/outputs'u dışlıyor).
   Ek olarak `E:\ATLAS_git\atlas.git`'ten `git clone --bare` yedeği `/opt/atlas/.gitseed`
   (opsiyonel, geçmiş istenirse).
7. Tracked-dışı ama GEREKLİ dosyaları kopyala: `atlas.db`, `config/` zaten tracked;
   `tools/audfprint` (gitignore'da `tools/` DIŞLANMIŞ ama audfprint ÇALIŞMA bağımlılığı —
   ayrıca kopyala veya upstream'den klonla), yüzbankası çekirdeği (§4.4).
8. §3-B/C/D kod fix'lerini uygula (env-tohum + platform dalı; davranış-nötr).
9. `atlas.env` yerleştir (aşağıda §7) — chmod 600.
**KAPI C:** `/opt/atlas` ağacı tam; `grep -rn "E:\\\\ATLAS" src/ scripts/` yalnız docstring;
`python -c "from atlas.config.paths import PROJECT_ROOT; print(PROJECT_ROOT)"` → /opt/atlas.

### Faz D — 8 venv (öncelik: core → ocr → asr → visual → nlp → face → audio → (lab))
10. Önce Windows'ta reçete dondur (E:'ye TEK yazma istisnası — İZİN İSTENİR; alternatif:
    bu keşifteki paket listeleri + pip download ile çözümleme):
    `venvs\<p>\Scripts\python.exe -m pip freeze > E:\MITAS\linux\atlas\reqs\<p>.txt` (8 dosya).
11. Kurulum deseni (MITAS Faz D kanıtlı):
    a. `ocr`: paddlepaddle-gpu 3.3.1 **Paddle-index** → paddleocr/paddlex → opencv'yi tek
       headless'a indir → import-check (`import paddle; from paddleocr import PaddleOCR`).
    b. GPU venv'leri: reçete − (torch*, oneocr, pyreadline3, win32*) → pip install →
       torch==2.11.0 **cu126 index EN SON** (nccl fix dersi) → `torch.cuda.is_available()`.
    c. `nlp`: CPU torch 2.12.0. `audio`: düz pip. `lab`: EN SON, opsiyonel.
**KAPI D:** her GPU-venv'de `cuda=True`; profil import'ları temiz
(`faster_whisper`, `paddleocr`, `insightface`, `gliner`, `scenedetect`, `open_clip`).

### Faz E — Modeller
12. ollama kur (MITAS `ollama_install3.sh` deseni: tgz + systemd) — **Environment:
    OLLAMA_HOST=127.0.0.1:11435, OLLAMA_MODELS=/opt/atlas/models/ollama** (K-A2).
13. 4 özel modeli `E:\OllamaModels`'tan blob-kopya (manifests + blobs; `copy_custom_models.sh`
    uyarlaması). `ollama list` → 4 model; her birine 1 gerçek inference (`ollama run`/API) —
    qwen35 **GPU %100** doğrula (MITAS kanıt deseni).
14. HF/yerel modeller: `hf-cache/hub` → `/opt/atlas/hf-cache` kopya; `models/asr`,
    `models/insightface` → `/opt/atlas/models/...`; Paddle modelleri taze indir.
**KAPI E:** embed (bge-m3 1024-d vektör), vlm_ocr (glm-ocr 1 kare), OllamaClient (qwen35 1
prompt), faster-whisper 10 sn ses, insightface 1 kare — hepsi F-içi, E:'siz çalışır.

### Faz F — OneOCR ikamesi (mimari iş; MITAS 08 şablonu)
15. **Köprü (geçici, opsiyonel):** MITAS 08-Yol-A birebir — Windows host'ta OneOCR HTTP servisi
    (:8791 — MITAS köprüsü 8790 ile çakışmasın), `ATLAS_ONEOCR_BRIDGE` env'i; `kj_ocr.py` ve
    `scan_clip_fast._winit` köprü-istemcisine bakar. Amaç: OCR değişkenini sabit tutarak
    Linux-taşımanın kendisini golden'da izole doğrulamak.
16. **Kalıcı ikame:** `scan_clip_fast` motoru → PaddleOCR (saat ROI zaten `clock_ocr.py`'de
    Paddle-kanıtlı; KJ ROI için Paddle rec) VEYA glm-ocr (GPU maliyeti: scan yoğun-tarama,
    OneOCR CPU'ydu — throughput ÖLÇÜLECEK). `jenerik.py` BULMA ayağı → Paddle-det hızlı kapı.
    `kj_read.py` guard'ları ikame-metnine göre yeniden değerlendir (diakritik guard'ı Paddle
    lehine muhtemelen kalkar — ölçüm işi).
**KAPI F (ATLAS-K1-GATE):** trt0604 (veya seçilen klip) scan+kj+jenerik çıktısı OneOCR-referansla
karşılaştırılır: saat-çapası aynı, KJ başlık seti eşdeğer-veya-iyi, jenerik olay listesi aynı.
"Okunamadı > yanlış oku" ilkesi korunur.

### Faz G — Servisler + webui
17. systemd birimleri: `atlas-ollama.service` (Faz E'de), `atlas-search.service`
    (`/opt/atlas/venvs/core/bin/python scripts/search_server.py`, :8789,
    `EnvironmentFile=/opt/atlas/atlas.env`, `Restart=on-failure`).
18. webui: `pnpm install --frozen-lockfile` (store F-içi) → `pnpm dev --host` (:8420) veya
    `pnpm build` + statik servis. `/api→8787` MITAS-proxy bağını doğrula/koparıp yalnız
    `/search-api` bırak (Faz G bulgusuna göre; kod değişikliği gerekirse Çağatay onayı).
19. Windows tarafından erişim: `http://localhost:8420` (WSL port yansıması otomatik).
**KAPI G:** `GET /api/health` → `{ok:true}`; webui'de gerçek arama sorgusu sonuç döndürür
(E: taşınma-doğrulamasındaki aynı test, bu kez F-içi).

### Faz H — Uçtan-uca kanıt + golden
20. K-A7 test paketi F'ye tek-seferlik kopya.
21. `pytest tests/` (40 test; `pytest.ini testpaths=tests`) — Windows geç/kal sayısıyla karşılaştır.
22. 1 klip `process_clip.py --video ... --profile config/profiles/trt_haber.v1.yaml` uçtan-uca;
    `outputs/scan/<clip>/status.json` tüm aşamalar OK; `gun_pdf.py` PDF üretir;
    `tests/golden_search_trt0604.json` arama golden'ı yeşil.
23. Çıktı karşılaştırma: haber sayısı / airtime dakikaları / KJ başlıkları Windows koşusuyla
    (fark yalnız Faz F ikamesinden ve açıklanmış olmalı).
**KAPI H (BİTİŞ):** ATLAS-WSL tamamen izole (C/D/E'ye runtime bağı yok), klip işliyor,
testler yeşil, servisler systemd'de, Windows/E:\ATLAS'a dokunulmadı.

---

## 7 · atlas.env taslağı (mitas.env şablonu)

```bash
# ATLAS Linux ortam dosyası — systemd EnvironmentFile + `set -a; source atlas.env; set +a`
# chmod 600. Pydantic-settings prefix'i ATLAS_ (src/atlas/config/settings.py).

# ── Çekirdek (settings.py'nin zaten okuduğu) ─────────────────────────────────
ATLAS_DATA_ROOT=/opt/atlas/data
ATLAS_DB_PATH=/opt/atlas/atlas.db
ATLAS_DEFAULT_PROFILE=config/profiles/trt_haber.v1.yaml
# ATLAS_HF_TOKEN=            # yalnız pyannote TAZE indirme gerekirse

# ── Yeni env-tohumları (Faz C kod fix'leriyle eklenir) ───────────────────────
ATLAS_FFMPEG=/usr/bin/ffmpeg           # K-A6: fark çıkarsa /opt/atlas/tools/ffmpeg (8.x statik)
ATLAS_OLLAMA_URL=http://127.0.0.1:11435   # K-A2: ATLAS'ın KENDİ ollama'sı
# ATLAS_ONEOCR_BRIDGE=http://<win-host>:8791   # Faz F köprüsü kullanılırsa

# ── HF / model cache (hepsi F-içi) ───────────────────────────────────────────
HF_HOME=/opt/atlas/hf-cache
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1

# ── ollama servis ortamı (systemd unit'e de yazılır) ─────────────────────────
OLLAMA_HOST=127.0.0.1:11435
OLLAMA_MODELS=/opt/atlas/models/ollama
```

---

## 8 · Doğrulama özeti (kapı → kanıt)

| Kapı | Kanıt komutu |
|---|---|
| A | `nvidia-smi` (WSL içinden), `systemctl is-system-running` |
| B | `pyenv version`, `ffmpeg -version`, `node -v`, `pnpm -v` |
| C | PROJECT_ROOT çıktısı; sabit-yol grep'i temiz |
| D | profil-başına import-check + `torch.cuda.is_available()` tablosu |
| E | 4 ollama modeli inference; bge-m3 embed boyut=1024; whisper/insightface smoke |
| F | scan/kj/jenerik OneOCR-referans karşılaştırma raporu (ATLAS-K1-GATE) |
| G | `curl :8789/api/health`; webui gerçek arama |
| H | `pytest tests/` sayıları; 1 klip status.json ALL-OK; PDF; golden-search yeşil |

---

## 9 · Riskler (dürüst liste)

1. **OneOCR = scan'in tek motoru** (MITAS'ta yalnız ham-OCR kaynağıydı; ATLAS'ta saat-çapası
   dahil scan tümüyle ona dayalı). İkame yanlış saat okursa TÜM timecode'lar kayar. Bu yüzden
   köprü-fazlı geçiş + K1-GATE zorunlu. En büyük iş kalemi.
2. **qwen35-35b-test yeri doldurulamaz** (registry'de yok, tabanı kayıp — K5 kaydı). Blob-kopya
   ÖNCESİ `E:\OllamaModels`'ın bu modelinin ayrıca bir yedeği alınmalı (E:'ye yazmadan, F'ye).
3. **ffmpeg 8.1 → apt 6.x sürüm farkı**: kare-çıkarma/PTS davranışı değişebilir → scan kare
   indeksleri kayabilir. Ölçümle çözülür (K-A6); gerekirse statik 8.x.
4. **WSL ortak port uzayı**: MITAS-WSL ile aynı anda çalışırken 11434/11435, 8787/8789/8420
   ayrımına dikkat; ATLAS birimleri yalnız 11435+8789+8420 kullanır.
5. **GPU çekişmesi**: qwen35 (20.5 GB) + MITAS modelleri aynı 24 GB'a sığmaz — iki proje
   eşzamanlı ağır iş KOŞTURMAZ (Windows'ta da böyleydi; davranış değişmiyor).
6. **venv kurulum sürprizleri**: paddle/onnxruntime-gpu/ctranslate2 CUDA-runtime uyumları.
   MITAS Faz D çözümleri (Paddle-index, tek-opencv, torch-son, legacy-resolver) hazır şablon.
7. **webui'nin MITAS-proxy kalıntısı** (`/api→8787`): ATLAS-WSL'de ölü bağlantı; arama dışı
   sekmeler MITAS backend bekliyor olabilir → Faz G'de haritalanır.
8. **audfprint `tools/` gitignore'da**: git-archive tohumuna GELMEZ; unutulursa
   jenerik_discover kırılır → Faz C adım 7'de açıkça kopyalanıyor.
9. **NTFS→ext4 I/O**: /mnt/e üzerinden koşturma YASAK (MITAS K5 dersi: yavaş + yanıltıcı);
   her şey WSL-içi ext4'te (F'deki vhdx).

## 10 · Çağatay kararı bekleyen açık maddeler

1. **K-A1 onayı:** ayrı `ATLAS` dağıtımı mı, MITAS dağıtımı içinde `/opt/atlas` mı? (öneri: AYRI — gerekçe §2)
2. **K-A7:** test verisi kapsamı — hangi klip(ler) F'ye kopyalanacak?
3. Reçete dondurma için `E:\MITAS\linux\atlas\reqs\`'e pip-freeze YAZMA izni (E:\ATLAS'a değil,
   MITAS plan klasörüne; yalnız okuma yapan freeze komutu venv python'larını çalıştırır).
4. `lab` venv taşınsın mı? (deneysel; öneri: şimdilik HAYIR, gerekirse sonra)
5. webui `/api→8787` MITAS-proxy bağı koparılsın mı? (kod değişikliği = talimat gerekir)
6. `run_ui.ps1` (bayat streamlit) kaderi.
