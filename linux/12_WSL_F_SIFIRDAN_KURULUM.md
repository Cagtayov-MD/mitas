# 12 · F Diskinde Sıfırdan İzole MITAS (WSL/Ubuntu) — Uygulama Planı

> **Çağatay talimatı (2026):** F diskinde, WSL/Ubuntu üstünde, **sıfırdan tamamen izole bir MITAS.**
> Kendi kodu, kendi venv'leri, **tüm modelleri yeniden indirilmiş**, tüm bağımlılıkları F'de.
> **C/D/E'den runtime'da hiçbir şey kullanmaz.** Windows/orijinal MITAS'a dokunulmaz. vLLM de kurulup denenir.
> **ÖNCE PLAN (bu belge) → onay → UYGULAMA.**

**F durumu (ölçüldü):** 1863 GB, **1862 GB boş** (tertemiz). Bol yer var.
**GPU:** RTX 3090 24 GB, WSL'den erişilebilir (doğrulandı).

---

## Önce 4 dürüst not (talimatınla çelişmez ama netleşmeli)

1. **WSL, Windows'un bir özelliğidir.** MITAS'ın kendisi F'de tam izole olur (kod+venv+model hepsi
   WSL-içi Linux dosya sisteminde, F'de). AMA WSL'i *çalıştıran* alt katman Windows'tur — bu, uzaktan
   çalışabilmemizin sebebi. "Windows'a dokunma" = **senin üretim MITAS'ına ve C/D/E verisine
   dokunulmaz**; ama Linux'u barındıran görünmez Windows katmanı kalır (zaten konuştuğumuz gibi).

2. **Kod tek seferlik "tohum" olarak kopyalanır.** F'deki MITAS'ın kodu bir yerden gelmeli. Onu
   Windows'taki `E:\MITAS`'tan **bir kez** kopyalarım (git). Ondan sonra F'deki kopya **bağımsızdır** —
   runtime'da asla C/D/E okumaz. Yani "tohum" tek seferlik bootstrap, sürekli bağ değil.

3. **OneOCR Linux'ta ÇALIŞAMAZ** (Windows-only). "Tüm bağımlılıklar F'de" derken OneOCR istisna:
   yerine **Paddle/GLM-OCR** konur (K1 kararı, [08](08_ONEOCR_IKAME.md)). F-MITAS OneOCR'sız çalışır.

4. **Çalıştırıp test etmek için VERİ lazım.** F-MITAS C/D/E okumayacaksa, işleyeceği filmleri +
   KB DuckDB'lerini (kimlik doğrulama) **F'ye bir kez kopyalamamız** gerekir — yoksa işleyecek
   bir şeyi olmaz. Bu da "tüm bağımlılıklar F'de"nin parçası (tek seferlik kopya, sonra bağımsız).

---

## UYGULAMA İLERLEMESİ (2026-07-12, otonom kurulum — canlı)

Bu bölüm yarın gerçek Linux geçişinde kullanılacak KANIT kaydı. WSL dağıtımı: `MITAS` (F:\wsl\MITAS).

- ✅ **Faz A:** WSL Ubuntu 24.04 F'de, GPU RTX 3090 görünür, systemd v255 aktif.
- ✅ **Faz B:** apt paketleri + pyenv Python 3.10.11 (pyenv PATH sorunu→mutlak-yol).
- ✅ **Faz C:** kod `git archive HEAD` ile /opt/mitas'a (28GB .git kopyalanmadı, temiz); mitas.env yerleşti.
- ✅ **Faz D:** 18/18 venv. Kanıtlanmış desen: **paddle(Paddle-index)→reqs(opencv-tek headless + Win-özel strip)→torch SON(cu126, nccl fix)→import-check**. Çözülen: torch cu126, paddle 3.3.1 Paddle-index, 3-opencv→tek headless (gapi-bug), tensorflow-intel strip, ina/nemo pin-gevşetme, asr legacy-resolver. Explicit-doğrulanmış: ocr(paddleocr+cv2), asr(faster_whisper), nemo, ina.
- ✅ **Faz E:** ollama (tgz `.tar.zst`'ten elle + systemd root servis, OLLAMA_MODELS→F). 5 üretim modeli: glm-ocr/gemma4:26b/gemma-4-31b-vision (E:\OllamaModels'tan blob-kopya) + qwen2.5vl:7b/qwen3:8b (taze pull). qwen3:8b inference **100% GPU** doğrulandı.
- ✅ **HF (vLLM için):** Qwen2.5-VL-7B-Instruct + Qwen3-8B (32GB, HF_HOME=/opt/mitas/models/hf_cache).
- ⚠️ **Faz F (vLLM): ERTELENDİ — sürücü kısıtı.** vLLM 0.25.0 ve 0.22.1 wheel'lerinin ikisi de torch **cu130 (CUDA 13.0)** getiriyor; WSL'in kullandığı Windows NVIDIA sürücüsü **560.94 = CUDA 12.6 max** → "driver too old (12060)", CUDA kernel çalışmıyor. **Kök-neden net.** ÇÖZÜM: (a) **bare-metal Linux'ta taze sürücü (580+) kur → vLLM çalışır** (yarın gerçek geçişte doğal); (b) VEYA Windows host NVIDIA sürücüsünü 580+'a güncelle (üretimi etkiler, senin kararın). HF Qwen modelleri (Qwen2.5-VL-7B + Qwen3-8B) indirilmiş, sürücü çözülünce hazır. **Not:** ollama cu126 kullandığı için ÇALIŞIYOR; vLLM cu130 istediği için çalışmıyor — baseline ollama ile ayakta.

  **DENENDİ (2026-07-12, torch-cu126 swap) — 2 BLOKER teşhis edildi:**
  1. **vLLM `_C` uzantısı CUDA 13'e derli** — torch'u cu126'ya çevirmek `import vllm`'i geçirir (lazy) ama gerçek kullanımda `ImportError: libcudart.so.13`. vLLM wheel'i cu13-built; cu13-lib sağlansa bile sürücü 12.6 cu13-kernel'i çalıştırırken reddeder. Tek çare: cu126-derli (çok eski, kısıtlı) vLLM VEYA sürücü 580+.
  2. **GPU Windows üretim-ollama'sında (~22/24 GB)** — WSL-ollama durdurulsa bile yer açılmıyor (Windows tarafı; dokunulmadı). vLLM çalışsa bile OOM.
  **Sonuç:** sürücü güncellemesi bile Bloker 2'yi çözmez + uzaktan reboot üretim-riski. **vLLM'in doğru yeri bare-metal (taze 580+ sürücü + paylaşılmayan GPU) → yarın orada sorunsuz.**

  **GÜNCELLEME (sürücü 610.62'ye güncellendi, GPU boş): torch cu130 KERNEL ÇALIŞIYOR ✅ (Bloker 1+2 çözüldü) — AMA vLLM yine açılmadı: `RuntimeError: UVA is not available`.** 4 workaround (stdin→dosya, VLLM_USE_V1=0, VLLM_ENABLE_V1_MULTIPROCESSING=0) hepsi aynı. **UVA (Unified Virtual Addressing) WSL2'nin GPU-sanallaştırmasında YOK — sürücüden BAĞIMSIZ WSL2 çekirdek sınırı.** → **vLLM WSL2'de ÇALIŞMAZ; yalnız bare-metal'de (gerçek Linux, sanallaştırma yok).** DERS: sürücü güncellemesi bu blokeri çözemezdi — model-yükleme WSL'de önce test edilmeliydi. WSL2'de model sunumu = ollama (çalışıyor). vLLM bare-metal enhancement'ı olarak kalır.
- 🟡 **Faz G (OneOCR ikame): Paddle-jenerik yolu DOĞRULANDI, GLM-oku promote kaldı.**
  - Paddle modelleri E:'den F'ye kopyalandı (100M: PP-OCRv5_server_det + latin/en_mobile_rec), mitas.env yolları düzeltildi.
  - `_pipe_ocr.py:build_engine()` **platform-guard'landı**: Windows=OneOCR, Linux/oneocr-yok=`_PaddleReadEngine` adapter (recognize_pil→PaddleOcrEngine), `MITAS_JENERIK_OCR_ENGINE=paddle`. (patch_build_engine.py, /opt/mitas kopyasında — E: üretime dokunulmadı.)
  - `paddlex[ocr]` 3.5.1 kuruldu (paddleocr 3.x hard bağımlılığı, frozen reqs'te yoktu). **Gerçek test: Paddle sentetik metni birebir okudu ('YONETMEN AHMET YILMAZ').**
  - İzolasyon doğrulandı: F kodu F'den import (CWD=/opt/mitas iken; systemd WorkingDirectory ile üretimde garanti).
  - opencv: paddlex[ocr] `opencv-contrib-python 4.10.0.84`'e hard-bağımlı (çalışıyor); `headless 5.0.0.93` atıl-zararsız (yarın golden'da teyit).
  - **GLM-OCR okuma DOĞRULANDI:** glm-ocr:latest sentetik metni okudu ('YONETMEN AHMET YILMAZ', 15s GPU). Paddle-jenerik + GLM-oku **iki rol de F'de gerçekten çalışıyor.**
  - **opencv TEMİZ (gereksiz süreç temizlendi):** üç-opencv→iki→**tek `opencv-contrib-python 5.0.0.93`** (gapi-bug yok, paddlex-name kabul, +libGL). Redundancy sıfır.
  - `MITAS_JENERIK_OCR_ENGINE=paddle` mitas.env'de. **KALAN (golden-zamanı ayar):** ham-OCR-oku default'unda GLM-consensus (MITAS_OCR_GLM_CONSENSUS) açık mı + pipeline100 Linux davranışı — yarın golden'da netleşir (davranış-değişikliği, ölçülü).
- ⬜ **Faz H:** pipeline smoke/golden (test verisi F'ye yarın, "sıfırdan koşacağız").

**Tüm kurulum scriptleri:** `/opt/mitas/linux/setup/` (build_venv3.sh, fix_conflicts.sh, ollama_install3.sh, ...) — yarın bare-metal'de tekrar kullanılabilir.

---

## Faz A — WSL/Ubuntu'yu F'ye kur

1. Eski `Ubuntu-MITAS` kaydını temizle (F boşaldı, vhdx'i gitmiş olabilir — kayıt bayat).
2. Ubuntu 24.04 rootfs indir → **vhdx'i F'de** olacak şekilde içe aktar:
   ```
   wsl --import MITAS-F  F:\wsl\mitas-f  <ubuntu-24.04-rootfs.tar.gz>  --version 2
   ```
   Böylece tüm Linux dosya sistemi F'de büyür (C'yi doldurmaz).
3. systemd'yi aç (`/etc/wsl.conf` → `[boot] systemd=true`), `wsl --shutdown` + yeniden gir.
4. GPU doğrula: `nvidia-smi` → RTX 3090, 24576 MiB.

**Kapı A:** WSL F'de açılıyor, systemd aktif, GPU görünüyor.

---

## Faz B — Sistem paketleri + Python

5. `apt install`: ffmpeg, tesseract-ocr(+tur), build-essential, git, curl, mscorefonts, ntfs-3g,
   pyenv bağımlılıkları.
6. pyenv + **Python 3.10.11** (venv paritesi).

**Kapı B:** `python --version` = 3.10.11, ffmpeg/tesseract çalışıyor.

---

## Faz C — Kod (tek seferlik tohum → bağımsız)

7. `E:\MITAS` kodunu WSL-içi `/opt/mitas`'a **bir kez** kopyala (git; venv/outputs/model/Database HARİÇ).
8. Linux kod fix'lerini uygula ([05](05_KOD_DEGISIKLIKLERI.md) — platform-koruma: meminfo, pkill,
   systemctl, font, tesseract yolları).
9. `mitas.env`'i yerleştir ([mitas.env](mitas.env)) — tüm yollar **F-içi Linux** yollarına
   (`/opt/mitas`, `/data/mitas`).

**Kapı C:** Kod F'de, yollar F'yi gösteriyor, C/D/E referansı yok.

---

## Faz D — venv'ler (18 profil, F-içi)

10. pyenv 3.10.11 ile 18 venv, `linux/reqs/*.txt`'ten ([06](06_VENV_KURULUM.md)); oneocr/pywin32
    çıkarılır, torch CUDA-index'ten. Öncelik: core → ocr → asr.

**Kapı D:** `torch.cuda.is_available()` = True; core/ocr/asr import temiz.

---

## Faz E — TÜM MODELLERİ F'ye YENİDEN İNDİR (bağımsız)

> Hiçbiri D'deki/C'deki kopyalara bağlı olmaz — hepsi F-içi, sıfırdan çekilir. **Büyük indirme
> (~yüzlerce GB, saatler).** ollama modelleri F-içi `OLLAMA_MODELS`'e, HF modelleri F-içi `HF_HOME`'a.

11. **ollama** (Linux, systemd) kur; `OLLAMA_MODELS=/data/mitas/models/ollama` (F-içi). Üretim modelleri çek:
    | Model | Rol |
    |---|---|
    | `glm-ocr:latest` | gölge-VL / OCR okuyucu (bench kazananı) |
    | `gemma-4-31b-it-qat-vision:latest` | vision (run_manifest) |
    | `qwen2.5vl:7b` | VL sınıflandırıcı/okuyucu (ana) |
    | `qwen3vl:8b` | dilim-VL default |
    | `gemma4:26b` | video-künye okuma |
    | `qwen3:8b`, `gemma3:12b` | metin (isim/özet) |
    | (test) `qwen3-vl:8b`, `qwen3-vl:30b`, `minicpm-v:latest`, `llama3.2-vision:11b` | VL adayları |

12. **HF modelleri** (venv'ler için, F-içi `HF_HOME`):
    - `faster-whisper large-v3` (ASR)
    - `pyannote/speaker-diarization-3.1` (diyarizasyon — HF token gerekir)
    - `speechbrain/lang-id-voxlingua107-ecapa` (dil-ID)
    - `InternVL3-8B` (internvl venv)
    - Paddle OCR det/rec modelleri
13. Modelleri doğrula (her biri yükleniyor mu, tek örnek).

**Kapı E:** Tüm üretim modelleri F-içi, C/D/E'deki hiçbir kopyaya bağlı değil.

---

## Faz F — vLLM (Qwen VL video, deneme)

14. `vllm` venv (WSL'de zaten kurulmuştu; F'de temiz kur).
15. **Qwen3-VL / Qwen-Omni HF formatında F-içi indir** (D'deki GGUF DEĞİL — vLLM HF ister).
16. vLLM ile Qwen3-VL sun, **gerçek video girişini** test et ([08 notu](08_ONEOCR_IKAME.md) + qwen-vl
    video). Ölç: kare-kare (ollama) vs video-native (vLLM) — kayan jenerikte fark var mı?

**Kapı F:** vLLM Qwen3-VL video girişini kabul ediyor; A/B ölçümü alındı (varsayım değil, ölçüm).

---

## Faz G — OneOCR ikamesi (F-MITAS OneOCR'sız)

17. ham-OCR yolunu Paddle/GLM'e bağla (`MITAS_OCR_ENGINE`), [08](08_ONEOCR_IKAME.md). K1-GATE ölçümü.

**Kapı G:** F-MITAS OneOCR olmadan künye okuyor; golden'da ikame ≥ referans.

---

## Faz H — Test verisi + golden (F izole çalışıyor kanıtı)

18. **Tek seferlik veri kopyası** F'ye: KB DuckDB'leri (`mitas.duckdb`, `imdb.duckdb`) + birkaç test filmi.
19. systemd servisleri (asr, tedial) [07](07_SERVISLER_SYSTEMD.md).
20. 3-5 film uçtan uca koştur; künye/cast/PDF üret; golden ile karşılaştır ([09](09_DOGRULAMA_GERI_DONUS.md)).

**Kapı H (BİTİŞ):** F-MITAS tamamen izole (C/D/E'ye runtime bağı yok), film işliyor, golden yeşil,
vLLM Qwen video denemesi ölçüldü.

---

## Süre / kaynak beklentisi (dürüst)

- **En uzun kalemler:** 18 venv (GB'larca) + TÜM modeller yeniden indirme (yüzlerce GB) → **saatler,
  iyi internet.** Adım adım ilerler, her fazın kapısında dururuz.
- **F'ye sığar mı:** OS+venv (~250GB) + modeller (~300-500GB) + test verisi → 1862 GB'da rahat.

## Çağatay kararları (2026 — ONAYLI, uygulama başladı)

1. **Kod tohumu:** `E:\MITAS`'tan tek-seferlik kopya. **GitHub'a KONULMAYACAK** (şimdilik).
2. **Model kapsamı:** **SADECE üretimde kullanılanlar.** Deneysel (`outputs/` A/B modelleri) YOK.
   vLLM için gerekli model AYRI çekilir (o istisna). Fazladan/harici bir şey indirilmez.
3. **Test verisi:** F'ye KOPYALANMAYACAK — **olduğu yerde kalır, sıfırdan koşacağız** (yarın Linux
   geçişinde). Yani Faz H'de veri-kopyası adımı ELENDİ; izole-çalışma kanıtı gerçek geçişte alınır.
4. **Amaç:** Bu kurulum **yarın gerçek Linux geçişinde kullanılacak** → TEMİZ, tekrarlanabilir iş.
