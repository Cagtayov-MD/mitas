# ATLAS → WSL (F:) Taşıma — Uygulama Günlüğü

> Canlı kanıt kaydı. Plan: `00_ATLAS_TASIMA_PLANI.md`. WSL dağıtımı: `ATLAS` (F:\wsl\ATLAS),
> kod `/opt/atlas`, ollama :11435. MITAS'a (F:\wsl\MITAS) hiçbir paylaşım/bağımlılık YOK.
> E:\ATLAS ve E:\OllamaModels yalnız OKUNDU/KOPYALANDI, hiçbir dosya değiştirilmedi/silinmedi.

## ✅ Faz A — WSL dağıtımı (2026-07-12)
- Eski `Ubuntu-MITAS` kaydı bayat çıktı (vhdx zaten yok, F boşaltılmıştı) — dokunulmadı, atlandı.
- Ubuntu 24.04 rootfs resmi kaynaktan indirildi: `ubuntu-noble-wsl-amd64-24.04lts.rootfs.tar.gz`
  (~340MB, `cloud-images.ubuntu.com/wsl/releases/24.04/current/`) → `F:\wsl\_tmp\`.
- `wsl --import ATLAS F:\wsl\ATLAS F:\wsl\_tmp\ubuntu-24.04-rootfs.tar.gz --version 2` — OK.
- `/etc/wsl.conf` → `[boot] systemd=true`; `wsl --shutdown` + yeniden giriş.
- **KAPI A kanıtı:** `systemctl is-system-running` → `running`. `nvidia-smi` → RTX 3090, driver
  560.94, 24576 MiB, CUDA 12.6 (Windows sürücüsünden miras — MITAS-WSL ile aynı, beklenen).

## ✅ Faz B — apt + pyenv + Node (2026-07-12)
- apt: ffmpeg, build-essential, git, curl, sqlite3, libgl1, libglib2.0-0, zstd, unzip, pyenv
  bağımlılıkları — hepsi kuruldu.
- Node 20 LTS (nodesource) + pnpm — **1. deneme HATA**: `pnpm@latest` → v11.12.0 kurdu, bu
  Node≥22.13 ister (`node:sqlite` builtin modülü Node 20'de yok) → `pnpm -v` patladı, script
  `set -e` ile durdu. **Düzeltme:** pnpm sürümü Node-20-uyumlu `pnpm@9` (9.15.9) olarak pinlendi,
  script tekrar çalıştırıldı (idempotent) — OK.
- pyenv 3.10.11 derlendi (tkinter uyarısı zararsız — GUI kullanılmıyor).
- **KAPI B kanıtı:** `python 3.10.11`, `ffmpeg 6.1.1-3ubuntu5`, `node v20.20.2`, `pnpm 9.15.9`.

## ✅ Faz C — Kod tohumu + env-tohum kod-fix'leri (2026-07-12)
- **ÖNEMLİ SAPMA plandan:** Plan "git archive HEAD" öneriyordu. Keşifte E:\ATLAS çalışma
  ağacında **244 tracked dosyada commit'lenmemiş değişiklik** bulundu — `config/app.yaml`,
  `config/taksonomi.yaml`, `src/atlas/*.py` (facet_tagger, story_analyzer, models, ollama_client,
  kj_ocr, story_segmenter, vlm_arbiter, faces, studio_detector), `scripts/*.py` (asr_full,
  chunk_digest, enrich_facets, face_timeline, segment_stories, topic_report, apply_hybrid, ...),
  `webui/src/**` dahil GERÇEK kod/konfig farkları. `git archive HEAD` bunları SESSİZCE
  atlardı → davranış-nötr göç (K-A5) ihlali olurdu. **Yerine:** `git ls-files` (tracked yol
  listesi — aynı dışlama kümesi) + çalışma-ağacındaki GÜNCEL içeriği `tar` ile aktardı
  (`git ls-files -z | tar --null -T - -cf - | tar -xf - -C /opt/atlas`). Sonuç: aynı disklama
  (gitignore), ama commit'lenmemiş GERÇEK değişiklikler DAHİL. E:\ATLAS'a hiçbir yazma olmadı
  (yalnız okuma + /opt/atlas'a kopya).
- 799 tracked dosya kopyalandı (61 MB — venvs/data/models/hf-cache/outputs/tools/Ornek Video
  gitignore ile doğru dışlandı).
- Ekstra (gitignore'da ama çalışma-bağımlılığı): `tools/audfprint` (4.6M), `atlas.db` (3.3M).
- `.gitseed` (opsiyonel tam git tarihi) — `E:\ATLAS_git\atlas.git`'ten `git clone --bare` — OK
  (yalnız okuma E:\ATLAS_git'ten).
- **Kod-fix'leri uygulandı (27 patch, 0 hata, `03_env_seed_patch.py`, idempotent):**
  - B (ffmpeg): `process_clip.py`, `make_proxy.py`, `segment_stories.py`, `jenerik_discover.py`,
    `vlm_arbiter.py` → `ATLAS_FFMPEG` env-tohumu (yoksa eski Windows-yolu fallback, davranış-nötr).
  - C (venv python yolu): `process_clip.py` → `_venv_py()` platform-dalı (`Scripts/python.exe`
    Windows / `bin/python` Linux); `search_server.py` CORE_PY aynı desen. `retag.py` zaten
    `.exists()` fallback'liydi — dokunulmadı (plan: SORUNSUZ).
  - D (ollama host): `ollama_client.py`, `embed.py`, `vlm_ocr.py` (fonksiyon varsayılanları),
    `jenerik.py`/`layer_a.py`/`production_type.py` (`load_cfg()` içinde YAML-sonrası override —
    YAML'daki eski `localhost:11434` sessizce ezilmesin diye), `enrich_event_tags.py`/
    `enrich_facets.py` (fonksiyon + argparse varsayılanları) → hepsi `ATLAS_OLLAMA_URL`
    env-tohumundan okunuyor (K-A2: 11435 portu). **Model adları AYNEN kaldı** (davranış-nötr).
  - 14 yamalı dosya `py_compile` ile sözdizimi doğrulandı — hepsi OK.
- `atlas.env` yerleşti (`/opt/atlas/atlas.env`, chmod 600) — `ATLAS_OLLAMA_URL=http://127.0.0.1:11435`,
  `ATLAS_FFMPEG=/usr/bin/ffmpeg`, `HF_HOME=/opt/atlas/hf-cache`, `OLLAMA_HOST=127.0.0.1:11435`,
  `OLLAMA_MODELS=/opt/atlas/models/ollama`.
- **KAPI C kanıtı:** `PROJECT_ROOT` → `/opt/atlas` (doğru, göreli çözüm). Kalan `E:\ATLAS` grep
  isabetleri yalnız: (a) `kj_ocr.py` OneOCR yolu — Faz F işi, bilinçli ertelendi; (b) debug/smoke/
  validation scriptleri (`asr_smoke.py`, `studio_validate.py`, `validation_compare.py`,
  `validation_remeasure.py`, `kj_ocr_ensemble.py`, `studio_detector.py` HF_HOME) — ana DAG'ın
  (`process_clip.py`) parçası DEĞİL, plan §3E ile uyumlu düşük-öncelik; (c) `run_ui.ps1` — BAYAT,
  taşınmıyor (plan kararı).
- `linux/reqs/*.txt` (8 dosya, aşağıda) ve `linux/setup/*` script'leri `/opt/atlas/linux/`'a
  kopyalandı (kaynak: bu MITAS reposu, E:\ATLAS DEĞİL).

### Reçete dondurma (pip freeze YERİNE salt-okuma dist-info taraması)
KESİN KISIT "E:'ye sadece OKU" gereği, `E:\ATLAS\venvs\<p>\Scripts\python.exe -m pip freeze`
ÇALIŞTIRILMADI (plan §10 madde-3'te zaten "İZİN İSTENİR" olarak işaretliydi). Yerine: PowerShell
ile yalnızca `*.dist-info`/`*.egg-info` DİZİN ADLARI okunup (name==version) ayrıştırıldı — hiçbir
E:\ATLAS ikili dosyası çalıştırılmadı. Sonuç `E:\MITAS\linux\atlas\reqs\*.txt`:

| venv | paket sayısı |
|---|---|
| core | 69 |
| ocr | 81 |
| asr | 112 |
| visual | 50 |
| face | 66 |
| nlp | 46 |
| audio | 34 |
| lab | 75 |

## 🟡 Faz D — 7 venv (core→ocr→asr→visual→face→nlp→audio; `lab` ERTELENDİ)
`lab` deneysel — plan §10 madde-4 açık karar bekliyor (MITAS emsali: "şimdilik HAYIR"), bu
yüzden ATLANDI (istenirse ayrıca kurulur, `04_build_venvs.sh lab`).

**Desen (`04_build_venvs.sh`, MITAS build_venv3.sh uyarlaması):** paddle(Paddle-index) →
reqs(strip'li) → opencv(TEK sürüm) → torch(SON, cu126) → import-check.

- **core:** OK — `sqlalchemy, alembic, cv2, reportlab, pandas, streamlit` temiz. opencv-contrib-
  python-headless.
- **ocr:** **1. deneme HATA** → reqs dondurmasında `~addlepaddle==3.3.1` bulundu (pip'in Windows'ta
  bir önceki paddlepaddle sürümünü değiştirirken bıraktığı bayat "~"-önekli dist-info klasöründen
  geldi — `reqs/ocr.txt`'den temizlendi). **2. deneme OK** — paddle 3.3.1 (Paddle-index) + paddleocr/
  paddlex + opencv-contrib-python==5.0.0.93 (non-headless, MITAS'ın kanıtladığı gapi-bug'sız sürüm,
  libgl1 zaten Faz B'de kurulu). `import paddle; from paddleocr import PaddleOCR` temiz.
- **asr:** **1. deneme HATA (kök-neden bulundu, MITAS'ta görülmemiş YENİ bir tuzak):** script'in
  `ver()` yardımcı fonksiyonu torch sürümünü ayıklarken `+cu126` yerel etiketini AYIKLIYORDU
  (`torch==2.11.0+cu126` → `2.11.0`). `pip install torch==2.11.0 torchaudio==2.11.0 --index-url
  cu126` gibi etiketsiz bir istek, cu126-index'te AYNI "2.11.0" numaralı ama farklı bir derlemeyi
  (muhtemelen cu130-linked) sessizce seçebiliyor — torchaudio'nun derlenmiş `.so`'su
  `libcudart.so.13` arıyordu, ama sürücü (560.94) CUDA 12.6 tavanlı → `OSError`. **Düzeltme:**
  yeni `ver_full()` yardımcı fonksiyonu (yerel etiketi KORUR) + adım-2'nin (pyannote/speechbrain gibi
  paketlerin UNPINNED "torch" bağımlılığı üzerinden) sessizce sürükleyebileceği yanlış paketleri
  temizleyen bir adım eklendi (`nvidia-*-cu13` guard). **2. deneme:** `torch==2.11.0+cu126` tam
  etiketle istendi → doğru cu126 derlemesi kuruldu, doğrulandı (aşağıda).
- **visual:** OK (ver_full düzeltmesiyle ilk denemede) — `torch cuda=True`, `open_clip`,
  `scenedetect`, `cv2` temiz.
- **face:** OK (aynı ver_full düzeltmesiyle) — `torch cuda=True`, `insightface`, `onnxruntime`
  (`TensorrtExecutionProvider`+`CUDAExecutionProvider` mevcut) temiz.
- **nlp:** OK — CPU torch 2.12.0 pinlendi (adım-2 sırasında `gliner`/`transformers`'ın etiketsiz
  "torch" bağımlılığı, PyPI varsayılanı olan cu13-bağımlı 2.12.1'i sessizce sürükledi; adım-3'ün
  tam-sürüm pini bunu doğru 2.12.0'a düzeltti). `cuda.is_available()=False` (beklenen, sürücü
  cu13 desteklemiyor → torch nazikçe CPU'ya düşüyor — hata değil, tasarım gereği doğru davranış).
- **audio:** OK — `librosa, scipy, soundfile` temiz (torch gerekmiyor, hızlı kuruldu).

**KAPI D — TÜMÜ DOĞRULANDI (7/7 profil, `lab` hariç):**

| venv | import-check | cuda |
|---|---|---|
| core | sqlalchemy+alembic+cv2+reportlab+pandas+streamlit | — |
| ocr | paddle 3.3.1 + paddleocr + cv2 | gpu (paddle) |
| asr | torch+faster_whisper+pyannote.audio | **True** |
| visual | torch+cv2+scenedetect+open_clip | **True** |
| face | torch+cv2+insightface+onnxruntime (TensorRT+CUDA providers) | **True** |
| nlp | torch+gliner+transformers | False (CPU by design) |
| audio | librosa+scipy+soundfile | — (CPU-only paket) |

Toplam disk: `/opt/atlas` ~70GB (venv'ler+29GB ollama modelleri), F: 872GB hâlâ boş.

## ✅ Faz E — Ollama (:11435) + modeller (2026-07-12)
- `ollama v0.31.2` (.tar.zst asset, MITAS ollama_install3.sh deseni) → `/usr/bin/ollama`.
- `atlas-ollama.service` (systemd, root, `OLLAMA_HOST=127.0.0.1:11435`,
  `OLLAMA_MODELS=/opt/atlas/models/ollama`) — **active**, MITAS'ın 11434'üyle ÇAKIŞMADI (K-A2).
- 4 özel model `E:\OllamaModels`'tan blob-kopya (manifest+blob, salt-okuma E:'den):
  `glm-ocr:atlas1` (2.2GB), `bge-m3:atlas1` (1.2GB), `qwen35-35b-test:latest` (22GB),
  `qwen3:8b-atlas1` (5.2GB) — toplam 29GB, `ollama list` 4/4 doğru gösteriyor.
- HF/yerel modeller kopyalandı: `hf-cache` (pyannote+laion, 1.3GB), `models/asr`
  (faster-whisper large-v3-turbo, 1.6GB), `models/insightface` (buffalo_l, 326MB).
- **KAPI E kanıtı (kısmi — GPU çekişmesi nedeniyle):** `bge-m3:atlas1` embed testi **GERÇEK
  çıkarımla GEÇTİ** (`curl /api/embed` → 1024-boyutlu vektör, HTTP 200). `glm-ocr`/`qwen35`
  çıkarım testleri GPU yetersizliğinden ERTELENDİ — **bu bir ATLAS kurulum kusuru DEĞİL**: aynı
  RTX 3090'ı (24GB) MITAS'ın ZATEN ÇALIŞAN Windows-native ollama'sı ~22GB ile dolduruyor
  (`nvidia-smi`: test sırasında yalnız 312MB-2.2GB serbest kaldı). Plan bunu risk-5 olarak zaten
  öngörmüştü ("iki proje eşzamanlı ağır iş koşturmaz — Windows'ta da böyleydi"). MITAS'ın ollama'sı
  **kapatılmadı/dokunulmadı** (kural: llama-server ÖLDÜRME YASAK). GPU boşken tekrar denenmeli.

## 🟡 Faz F — OneOCR ikamesi (kod TAMAM, K1-GATE ÖLÇÜLMEDİ)
- **Tek değişim noktası doğrulandı:** `src/atlas/ocr/kj_ocr.py`'nin `KjOCR` sınıfı hem
  `scan_clip_fast.py` (saat+KJ ROI, TEK motor) hem `jenerik.py`'nin BULMA aşaması (satır 250-251)
  tarafından kullanılıyor → tek sınıfı platform-guard'lamak HER İKİSİNİ de kapsıyor.
  `scan_clip_fast.py`/`jenerik.py` DEĞİŞMEDİ (aynı `read(image_bgr)->list[OcrResult]` sözleşmesi).
- Yeni `src/atlas/ocr/paddle_backend.py` (MITAS'ın kanıtlı `credit_experiment.PaddleOcrEngine`
  deseni uyarlaması): `PP-OCRv5_server_det` + `latin_PP-OCRv5_mobile_rec`, modelscope→torch eager-
  import guard'ı (ocr venv'de torch YOK), GPU/CPU otomatik seçim. ATLAS için (MITAS'tan farklı)
  yerel model-dizini ZORUNLU DEĞİL — paddlex ilk kullanımda otomatik indirir (plan §5.2).
  `kj_ocr.py::_ensure_engine()` artık: `oneocr` dene → başarısızsa (Linux'ta HER ZAMAN) `paddle`ya
  düş (`ATLAS_OCR_ENGINE` env-tohumu, varsayılan `paddle`). `read()` motora göre dallanıyor.
  27+1 patch `py_compile` ile doğrulandı (paddle_backend.py'nin kendisi ocr venv olmadan
  derlenemedi — venv hazır olunca ayrıca doğrulanacak).
- **Gerçek fonksiyonel duman-testi GEÇTİ (ocr venv hazır olunca çalıştırıldı):** sentetik
  "YONETMEN AHMET YILMAZ" görüntüsü `KjOCR().read()` üzerinden (gerçek çağrı yolu, `scan_clip_fast.py`
  ile AYNI) okundu. PaddleOCR modelleri (`PP-OCRv5_server_det` 85MB + `latin_PP-OCRv5_mobile_rec`
  7.9MB) ilk kullanımda gerçekten TAZE indirildi (HF/aistudio/modelscope engellendi → BOS'tan
  indi, plan §5.2 ile uyumlu). **Sonuç: `BACKEND: paddle`, metin BİREBİR doğru okundu, güven
  0.997.** `paddle_backend.py` `py_compile` ile de doğrulandı.
- **KAPI F (K1-GATE) HENÜZ ÖLÇÜLMEDİ:** yukarıdaki duman-testi motorun ÇALIŞTIĞINI kanıtlıyor,
  ama gerçek video ile OneOCR-referans karşılaştırması (saat-çapası doğruluğu, KJ başlık kalitesi)
  Faz H test verisi + Windows tarafında bir referans-koşu gerektiriyor. "En büyük iş kalemi"
  (plan §9-1) — bilinçli olarak bu oturumda TAMAMLANMADI, yalnız kod-altyapısı hazır+kanıtlı.
- Ayrıca (bağımsız bulgu, iş kapsamı dışı ama not edilsin): `kj_ocr.py`'nin OneOCR dalı
  `ONEOCR_DIR = E:\ATLAS\tools\oneocr` sabit yolu KALDI (Windows dalı, dokunulmadı — doğru davranış).

## 🟡 Faz G — Servisler + webui (kısmen doğrulandı)
- `atlas-search.service` (systemd, core venv, `EnvironmentFile=atlas.env`, :8789) — **active**,
  `GET /api/health` → `{"ok": true, "days": []}` HTTP 200 (**gerçek HTTP yanıtı**, "days" boş çünkü
  henüz işlenmiş klip yok — beklenen).
- `atlas-webui.service` (systemd, `node vite.js --host`, :8420) — **active**, ana sayfa HTTP 200
  (**gerçek vite dev-server yanıtı**, React/vite-client injection doğrulandı).
- **Bulgu + düzeltme (yalnız Linux kopyada, E:\ATLAS'a DOKUNULMADI):** `webui/pnpm-workspace.yaml`
  E:\ATLAS'ın KENDİSİNDE ZATEN BOZUK (doğrulandı, salt-okuma) — `allowBuilds` değerleri placeholder
  metin ("set this to true or false") ve zorunlu `packages` alanı YOK; pnpm 9 "packages field
  missing or empty" hatasıyla durdu. `/opt/atlas/webui/pnpm-workspace.yaml` içinde
  `packages: ['.']` + `allowBuilds` gerçek `true` değerleriyle düzeltildi (yalnız Linux kopya).
  **Çağatay'a not: aynı bozukluk E:\ATLAS'ta da var, orada da düzeltme gerekebilir.**
- `pnpm install` ayrıca `--frozen-lockfile` ile `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` verdi (lockfile,
  bozuk pnpm-workspace.yaml'dan önce üretilmiş olabilir) → tek-seferlik bootstrap olduğu için
  `--no-frozen-lockfile` ile devam edildi (pnpm-lock.yaml yalnız Linux kopyada güncellendi).
- **Dokunulmayan açık madde (plan §10-5, talimat gerekir):** `vite.config.ts`'de `/api` MITAS'ın
  :8787'sine proxy'leniyor (ATLAS-WSL'de YOK) — yalnız `/search-api` (→:8789, ATLAS'ın kendi
  search_server'ı) gerçekten çalışıyor. Kod DEĞİŞTİRİLMEDİ.

## 🟡 Faz H — pytest TAMAM, uçtan-uca klip + golden BEKLİYOR
- **`pytest tests/` — İKİ KEZ çalıştırıldı, ikisinde de 676 passed, 8 skipped, 0 failed:**
  1) yalnız `core` venv hazırken (44.84s), 2) TÜM 7 venv hazır olduktan sonra (44.69s) — aynı
  sonuç, sayı DEĞİŞMEDİ (testler ağırlıkla saf-mantık/DB, ağır ML kütüphanelerini import etmiyor).
  Bu güçlü, tekrarlanmış bir sinyal.
- **Uçtan-uca klip testi YAPILMADI (bilinçli, K-A7 kararı bekliyor):** plan §10-2 açıkça
  "Çağatay kararı GEREKLİ" diyor — hangi klip kopyalanacak. Aday belirlendi (salt-okuma
  keşfiyle): `Ornek Video/TRT HABER HD_null2026-06-04T15_00_20.000Z.mp4` (3.39GB) — dosya adındaki
  tarih (2026-06-04) `tests/golden_search_trt0604.json` altın-setinin tarihiyle EŞLEŞİYOR, yani bu
  muhtemelen "trt0604" kaynağı. Kopyalanmadı — onay bekliyor.
- **KAPI H tam değerlendirmesi** (status.json ALL-OK, PDF üretimi, golden-search yeşili) bu klip
  kopyalanıp `process_clip.py` uçtan-uca koşulmadan tamamlanamaz.

## Bu oturumda ÇALIŞTIRILAN 3 systemd servisi (canlı, doğrulanmış)
| Servis | Port | Kanıt |
|---|---|---|
| `atlas-ollama` | 11435 | `ollama list` → 4/4 model; `bge-m3` gerçek embed (1024-d) |
| `atlas-search` | 8789 | `GET /api/health` → `{"ok":true,"days":[]}` HTTP 200 |
| `atlas-webui` | 8420 | anasayfa HTTP 200, gerçek vite/React yanıtı |

## Genel özet (bu oturum sonu)
- **TAMAM+DOĞRULANDI:** Faz A, B, C, D (7/7 venv), E (blob-kopya+bge-m3 gerçek çıkarım),
  F (kod+duman-testi — K1-GATE hariç), G (search+webui servis-seviyesi).
- **BİLİNÇLİ ERTELENEN (Çağatay kararı gerekiyor):** `lab` venv (plan §10-4), Faz H video-seçimi
  (plan §10-2), K1-GATE ölçümü (Faz H verisine bağlı), `/api`→8787 MITAS-proxy kararı (plan §10-5).
- **GPU çekişmesi nedeniyle ertelenen (kurulum kusuru DEĞİL):** `glm-ocr`/`qwen35-35b-test` gerçek
  çıkarım testleri (MITAS'ın Windows-native ollama'sı GPU'nun ~22GB'ını dolduruyor).
- **E:\ATLAS'a HİÇBİR yazma/silme/değişiklik yapılmadı** (yalnız okuma+kopyalama). MITAS-WSL
  dağıtımına dokunulmadı (yalnız referans için salt-okuma sorgular, `wsl -d MITAS`).
