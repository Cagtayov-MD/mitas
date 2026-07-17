# 06 · Venv Kurulumu (18 profil, Python 3.10.11)

> En büyük emek kalemi. 18 venv, hepsi Python 3.10.11. Merkezi `requirements.txt` YOK (ad-hoc
> kuruldular). Strateji: **Windows'ta reçete dondur → Linux'ta 3.10.11 ile kur → duman-test.**

**Profiller:** `alignment, asr, audio, core, denoise, face, ina, internvl, locateanything,
minicpmv, nemo, ocr, stt, tag, translate, tts, visual, vlm`

---

## Adım 1 — Windows'ta reçeteleri dondur (ŞİMDİ yapılabilir)

Her venv'in tam paket listesini çıkar. Windows'tayken (kaynak makine):

```powershell
# E:\MITAS içinde, her venv için pip freeze
foreach ($v in Get-ChildItem E:\MITAS\venvs -Directory) {
  & "$($v.FullName)\Scripts\python.exe" -m pip freeze |
    Out-File -Encoding utf8 "E:\MITAS\linux\reqs\$($v.Name).txt"
}
```

Çıktı: `E:\MITAS\linux\reqs\<profil>.txt` (18 dosya). **Bu dosyalar göç için kritik yedek** —
Faz 0 ve Faz 2'de kurulum kaynağı. (Reçeteler bu klasörde dursun; git'e ekle.)

> **Not:** Bazı paketler Windows-özgü wheel taşır (ör. `pywin32`, bazı `*-win_amd64` wheel'leri).
> Linux'ta bunları reçeteden çıkar/atla — Linux muadili pip'ten gelir. `oneocr` paketi Linux'ta
> YOK (K1 ile zaten kalkıyor, [08](08_ONEOCR_IKAME.md)).

---

## Adım 2 — Linux'ta venv iskeleti

```bash
cd /opt/mitas            # Faz 0'da ~/mitas
pyenv local 3.10.11      # bu dizinde 3.10.11 kilitli
mkdir -p venvs
for p in core ocr asr; do            # ÖNCELİK sırası: önce bu üçü
  python -m venv venvs/$p
done
```

**Öncelik gerekçesi:** `core` (pipeline çekirdeği), `ocr` (künye — OneOCR ikamesi burada),
`asr` (servis + transkripsiyon) golden-regresyonun çekirdeği. Bu üçü yeşil olmadan diğerlerine
geçme. Kalan 15 profil (face, visual, vlm, nemo, tts, ...) sonra, kullanım sırasına göre.

---

## Adım 3 — Kurulum (profil-bazlı, GPU dikkatli)

### torch/CUDA (asr, ocr, vlm, nemo, face, visual, internvl, minicpmv, ...)

RTX 3090 için CUDA 12.x wheel. Reçetedeki torch sürümünü koru (parite), CUDA index'ten al:

```bash
source venvs/asr/bin/activate
pip install --upgrade pip
# torch'u reçetedeki SÜRÜMLE, Linux CUDA wheel'inden:
pip install torch==<reçete-sürümü> --index-url https://download.pytorch.org/whl/cu124
# kalan paketler reçeteden (torch satırını çıkararak):
grep -v -iE '^(torch|torchvision|torchaudio|pywin32|oneocr)' linux/reqs/asr.txt > /tmp/asr_lin.txt
pip install -r /tmp/asr_lin.txt
deactivate
```

Aynı kalıbı her GPU-profili için tekrarla. **CPU-only profiller** (translate, tag bazıları)
CUDA index'e gerek duymaz.

### Özel dikkat gereken paketler

| Paket | Linux notu |
|---|---|
| `oneocr` | Linux'ta YOK — reçeteden çıkar; ikame [08](08_ONEOCR_IKAME.md) |
| `pywin32` / `win32*` | Windows-özgü — Linux'ta atla |
| `paddlepaddle-gpu` | Linux CUDA wheel'i ayrı; PaddleOCR modelleri `/opt/mitas/models/ocr/paddle` |
| `flash-attn`, `xformers` | Linux'ta birinci-sınıf (Windows'ta eziyetti) — sorunsuz kurulur |
| `vllm` | Linux'ta yerel (WSL'de zaten kurulu: 0.22.1) |
| `nemo_toolkit` | Linux'ta daha stabil; ffmpeg/sox sistem paketleri gerekir |
| `faster-whisper` / `ctranslate2` | CUDA runtime uyumu — reçete sürümünü koru |
| `pyannote.audio` | HF token gerekir (env); model cache `/data/mitas/models/hf_cache` |

---

## Adım 4 — Duman testi (profil-bazlı)

Her profil kurulunca, o profilin çekirdek import'unu ve varsa smoke-test'ini koştur:

```bash
# core/ocr/asr için mevcut smoke altyapısı:
source venvs/core/bin/activate
python scripts/run_model_smoke_tests.py        # model duman testleri
python -m pytest tests/ -k "not real_media" -q  # OS-bağımsız test'ler
deactivate
```

Profil-özgü hızlı import kontrolleri:

```bash
# asr
venvs/asr/bin/python -c "import torch, faster_whisper; print(torch.cuda.is_available())"  # True
# ocr
venvs/ocr/bin/python -c "import paddle; from paddleocr import PaddleOCR; print('ok')"
# vlm
venvs/vlm/bin/python -c "import torch, transformers; print(transformers.__version__)"
```

**Kapı:** `torch.cuda.is_available()` her GPU-profilinde `True`; import'lar hatasız; smoke test'ler
Windows'takiyle aynı sonuç.

---

## Adım 5 — HF cache + model yerleşimi

D diskini doldurmamak için model'ler veri diskinde:

```bash
export HF_HOME=/data/mitas/models/hf_cache      # mitas.env'e ekle
export HF_HUB_TOKEN=<token>                       # pyannote vb. için
# ollama modelleri:
export OLLAMA_MODELS=/data/mitas/models/ollama    # 07'de systemd env
```

Ollama modellerini yeniden çek (Windows'tan kopyalamak yerine temiz çek, format uyumu için):

```bash
ollama pull gemma3:27b      # veya üretimdeki tam etiket (mitas_pipeline model adına bak)
# üretimde kullanılan tüm modeller — start_mitas.ps1/mitas_pipeline'daki model adlarından liste çıkar
```

---

## Öz-denetim

- 18 profil listelendi; öncelik core→ocr→asr net.
- `oneocr`/`pywin32` Linux'ta çıkarılıyor — [08](08_ONEOCR_IKAME.md) ve [02·E2](02_ENVANTER.md) ile tutarlı.
- torch CUDA wheel + reçete-sürüm paritesi (davranış-nötr göç ilkesi).
- Model'ler veri diskinde ([03](03_DONANIM_DISK_KURULUM.md) boyut-kuralıyla tutarlı).
