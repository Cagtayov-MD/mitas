# 05 · Kod Değişiklikleri (dosya-dosya, gerçek ikame koduyla)

> Her görev: hangi dosya, ne değişecek, **gerçek ikame kodu**, doğrulama komutu. Placeholder yok.
> Genel ilke: **platform-korumalı** yaz (`sys.platform`) — aynı kod Windows'ta (geçiş fazında
> hâlâ üretim) ve Linux'ta çalışsın. Böylece göç davranış-nötr kalır (Global Kısıt).
>
> **Dal disiplini:** Bu değişiklikler `master`'da doğrudan (proje kuralı: worktree yok). Ama
> göç işi için `linux-port` dalı aç, Faz 0'da orada topla, KAPI 0 geçince master'a al.

---

## Görev 1 — `mitas.env` dosyası (kod DEĞİL, konfigürasyon)

**Dosya:** Oluştur `/opt/mitas/mitas.env` (Faz 0'da `~/mitas/mitas.env`).

Tüm yol env-tohumlarını Linux'a bağla. [02·A1](02_ENVANTER.md) tablosundan türet:

```bash
# /opt/mitas/mitas.env  — systemd EnvironmentFile + `set -a; source mitas.env; set +a`
MITAS_PROJECT_ROOT=/opt/mitas
MITAS_FFMPEG=/usr/bin/ffmpeg
MITAS_FFPROBE=/usr/bin/ffprobe
MITAS_KB_DUCKDB=/data/mitas/MitaData/mitas.duckdb
MITAS_IMDB_DUCKDB=/data/mitas/IMDB/db/imdb.duckdb
MITAS_WIKIDATA_DUCKDB=/data/mitas/MitaData/mitas.duckdb
MITAS_PDFMITAS_DIR=/opt/mitas/OCR-worktree/pdf-mitas
MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR=/opt/mitas/models/ocr/paddle/det
MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR=/opt/mitas/models/ocr/paddle/rec
MITAS_TESSERACT_TESSDATA_DIR=/usr/share/tesseract-ocr/5/tessdata
MITAS_OLLAMA_URL=http://127.0.0.1:11434
MITAS_SERILER_ROOT=/data/mitas/seriler
MITAS_WEB_CACHE_DIR=/opt/mitas/cache/web
MITAS_DUCKDB_CACHE=/opt/mitas/cache/duckdb
MITAS_FLOW_STAGING=/opt/mitas/cache/staging
MITAS_PDF_PYTHON=/opt/mitas/venvs/asr/bin/python
MITAS_JENERIK_PADDLE_MODEL_ROOT=/opt/mitas/models/ocr/paddle/official_models
MITAS_MSFONT_DIR=/usr/share/fonts/truetype/msttcorefonts
# + start_mitas.ps1'deki tüm QC2/perf default'ları (Görev 8) + API anahtarları (ANTHROPIC_/OPENAI_/MITAS_TMDB...)
```

**Doğrulama:** `set -a; source mitas.env; set +a; python -c "import os; print(os.environ['MITAS_PROJECT_ROOT'])"` → `/opt/mitas`.

---

## Görev 2 — asr_server: sabit Python exe yolu

**Dosya:** `core/api/asr_server.py:159-161`

Şu an `MITAS_PDF_PYTHON` tohumu VAR, yalnız default Windows. Kod değişmiyor — Görev 1'de env
verildi. Tek yapılacak: emin ol ki üretimde bu env **her zaman** set (systemd EnvironmentFile).

**Doğrulama:** `python -c "from core.api import asr_server; print(asr_server._KB_CANARY_PY)"` →
Linux python yolu.

---

## Görev 3 — asr_server: NTFS cihaz-kontrolü (`Path("E:\\").stat()`)

**Dosya:** `core/api/asr_server.py:709,714`

`Path(src).drive.upper().startswith("E:")` ve `Path("E:\\").stat().st_dev` Windows-özgü
(sürücü harfi + drive kavramı). Linux'ta staging-prefetch mantığı "kaynak yerel diskte mi"
kontrolüdür. Platform-korumalı yaz:

```python
# 709. satır — yerel-kaynak kontrolü
_stage_dev = _stage_dir.stat().st_dev if _stage_dir.exists() else None
def _is_local_src(p: Path) -> bool:
    try:
        return p.stat().st_dev == _stage_dev  # aynı cihaz = zaten yerel, prefetch anlamsız
    except OSError:
        return False
# ...
if not src or not Path(src).exists() or _is_local_src(Path(src)):
    return
# 714. satır — disk emniyet payı: st_dev karşılaştırması platform-nötr, yalnız Path("E:\\") kalksın
if (_stage_dir.stat().st_dev == Path(src).stat().st_dev
        and shutil.disk_usage(str(_stage_dir)).free < size + 20 * 2**30):
    return
```

**Doğrulama:** ağ-kaynağı simüle eden bir smoke koşusunda prefetch tetiklenir; yerel kaynakta atlanır (log: `staging_prefetch`).

---

## Görev 4 — mitas_pipeline: commit-boş RAM (`GlobalMemoryStatusEx`)

**Dosya:** `scripts/mitas_pipeline.py:2106-2118` (ASR-ön-sübap)

Windows `ctypes.windll.kernel32.GlobalMemoryStatusEx` → Linux `/proc/meminfo`. Platform-korumalı:

```python
import sys as _sys

def _commit_bos_gb():
    """Commit-boş bellek (GB). ASR-ön-sübap large-v3 öncesi bunu bekler."""
    if _sys.platform == "win32":
        import ctypes as _ct
        class _MSX(_ct.Structure):
            _fields_ = ([("dwLength", _ct.c_ulong), ("dwMemoryLoad", _ct.c_ulong)]
                        + [(_n, _ct.c_ulonglong) for _n in
                           ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                            "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                            "ullAvailExtendedVirtual")])
        _m = _MSX(); _m.dwLength = _ct.sizeof(_MSX)
        _ct.windll.kernel32.GlobalMemoryStatusEx(_ct.byref(_m))
        return _m.ullAvailPageFile / 2**30
    # Linux: kullanılabilir fiziksel + boş swap ≈ Windows "available commit"
    vals = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, rest = line.partition(":")
            if k in ("MemAvailable", "SwapFree"):
                vals[k] = int(rest.split()[0])  # kB
    return (vals.get("MemAvailable", 0) + vals.get("SwapFree", 0)) / 2**20  # kB -> GB
```

**Doğrulama:** `python -c "import scripts.mitas_pipeline as m; print(m._commit_bos_gb())"` (fonksiyonu
modül seviyesine taşırsan) veya bir ASR koşusunda `asr_pre_valve` log-event'i commit-boş GB yazar.

---

## Görev 5 — mitas_pipeline: öksüz llama-server temizliği (PowerShell)

**Dosya:** `scripts/mitas_pipeline.py:2362-2368`

Windows PowerShell (ebeveyni ölü `llama-server.exe`'yi öldür) → Linux'ta çok daha basit. Öksüz
süreçler Linux'ta PID 1'e reparent olur; ollama systemd servisi alt-süreçlerini kendi yönetir.
Platform-korumalı:

```python
if _sys.platform == "win32":
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
         "ForEach-Object { if (-not (Get-Process -Id $_.ParentProcessId "
         "-ErrorAction SilentlyContinue)) { Stop-Process -Id $_.ProcessId -Force } }"],
        capture_output=True, timeout=30)
else:
    # Linux: ollama systemd servisi restart edilince alt llama-server'lar temizlenir.
    # Servis-dışı çalışıyorsa öksüz llama-server'ı düşür (guard: yalnız gerçekten öksüzse).
    subprocess.run(["pkill", "-f", "llama[-_]server"], capture_output=True, timeout=30)
```

**Doğrulama:** LLM-preflight-recovery yolu tetiklendiğinde (ollama 404) Linux'ta hata vermeden
geçer; `llm_preflight_recovered` log-event'i yazılır.

---

## Görev 6 — mitas_pipeline: ollama başlatma (`ollama.exe serve`)

**Dosya:** `scripts/mitas_pipeline.py:2372-2374`

Windows `ollama.exe serve` (LOCALAPPDATA) → Linux systemd servisi. Platform-korumalı:

```python
if _sys.platform == "win32":
    _oexe = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    subprocess.Popen([_oexe, "serve"], creationflags=0x08000000)
else:
    # Linux: ollama systemd servisi (bkz. 07). Servis yönetimli başlat.
    subprocess.run(["systemctl", "start", "ollama"], capture_output=True, timeout=30)
```

> Not: `creationflags=0x08000000` (CREATE_NO_WINDOW) Windows-özgü; Linux dalında yok. Kodun
> başka yerlerinde `creationflags=` kullanımı varsa aynı platform-koruması uygulanır (Linux'ta
> `creationflags` parametresi geçersiz → kaldırılır veya `if win32` ile sarılır).

**Doğrulama:** ollama durdurulup pipeline koşulur; ollama-bekçisi Linux'ta `systemctl start ollama`
ile diriltir, `llm_preflight_recovered` yazılır.

---

## Görev 7 — Fontlar (`C:\Windows\Fonts\arial.ttf`)

**Dosyalar:** [02·C](02_ENVANTER.md) listesi (`_prototype_credits_pdf_build.py:89-96`, `compose_*`,
`text_layer_descroll.py:1268`, `ocr_model_healthcheck.py:117-119`, `_info_card.py:15-16`, ...)

**Sistem tarafı:** `apt install ttf-mscorefonts-installer fonts-liberation` → gerçek Arial
`/usr/share/fonts/truetype/msttcorefonts/Arial.ttf`.

**Kod tarafı:** Sabit `C:\Windows\Fonts\arial.ttf` yerine env-tohumlu font-çözücü. Mevcut aday
listelerine Linux yolunu ekle (çoğu zaten `ImageFont.truetype("arial.ttf", ...)` — fontconfig
Linux'ta `arial.ttf`'i mscorefonts'tan bulur, çoğu yerde değişiklik gerekmez). Sabit `r"C:\Windows\Fonts\..."`
yazan yerler (`_info_card.py:15-16`) için:

```python
_FONT_DIR = os.environ.get("MITAS_MSFONT_DIR",
                           r"C:\Windows\Fonts" if _sys.platform == "win32"
                           else "/usr/share/fonts/truetype/msttcorefonts")
FONT  = os.path.join(_FONT_DIR, "Arial.ttf"  if _sys.platform != "win32" else "arial.ttf")
FONTB = os.path.join(_FONT_DIR, "Arial_Bold.ttf" if _sys.platform != "win32" else "arialbd.ttf")
```

**Doğrulama:** Bir künye PNG/PDF üret, çıktıyı Windows üretimiyle görsel karşılaştır (aynı font
metriği). `_prototype_credits_pdf_build` ve gerçek `_pipe_pdf` çıktısı bozulmamalı.

---

## Görev 8 — start_mitas.ps1 → mitas.env + systemd

**Dosya:** `scripts/start_mitas.ps1` (referans) → yeni `mitas.env` + systemd birimleri ([07](07_SERVISLER_SYSTEMD.md))

`start_mitas.ps1:22-107` tüm QC2/perf default'larını `os.environ.setdefault` mantığıyla kuruyor.
Bu default'lar **kodda da ayna** (mitas_pipeline.py:1385-1451 civarı, "start_mitas.ps1 ile BİREBİR"
notu). Yani systemd `EnvironmentFile=mitas.env` bunları yükler, kod aynası korunur. **İş:** ps1'deki
her `$env:MITAS_X = 'Y'` satırını `mitas.env`'e `MITAS_X=Y` olarak taşı (Görev 1 dosyasına ekle).

**Doğrulama:** `07`'deki test — servis ayağa kalkınca `systemctl show mitas-asr | grep MITAS_QC2`
→ `1`. Kod aynası ile ps1 default'ları eşleşiyor (mevcut ayna-testi `tests/test_prod_defaults_ps1_mirror.py`
Linux'ta da geçmeli).

---

## Görev 9 — nvidia-smi yolları (düşük risk)

**Dosya:** `core/api/asr_server.py:1183-1185`

Aday listesi zaten `["nvidia-smi", r"C:\Windows\...", r"C:\Program Files\..."]` — ilk aday PATH'ten
`nvidia-smi`, Linux'ta kendiliğinden bulunur. Değişiklik gerekmez; sadece doğrula:

**Doğrulama:** `python -c "import shutil; print(shutil.which('nvidia-smi'))"` → `/usr/bin/nvidia-smi`.
pynvml zaten platform-nötr; GPU-VRAM izleme Linux'ta çalışır.

---

## Görev 10 — Tesseract yolları

**Dosya:** `core/pipelines/ocr/credit_experiment.py:3619-3675`

Sabit `C:/Program Files/Tesseract-OCR/tesseract.exe` + tessdata → Linux `apt install tesseract-ocr`
sonrası PATH'te. Aday listesine Linux yolları ekle veya `shutil.which("tesseract")` önceliklendir:

```python
_TESS = shutil.which("tesseract") or next(
    (str(p) for p in [
        Path("/usr/bin/tesseract"),
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ] if p.exists()), None)
```
tessdata için `MITAS_TESSERACT_TESSDATA_DIR` (Görev 1'de `/usr/share/tesseract-ocr/5/tessdata`).

**Doğrulama:** `tesseract --version` çalışır; credit_experiment tesseract yolu koşulursa hata vermez.

---

## Görev 11 — `creationflags` / diğer win32-özgü subprocess bayrakları

**Tarama:** `grep -rn "creationflags\|CREATE_NO_WINDOW\|startupinfo\|SW_HIDE" scripts/ core/`

Her birini platform-koru: Windows'ta mevcut bayrak, Linux'ta parametre atlanır. (Linux'ta
`creationflags` geçersiz argüman değil ama etkisizdir; yine de `if _sys.platform == "win32"`
ile ayırmak temiz.)

**Doğrulama:** `pytest tests/` — subprocess başlatan test'ler (asr, pdf) Linux'ta hata vermez.

---

## Öz-denetim (writing-plans self-review)

- **Kapsam:** [02·A2](02_ENVANTER.md) (env-tohumsuz yollar) → G2,3,10; [02·B](02_ENVANTER.md)
  (Win-API) → G4,5,6,11; [02·C](02_ENVANTER.md) (font) → G7; [02·D](02_ENVANTER.md) (servis) → G8 + [07].
- **Placeholder yok:** her görevde gerçek kod + gerçek doğrulama komutu.
- **Tutarlılık:** `_sys = sys` platform-koruması tüm görevlerde aynı desen; `mitas.env` env
  adları [02·A1](02_ENVANTER.md) tablosuyla birebir.
