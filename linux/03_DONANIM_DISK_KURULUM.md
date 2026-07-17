# 03 · Donanım, Disk ve Sistem Kurulumu

> Yeni PC'de fiziksel kurulum planı. Diskler, dağıtım, bölümleme, GPU/CUDA, NTFS mount,
> dizin düzeni. Ölçülen mevcut durum tarih: 2026-07-10.

---

## Mevcut donanım (kaynak makine, ölçülen)

| Disk | Model | Boyut | Windows sürücü | Doluluk |
|---|---|---|---|---|
| 0 | Samsung 980 PRO 500GB | 466 GB | **C:** (Windows sistem) | %96 dolu (19 GB boş) |
| 1 | Samsung 980 PRO 500GB | 466 GB | **D:** ("Yeni Birim") | %83 dolu (79 GB boş, ~387 GB veri) |
| 2 | Samsung 970 EVO Plus 2TB | 1863 GB | **E:** (`E:\MITAS`) | %97 dolu (60 GB boş) |
| 3 | Samsung 970 EVO Plus 2TB | 1863 GB | **F:** (WSL + boşluk) | %72 dolu (528 GB boş) |

- **GPU:** NVIDIA RTX 3090 24 GB, sürücü 560.94 (WSL'den `nvidia-smi` görüyor → CUDA hazır).
- **RAM:** bol (proje kuralı: E:\MITAS'ta bellek endişesi yok).

> **"Yeni PC"** farklı donanımsa: aşağıdaki disk-rol atamasını kendi disklerine uyarla, mantık
> aynı — bir disk Linux OS+programlar, bir disk Windows rollback, büyük diskler veri.

---

## Disk rol ataması (hedef)

| Disk | Rol (geçiş fazı) | Rol (Faz 4 sonrası) |
|---|---|---|
| **0 (C, Windows)** | **DOKUNULMAZ** — rollback ağı | Faz 4'te emekli / cold spare |
| **1 (D, 466 GB)** | **Linux OS + programlar** (kök, venv, kod) | aynı |
| **2 (E, 2TB)** | NTFS mount → `/data/mitas` (veri, RO/RW) | ext4'e çevrilir |
| **3 (F, 2TB)** | NTFS mount → `/data/mitas2` + WSL barınağı | ext4'e çevrilir |

### D diskini hazırlama (KRİTİK — veri kaybı riski)

D'de ~387 GB veri var. Linux kurmadan önce:

1. **D'nin içeriğini yedekle.** Nereye: F'nin boşuna (528 GB var) VEYA harici disk. **E'ye ASLA
   koyma** (%97 dolu). İçeriğin ne olduğunu önce listele — silme yasağı geçerli, onaylanmadan
   hiçbir şey silinmez.
2. Yedek doğrulandıktan sonra D formatlanacak (Linux kurulumu sırasında).

> Bu adım **fiziksel ve geri-alınamaz** — Kontrol Listesi'nde ([10](10_KONTROL_LISTESI.md))
> ayrı bir onay kapısı olarak işaretli.

### Boyut kontrolü — 466 GB yeter mi?

- Linux kök (`/`): ~30 GB
- 18 venv (torch/CUDA/vLLM/paddle/nemo yığınları): ~150-250 GB
- Kod + `.git`: ~birkaç GB
- **Model ağırlıkları ve HF cache → D'ye DEĞİL, veri diskine** (aşağıda symlink)

**Kural:** D = OS + venv + kod. Ağır model'ler (ollama modelleri, HF hub cache, Paddle/VLM
ağırlıkları) mount'lu 2TB diske alınır. Bu düzenle 466 GB rahat.

---

## Dağıtım ve temel sistem

- **Dağıtım:** Ubuntu 24.04 LTS (WSL'deki `Ubuntu-MITAS` ile aynı; en iyi CUDA/ML desteği).
- **Python 3.10.11:** Ubuntu 24.04 varsayılanı 3.12 → **pyenv** ile 3.10.11 kur (venv paritesi için).
  ```bash
  curl https://pyenv.run | bash
  pyenv install 3.10.11
  pyenv global 3.10.11   # veya proje-yerel
  ```
- **GPU sürücü + CUDA:**
  ```bash
  sudo ubuntu-drivers autoinstall          # NVIDIA 560+ sürücü
  # CUDA toolkit: torch kendi CUDA runtime'ını wheel ile getirir (12.x); ayrı toolkit ops.
  nvidia-smi                                # doğrula: RTX 3090, 24576 MiB
  ```
- **Sistem paketleri:**
  ```bash
  sudo apt update && sudo apt install -y \
    ffmpeg tesseract-ocr tesseract-ocr-tur \
    build-essential git curl \
    ttf-mscorefonts-installer fonts-liberation \
    ntfs-3g
  ```

---

## Dizin düzeni (hedef)

```
/opt/mitas/                 # KOD (git repo; MITAS_PROJECT_ROOT)
├── scripts/  core/  tests/  webui/  OCR-worktree/
├── venvs/                  # 18 venv (D diskinde)
├── cache/                  # staging, web, duckdb (D)
└── mitas.env              # tüm MITAS_/ANTHROPIC_/OPENAI_ env (systemd EnvironmentFile)

/data/mitas/                # E diski mount (veri)
├── Database/               # üretim künye verisi
├── outputs/                # koşu çıktıları
├── MitaData/  IMDB/        # DuckDB'ler (KB/IMDB/Wikidata)
└── models/                 # ağır model ağırlıkları (HF cache buraya symlink)

/data/mitas2/               # F diski mount (ek veri / seriler / yedek)
```

### NTFS mount (geçiş fazı — veri TAŞINMAZ)

E ve F NTFS kalır, `ntfs3` çekirdek sürücüsüyle okunur/yazılır. `/etc/fstab`:

```
# UUID'leri `sudo blkid` ile al
UUID=<E-diski>  /data/mitas   ntfs3  defaults,uid=1000,gid=1000,windows_names  0 0
UUID=<F-diski>  /data/mitas2  ntfs3  defaults,uid=1000,gid=1000,windows_names  0 0
```

> **Performans notu:** NTFS mount, ext4'ten yavaştır (özellikle binlerce frame-PNG'lik havuz
> I/O'sunda). Bu geçiş-fazı çözümü; asıl hız Faz 4'te ext4'e çevrilince gelir. Hız ölçümünü
> Faz 4 öncesi/sonrası karşılaştır (bkz. [09](09_DOGRULAMA_GERI_DONUS.md)).

### HF cache + model symlink (D'yi doldurmamak için)

```bash
mkdir -p /data/mitas/models/hf_cache /data/mitas/models/ollama
ln -s /data/mitas/models/hf_cache  ~/.cache/huggingface
# ollama modelleri: OLLAMA_MODELS=/data/mitas/models/ollama (systemd env)
```

---

## Boot stratejisi (ayrı-disk, dual-boot DEĞİL)

- Windows disk 0'da kendi EFI'siyle; Linux disk 1'e kendi EFI'siyle kurulur.
- **GRUB'un Windows bootloader'ına dokunmasına izin verme** — Linux kurulumunda bootloader'ı
  D diskinin kendi EFI bölümüne yaz.
- OS seçimi: boot'ta UEFI boot-menüsü (genelde F8/F11/F12) → hangi diske boot edeceğini seç.
- **Geri-dönüş:** Linux sorun çıkarırsa boot menüsünden Windows disk'ini seç, hiçbir şey kaybolmaz.
