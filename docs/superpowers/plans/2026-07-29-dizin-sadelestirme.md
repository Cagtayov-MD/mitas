# MITAS Mayın Temizliği + Dizin Sadeleştirme — Uygulama Planı v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repoyu tek bir rutin komutla silinebilir olmaktan çıkarmak — üç mayını TDD ile etkisizleştirmek.

**Architecture:** Üç bağımsız düzeltme, her biri kendi kırmızı testiyle: (1) guard hook `git clean -x` ve `git gc`'yi engeller, (2) ASR kill-switch API yolunda da geçerli olur, (3) `mitas_roots.py` env yokken çapalı repo köküne düşer. **Hiçbir veri taşınmaz**; üçü de geri alınabilir kod değişikliğidir.

**Kapsam:** Dizin taşıması (Blok B) bu planda **değil** — gerekçesi aşağıda. Bu plan tek başına çalışan, test edilebilir bir sonuç üretir: repo artık kazayla silinemez.

**Tech Stack:** Python 3.12 (`venvs/core`), pytest, git, bash, systemd/cron.

## Bu plan v1'in çürütülmesi üzerine yazıldı

53 ajanlık kırmızı-takım turu (2026-07-29) v1'in şu varsayımlarını çürüttü. Aşağıdaki her satır planın bir yerinde karşılık bulur:

| v1 varsayımı | Gerçek | Kanıt |
|---|---|---|
| Kökte 48 giriş | **57** (`ls -A`) | gizli dosyalar sayılmamış |
| 206 G kazanılır | **~38 G anında** (`mv` aynı ext4'te `df`'i değiştirmez) | tüm adaylar `stat -c %d` → 66314 |
| `git prune` risksiz | 2 commit'i (düşürülmüş stash) siler | `git prune --dry-run` |
| `git gc` yapılabilir | **3 benzersiz test dosyasını yok ederdi** | kurtarma dalları açıldı ✓ |
| `parents[1]` yeterli | `.claude/worktrees/musing-aryabhata-1d5189` canlı worktree | `git worktree list` |
| `main` dalındayız | **`jenerik-tek-motor`** | `git branch --show-current` |
| pytest = kapı | `tests/` altında taşınan yollara **0 referans** | `grep -rlIE` |
| `_karantina/` güvenli | `.gitignore:112 /_*` ile ignore → `git clean -fdx` siler | `git check-ignore -v` |
| Ölü venv'lere tek Windows referansı | 8 adayın **5'inde çürütüldü** | `kurulum/`, `linux/` taranmamıştı |

## Global Constraints

- **`git clean -x` / `git clean -X` ASLA.** `git clean -ndx` şu an 1429 giriş listeliyor; içinde `models/` 587 G, `Mitas_Files/` 157 G, `Database/` 119 G, `venvs/` 105 G, `Mitas Output/`, `mitas.env` (API anahtarları) ve `CLAUDE.md` var. Toplam ~1.1 TB, geri dönüşü yok.
- **`git gc` / `git repack` / `git gc --aggressive` ASLA.** 3 packed yetim commit'te başka hiçbir yerde olmayan dosyalar vardı; `kurtarma/e3320e7-regresyon-koruma`, `kurtarma/3ff10b2-golden-veri-kaybi`, `kurtarma/9b7e90d` dalları bu yüzden açıldı. Bu dallar **silinmez**.
- **Silme YASAK.** Yalnız `mv` (untracked için) ve `git mv` (tracked için). Tek istisna: `__pycache__`, `.pytest_cache`, `webui/dist` ve `git prune`. Silme kararı Çağatay'a aittir.
- **Yük taşıyan yollar değişmez.** `scripts/mitas_roots.py` `resolve()`'un döndürdüğü 13 kök taşınmaz.
- **`venvs/` ve `models/` altında `rm`/`-delete` çalıştırma.** `.claude/hooks/mitas_guard.py:96-107` bunları DENY ediyor; komutları `-not -path '*/venvs/*' -not -path '*/models/*'` ile yaz.
- **`mitas.env` Read ile açılmaz** (guard `:87` DENY). Gerekirse `grep -oE '^[A-Z_]+=' /opt/mitas/mitas.env`.
- **`scripts/mitas_roots.py`, `model_manifest.yaml`, `CLAUDE.md`, `MITAS_KUNYE_KURALLARI.md` düzenlenirken guard "ask" üretir** (`mitas_guard.py:44-53`). Görev 3 bu yüzden Çağatay'ın onaylayabileceği bir oturumda yapılır; ajan onayı reddetmemeli.
- **Aktif dal `jenerik-tek-motor`**, `main` değil. İkinci canlı worktree: `.claude/worktrees/musing-aryabhata-1d5189` (`claude/wonderful-vaughan-97d7fe`).
- **mtime'a güvenilmez** (2026-07-16 kopyası sıfırladı). Kanıt = `git log` + kod referansı.
- **Python:** `venvs/core/bin/python`. Testler: `venvs/core/bin/python -m pytest`.
- **Referans tasarım:** `docs/MITAS_Dizin_Sadelestirme_v1.md`.

---

## Dosya Yapısı

| Yol | Sorumluluk | Durum |
|---|---|---|
| `.claude/hooks/mitas_guard.py` | PreToolUse koruması | **Değiştirilecek** (Görev 1) |
| `tests/test_mitas_guard.py` | Guard davranış testleri | **Yeni** (Görev 1) |
| `core/api/asr_server.py` | ASR/özet API'si | **Değiştirilecek** (Görev 2) |
| `tests/test_asr_killswitch.py` | Kill-switch testleri | **Yeni** (Görev 2) |
| `scripts/mitas_roots.py` | Üretim kök çözücüsü | **Değiştirilecek** (Görev 3) |
| `tests/test_mitas_roots.py` | Kök çözücü sözleşmesi | **Değiştirilecek** (Görev 3) |
| `.github/workflows/ci.yml` | CI test listesi | **Değiştirilecek** (Görev 3) |

Blok B'nin dosyaları (`scripts/karantina_tasi.py`, `kurulum/PENCERE_AC.sh`, `HARITA.md` …) bu planda **oluşturulmaz**.

---

# BLOK A — MAYINLAR

## Görev 1: `git clean` / `git gc` mayını — guard hook

**Files:**
- Modify: `.claude/hooks/mitas_guard.py:55-62, 94-108`
- Test: `tests/test_mitas_guard.py` (yeni)

**Interfaces:**
- Consumes: yok
- Produces: `mitas_guard.py` artık `Bash` aracında iki yeni sınıf komut için karar üretir. Hook sözleşmesi değişmez: stdin'den JSON, stdout'a `{"hookSpecificOutput": {...}}`, exit 0.

**Neden ilk:** `git clean -fdx` bugün 1.1 TB siler ve mevcut regex (`\b(rm|rmdir|shred)\b`) onu yakalamaz. Bu plan Kademe 0'da `__pycache__` temizliği yapacak — yani tam olarak `git clean` refleksini tetikleyen işi. Koruma önce gelmeli.

- [ ] **Adım 1: Mevcut açığı test olarak yaz**

Create `tests/test_mitas_guard.py`:

```python
# -*- coding: utf-8 -*-
"""mitas_guard PreToolUse hook testleri.

2026-07-29: git clean -fdx'in 1.1 TB'ı (models/ 587G, Mitas_Files/ 157G,
Database/ 119G, venvs/ 105G, mitas.env) sildiği tespit edildi; mevcut regex
\\b(rm|rmdir|shred)\\b onu yakalamıyordu. Ayrıca git gc/repack, dal ile
kurtarılmış 3 yetim commit'i yok ediyordu."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "mitas_guard.py"


def _cagir(tool, tool_input, cwd="/opt/mitas"):
    girdi = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": cwd})
    p = subprocess.run([sys.executable, str(HOOK)], input=girdi,
                       capture_output=True, text=True, timeout=15)
    assert p.returncode == 0, f"hook exit {p.returncode}: {p.stderr}"
    if not p.stdout.strip():
        return None  # sessiz geçiş = izin
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("cmd", [
    "git clean -fdx",
    "git clean -xdf",
    "cd /opt/mitas && git clean -fdX",
    "git clean --force -d -x",
    "git -C /opt/mitas clean -fdx",
])
def test_git_clean_x_reddedilir(cmd):
    """git clean -x/-X ignore'lu her şeyi siler: models/, Database/, mitas.env dahil."""
    assert _cagir("Bash", {"command": cmd}) == "deny", f"YAKALANMADI: {cmd}"


@pytest.mark.parametrize("cmd", [
    "git gc",
    "git gc --prune=now",
    "git gc --aggressive",
    "git repack -ad",
])
def test_git_gc_reddedilir(cmd):
    """gc/repack, kurtarma/* dallarıyla korunan yetim commit'leri yeniden paketlerken atar."""
    assert _cagir("Bash", {"command": cmd}) == "deny", f"YAKALANMADI: {cmd}"


@pytest.mark.parametrize("cmd", [
    "git clean -nd",
    "git clean -ndx",
    "git clean --dry-run -fdx",
    "git prune --dry-run",
    "git status",
    "git log --oneline -5",
    "ls -la",
])
def test_zararsiz_komutlar_gecer(cmd):
    """Kuru koşu ve okuma komutları engellenmemeli — guard iş akışını kilitlememeli."""
    assert _cagir("Bash", {"command": cmd}) is None, f"YANLIŞ ENGEL: {cmd}"


def test_uretim_kokunde_rm_hala_reddedilir():
    """Mevcut koruma bozulmamalı (regresyon)."""
    assert _cagir("Bash", {"command": "rm -rf /opt/mitas/Database/foo"}) == "deny"


def test_karantina_koku_de_korunur():
    """Taşınan veri kaynağı kadar korunmalı — KARANTINA/arsiv PROD_ROOTS'a girdi."""
    assert _cagir("Bash", {"command": "rm -rf KARANTINA_2026-07-29/venvs"}) == "deny"
    assert _cagir("Bash", {"command": "rm -rf /opt/mitas/arsiv/mutfak"}) == "deny"


def test_kilitli_dosya_ask_uretir():
    """Regresyon: LOCKED davranışı bozulmamalı."""
    assert _cagir("Edit", {"file_path": "/opt/mitas/scripts/mitas_roots.py"}) == "ask"


def test_env_okuma_reddedilir():
    """Regresyon: anahtar sızıntısı koruması bozulmamalı."""
    assert _cagir("Read", {"file_path": "/opt/mitas/mitas.env"}) == "deny"
```

- [ ] **Adım 2: Testi koş — açığın gerçek olduğunu gör**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_guard.py -q
```

Expected: **10 failed, 10 passed.** Patlayanlar: 5 × `test_git_clean_x_reddedilir`, 4 × `test_git_gc_reddedilir`, 1 × `test_karantina_koku_de_korunur`. Hata mesajı `AssertionError: YAKALANMADI: git clean -fdx` biçiminde olmalı — yani hook `None` (izin) döndürüyor.

- [ ] **Adım 3: Guard'ı düzelt**

`.claude/hooks/mitas_guard.py` içinde `PROD_ROOTS` listesine (L55-62) iki satır ekle:

```python
PROD_ROOTS = [
    "/opt/mitas/Database",
    "/opt/mitas/Mitas Output",
    "/opt/mitas/Mitas_Files",
    "/opt/mitas/models",
    "/opt/mitas/venvs",
    "/opt/mitas/testklipler",
    "/opt/mitas/KARANTINA_2026-07-29",
    "/opt/mitas/arsiv",
]
```

Ve `if tool == "Bash":` bloğunu (L94-108) şununla değiştir:

```python
# Tüm ağacı süpüren komutlar: yol eşleşmesi ARAMAZ, cwd'den itibaren her şeyi vururlar.
# git clean -x/-X: .gitignore'lu HER ŞEYİ siler. /opt/mitas'ta bu 1.1 TB demek —
#   models/ 587G, Mitas_Files/ 157G, Database/ 119G, venvs/ 105G, mitas.env, CLAUDE.md.
#   (2026-07-29 ölçümü: `git clean -ndx` 1429 giriş listeliyor.)
# git gc/repack: erişilemez ama BENZERSİZ commit'leri yeniden paketlerken atar.
#   2026-07-29'da 3 yetim commit'te başka hiçbir yerde olmayan test dosyaları bulundu;
#   kurtarma/* dalları o yüzden açıldı. gc bu dallar olmadan onları yok ederdi.
SUPURGE = [
    (re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+clean\b(?=.*(?:-\w*[xX]|--force.*-\w*[xX]))"),
     "git clean -x/-X: .gitignore'lu HER ŞEYİ siler — burada ~1.1 TB "
     "(models/, Mitas_Files/, Database/, venvs/, mitas.env). Kuru koşu için "
     "`git clean -ndx` kullanın."),
    (re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+(?:gc|repack)\b"),
     "git gc/repack: erişilemez ama benzersiz commit'leri yok eder. Bu repoda "
     "kurtarma/* dallarıyla korunan 3 yetim commit var. Gerekiyorsa önce "
     "`git fsck --unreachable` ile inceleyin."),
]

if tool == "Bash":
    cmd = ti.get("command", "") or ""
    kuru = ("--dry-run" in cmd) or re.search(r"\bclean\b[^|;&]*\s-\w*n", cmd)
    if not kuru:
        for desen, mesaj in SUPURGE:
            if desen.search(cmd):
                out("deny", f"🛑 SÜPÜRGE KOMUTU: {mesaj}")
    if re.search(r"\b(rm|rmdir|shred)\b", cmd) or "-delete" in cmd:
        for root in PROD_ROOTS:
            rel = os.path.basename(root)
            hit = (root in cmd
                   or root.replace(" ", "\\ ") in cmd
                   or re.search(rf"""(^|[\s"'=]){re.escape(rel)}/""", cmd))
            if hit:
                out("deny",
                    f"🛑 ÜRETİM VERİSİ KORUMASI: komut '{root}' üzerinde "
                    "silme içeriyor — bu geri getirilemez arşiv/model "
                    "verisine dokunur. Gerçekten gerekiyorsa Çağatay kendi "
                    "terminalinden çalıştırsın.")
    sys.exit(0)
```

Docstring'in başındaki "Uc koruma" listesine dördüncü maddeyi ekle:

```
4. SUPURGE KOMUTU -> "deny": git clean -x/-X ve git gc/repack tum agaci
   vurur; yol eslesmesi aranmaz. Kuru kosu (--dry-run / -n) serbesttir.
```

- [ ] **Adım 4: Testleri koş — hepsi yeşil olmalı**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_guard.py -v
```

Expected: `20 passed`. Özellikle `test_zararsiz_komutlar_gecer[git clean -ndx]` geçmeli — kuru koşuyu engellersek kendi doğrulama adımlarımızı kırarız.

- [ ] **Adım 5: Hook'un canlı çalıştığını doğrula**

Run:
```bash
cd /opt/mitas && echo '{"tool_name":"Bash","tool_input":{"command":"git clean -fdx"},"cwd":"/opt/mitas"}' | python3 .claude/hooks/mitas_guard.py
```

Expected: `permissionDecision` alanı `"deny"` olan bir JSON.

- [ ] **Adım 6: Commit**

```bash
cd /opt/mitas
git add .claude/hooks/mitas_guard.py tests/test_mitas_guard.py
git commit -m "fix(guard): git clean -x ve git gc/repack'i engelle

git clean -fdx bu repoda 1.1 TB siliyordu (models/ 587G, Mitas_Files/ 157G,
Database/ 119G, venvs/ 105G, mitas.env, CLAUDE.md) — mevcut regex
\\b(rm|rmdir|shred)\\b onu yakalamıyordu. git gc/repack ise kurtarma/*
dallarıyla korunan 3 yetim commit'i yok ediyordu.

Kuru koşu (--dry-run / clean -n) serbest bırakıldı; doğrulama adımları
buna bağlı. KARANTINA_2026-07-29 ve arsiv PROD_ROOTS'a eklendi.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 2: ASR kill-switch deliği

**Files:**
- Modify: `core/api/asr_server.py` (yeni yardımcı + 4 giriş noktası: `:1408`, `:2127`, `:2220`, `:2570` civarı)
- Test: `tests/test_asr_killswitch.py` (yeni)

**Interfaces:**
- Consumes: Görev 1'den değişiklik yok.
- Produces: `asr_server.asr_kapali_mi() -> tuple[bool, str]` — `(kapali, sebep)`. Sebep insan-okur metin (`"ASR_KAPALI.flag"` veya `"MITAS_DISABLE_ASR"`), kapalı değilse boş string.

**Kanıt:** `outputs/system_events.jsonl`, 2026-07-29:
```
11:24:36  asr_queued   EK_TAKS.mp4 için ASR kuyruğa alındı.
11:24:36  asr_started  EK_TAKS.mp4 için ASR başladı.
11:25:40  asr_failed   Library libcublas.so.12 is not found
```
Kill-switch'i kontrol eden tek yer `scripts/mitas_pipeline.py:2394`. `asr_server.py` bakmıyor. ASR'yi durduran şey bir kontrol değil, `venvs/asr`'da `libcublas.so.12`'nin **olmaması** — bir kaza. `venvs/alignment`'ta ve ollama'nın cuda dizininde o kütüphane zaten var; `LD_LIBRARY_PATH` düzelirse ASR sessizce koşmaya başlar.

- [ ] **Adım 1: Testi yaz**

Create `tests/test_asr_killswitch.py`:

```python
# -*- coding: utf-8 -*-
"""ASR kalıcı kill-switch (Çağatay 2026-07-11) API yolunda da geçerli olmalı.

2026-07-29 kanıtı: outputs/system_events.jsonl 11:24:36'da asr_queued+asr_started
üretti; ASR_KAPALI.flag diskte duruyordu. Kill-switch'i yalnız
scripts/mitas_pipeline.py:2394 kontrol ediyordu, core/api/asr_server.py hiç bakmıyordu."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.api import asr_server  # noqa: E402


def test_flag_dosyasi_varsa_kapali(tmp_path, monkeypatch):
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    (tmp_path / "ASR_KAPALI.flag").write_text("test")
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is True
    assert "ASR_KAPALI.flag" in sebep


def test_flag_yoksa_ve_env_yoksa_acik(tmp_path, monkeypatch):
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is False
    assert sebep == ""


@pytest.mark.parametrize("deger", ["1", "true", "TRUE", "on", "yes", " 1 "])
def test_env_degiskeni_kapatir(tmp_path, monkeypatch, deger):
    """mitas_pipeline.py:2395-2396 ile BİREBİR aynı kabul listesi."""
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("MITAS_DISABLE_ASR", deger)
    kapali, sebep = asr_server.asr_kapali_mi()
    assert kapali is True
    assert "MITAS_DISABLE_ASR" in sebep


@pytest.mark.parametrize("deger", ["0", "false", "off", "no", ""])
def test_env_degiskeni_yanlis_degerde_kapatmaz(tmp_path, monkeypatch, deger):
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("MITAS_DISABLE_ASR", deger)
    kapali, _ = asr_server.asr_kapali_mi()
    assert kapali is False


def test_pipeline_ile_ayni_mantik(tmp_path, monkeypatch):
    """Regresyon kilidi: iki kill-switch uygulaması ayrışmamalı.

    mitas_pipeline.py:2394-2396 mantığı burada birebir tekrarlanıyor; ikisi
    ayrışırsa bu test patlar."""
    monkeypatch.setattr(asr_server, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
    for flag_var, env_deger, beklenen in [
        (False, None, False),
        (True, None, True),
        (False, "1", True),
        (True, "0", True),
    ]:
        bayrak = tmp_path / "ASR_KAPALI.flag"
        if flag_var:
            bayrak.write_text("x")
        elif bayrak.exists():
            bayrak.unlink()
        if env_deger is None:
            monkeypatch.delenv("MITAS_DISABLE_ASR", raising=False)
        else:
            monkeypatch.setenv("MITAS_DISABLE_ASR", env_deger)
        assert asr_server.asr_kapali_mi()[0] is beklenen, (flag_var, env_deger)


def test_gercek_repo_kokunde_flag_duruyor():
    """Çağatay'ın 2026-07-11 talimatı hâlâ yürürlükte — dosya silinmemiş olmalı."""
    kok = Path(__file__).resolve().parents[1]
    assert (kok / "ASR_KAPALI.flag").exists(), (
        "ASR_KAPALI.flag silinmiş. Bilinçli bir karar ise bu testi de kaldırın.")
```

- [ ] **Adım 2: Testi koş — patlamasını gör**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_asr_killswitch.py -q
```

Expected: `AttributeError: module 'core.api.asr_server' has no attribute 'asr_kapali_mi'` — **14 failed, 1 passed** (geçen tek test `test_gercek_repo_kokunde_flag_duruyor`).

Not: `asr_server.py` ağır importlar içerir. `ImportError` alırsan `venvs/asr/bin/python` ile koş ve bunu adımda not et.

- [ ] **Adım 3: `asr_kapali_mi()` yardımcısını ekle**

`core/api/asr_server.py` içinde, `PROJECT_ROOT` tanımından hemen sonra ekle:

```python
def asr_kapali_mi() -> tuple[bool, str]:
    """ASR kalıcı kill-switch (Çağatay 2026-07-11) — API yolu için.

    scripts/mitas_pipeline.py:2394-2396 ile BİREBİR aynı mantık. 2026-07-29'a
    kadar bu kontrol yalnız pipeline'da vardı; API/webui yükleme yolu flag'e
    hiç bakmıyordu ve 2026-07-29 11:24'te ASR'yi gerçekten başlattı
    (outputs/system_events.jsonl: asr_queued -> asr_started -> asr_failed).
    """
    if (PROJECT_ROOT / "ASR_KAPALI.flag").exists():
        return True, "ASR_KAPALI.flag"
    if os.environ.get("MITAS_DISABLE_ASR", "").strip().lower() in ("1", "true", "on", "yes"):
        return True, "MITAS_DISABLE_ASR"
    return False, ""
```

- [ ] **Adım 4: Dört giriş noktasına kapıyı koy**

`core/api/asr_server.py:1408` `create_asr_job`, `:2127` `reprocess_clip_asr`, `:2220` `process_clip_asr_range` ve `:2570` civarındaki `asr_started` üreticisinin **her birinin gövdesinin ilk satırına** şunu ekle:

```python
    _kapali, _sebep = asr_kapali_mi()
    if _kapali:
        raise HTTPException(
            status_code=409,
            detail=f"ASR kalıcı devre dışı ({_sebep}) — Çağatay 2026-07-11 talimatı. "
                   f"Açmak için: {PROJECT_ROOT / 'ASR_KAPALI.flag'} dosyasını silin.")
```

`HTTPException` zaten import edilmiş olmalı; değilse `from fastapi import HTTPException` ekle.

Kesin satır numaraları için önce şunu koş:
```bash
cd /opt/mitas && grep -n "^async def create_asr_job\|^def reprocess_clip_asr\|^def process_clip_asr_range\|\"asr_started\"" core/api/asr_server.py
```

- [ ] **Adım 5: Testleri koş**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_asr_killswitch.py -v
```

Expected: `15 passed`.

- [ ] **Adım 6: Servisi yeniden başlat ve canlı doğrula**

Run:
```bash
sudo systemctl restart mitas-asr.service && sleep 5
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8787/api/asr/transcribe -H 'Content-Type: application/json' -d '{}'
```

Expected: `409` (veya kimlik doğrulama varsa `401`/`403` — o durumda `journalctl -u mitas-asr -n 20` ile `ASR kalıcı devre dışı` satırını ara).

- [ ] **Adım 7: Commit**

```bash
cd /opt/mitas
git add core/api/asr_server.py tests/test_asr_killswitch.py
git commit -m "fix(asr): kill-switch'i API yoluna da uygula

ASR_KAPALI.flag'i yalnız scripts/mitas_pipeline.py:2394 kontrol ediyordu.
core/api/asr_server.py (webui yükleme yolu) flag'e hiç bakmıyordu ve
2026-07-29 11:24'te ASR'yi gerçekten başlattı — onu durduran şey bir kontrol
değil, venvs/asr'da libcublas.so.12'nin olmamasıydı (kaza). Çağatay'ın
2026-07-11 talimatı 18 gündür yarım uygulanıyordu.

asr_kapali_mi() pipeline'daki mantığı birebir tekrarlar; test_pipeline_ile_ayni_mantik
iki uygulamanın ayrışmasını yakalar.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 3: `mitas_roots.py` kök sebebi (çapa desenli)

**Files:**
- Modify: `scripts/mitas_roots.py:27-29` — **guard "ask" üretir, onay gerekir**
- Modify: `tests/test_mitas_roots.py:19-42`
- Modify: `.github/workflows/ci.yml:92` civarı

**Interfaces:**
- Consumes: Görev 1-2'den değişiklik yok.
- Produces: `mitas_roots.PROJECT_ROOT` env yokken `/opt/mitas` döner (worktree'den çağrılsa bile). `resolve()`, `resolve_production()`, `validate_candidate_run_root()`, `is_candidate()`, `export_child_env()` **imzaları değişmez**.

**Naif fix neden yanlış:** `.claude/worktrees/musing-aryabhata-1d5189/scripts/mitas_roots.py` **canlı** (`git worktree list`) ve o worktree'de `Database/`, `Mitas Output/`, `models/`, `venvs/` **yok**. `Path(__file__).parents[1]` orayı PROJECT_ROOT yapar → pipeline boş ağaca yazar. Çapa aramak zorunlu.

**Çapa seçimi:** `normalize.py` `models/asr/faster-whisper` kullanıyor ama `mitas_roots` ASR'den bağımsız bir modül — ASR modeline bağlı çapa mantıksal olarak yanlış ve model klasörü taşınınca kök çözümü sessizce değişir. `Database` + `model_manifest.yaml` ikilisi kullanılacak.

**Bilinçli davranış değişikliği:** env yokken `validate_candidate_run_root()` bugün `/opt/mitas/candidate_runs/*` için **her zaman** `RootSafetyError` atıyor (çünkü `CANDIDATE_ROOT` = `E:\MITAS/candidate_runs`). Fix sonrası kabul edecek. `scripts/promote_hub.py:267` bunu candidate→üretim terfi kapısı olarak kullanıyor: "hiçbir şey terfi edemez"den "terfi çalışır"a geçiyoruz. Adım 8 bunu ayrıca doğrular.

- [ ] **Adım 1: Mevcut kırmızı testi gör**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_roots.py -q
```

Expected: `1 failed, 7 passed`, hata:
```
AssertionError: DB_ROOT: E:\MITAS/Database != E:\MITAS\Database
```
Bu test Linux'ta yapısal olarak geçemez ve CI onu koşmuyor (`ci.yml:92` listesinde yok) — 2026-07-16'dan beri kırmızı.

- [ ] **Adım 2: Testleri yeniden yaz**

`tests/test_mitas_roots.py` içindeki `URETIM_BEKLENEN` (L19-33) ve `test_uretim_yollari_byte_ayni` (L36-42) yerine:

```python
URETIM_BEKLENEN_GORELI = {
    "DB_ROOT": "Database",
    "OUT_ROOT": "Mitas Output",
    "EXPORT_ROOT": "Mitas Output/export",
    "HAZIR": "Mitas Output/export/ONAYLI",
    "KONTROL": "Mitas Output/export/KONTROL",
    "SPECIAL_GENRE_DIR": "Mitas Output/muzikal_animasyon_belgesel",
    "EVENTS_PATH": "outputs/system_events.jsonl",
    "MASTER_MD": "Mitas Output/export/_ISLEM_LOG.md",
    "MASTER_JSONL": "Mitas Output/export/_ISLEM_LOG.jsonl",
    "MANIFEST_DIR": "outputs/manifests",
    "OUTPUTS_DIR": "outputs",
    "WEB_CACHE_DIR": "cache/web",
    "AFIS_CACHE_DIR": "_102_afis_cache",
}


def test_uretim_yollari_project_root_altinda(monkeypatch):
    """MITAS_RUN_ROOT boş → 13 yazma kökü PROJECT_ROOT altında, göreli yapı korunur."""
    monkeypatch.delenv("MITAS_RUN_ROOT", raising=False)
    r = mitas_roots.resolve()
    assert r["RUN_ROOT"] is None
    kok = r["PROJECT_ROOT"]
    for k, goreli in URETIM_BEKLENEN_GORELI.items():
        assert r[k] == kok / goreli, f"{k}: {r[k]} != {kok / goreli}"


def test_env_yokken_repo_kokune_duser(monkeypatch):
    """KÖK SEBEP: env yoksa Windows sabitine değil, çapalı repo köküne düşülür."""
    import importlib
    monkeypatch.delenv("MITAS_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("MITAS_RUN_ROOT", raising=False)
    yeniden = importlib.reload(mitas_roots)
    try:
        kok = yeniden.PROJECT_ROOT
        assert "E:" not in str(kok), f"Windows sabitine düştü: {kok}"
        assert "\\" not in str(kok), f"Yolda backslash var: {kok}"
        assert kok.is_absolute(), f"Mutlak yol değil: {kok}"
        assert (kok / "Database").is_dir(), f"Çapa yok, yanlış kök: {kok}"
        assert (kok / "model_manifest.yaml").is_file(), f"Çapa yok, yanlış kök: {kok}"
    finally:
        importlib.reload(yeniden)


def test_env_varsa_env_kazanir(monkeypatch, tmp_path):
    """Sözleşme: MITAS_PROJECT_ROOT set ise o kazanır (systemd bu yolu kullanıyor)."""
    import importlib
    monkeypatch.setenv("MITAS_PROJECT_ROOT", f"  {tmp_path}  ")  # .strip() denetimi
    monkeypatch.delenv("MITAS_RUN_ROOT", raising=False)
    yeniden = importlib.reload(mitas_roots)
    try:
        assert yeniden.PROJECT_ROOT == tmp_path
        assert yeniden.resolve()["DB_ROOT"] == tmp_path / "Database"
    finally:
        monkeypatch.delenv("MITAS_PROJECT_ROOT", raising=False)
        importlib.reload(yeniden)


def test_worktree_kopyasi_ana_agaca_cozer(monkeypatch, tmp_path):
    """WORKTREE TUZAĞI: çapasız bir ağaçtaki kopya kendi köküne düşmemeli.

    .claude/worktrees/musing-aryabhata-1d5189 canlı bir worktree ve orada
    Database/ yok. Naif parents[1] o ağacı PROJECT_ROOT yapar → pipeline
    boş ağaca yazar."""
    sahte_worktree = tmp_path / "repo" / ".claude" / "worktrees" / "wt1" / "scripts"
    sahte_worktree.mkdir(parents=True)
    (tmp_path / "repo" / "Database").mkdir(parents=True)
    (tmp_path / "repo" / "model_manifest.yaml").write_text("x")
    monkeypatch.delenv("MITAS_PROJECT_ROOT", raising=False)
    bulunan = mitas_roots._cozumle_proje_koku(sahte_worktree / "mitas_roots.py")
    assert bulunan == tmp_path / "repo", f"worktree'ye takıldı: {bulunan}"
```

- [ ] **Adım 3: Testleri koş — doğru sebeple patlasın**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_roots.py -q
```

Expected: `test_env_yokken_repo_kokune_duser` FAILS (`Windows sabitine düştü: E:\MITAS`) ve `test_worktree_kopyasi_ana_agaca_cozer` FAILS (`AttributeError: _cozumle_proje_koku`).

- [ ] **Adım 4: `mitas_roots.py`'yi düzelt (guard "ask" üretecek — onaylayın)**

L27-29'u şununla değiştir:

```python
# Çapalar: bunların İKİSİ birden bulunan dizin gerçek proje köküdür. Tek çapa yetmez —
# .claude/worktrees/* altındaki canlı worktree'lerde ikisi de yoktur, dolayısıyla
# oradan çağrıldığında da ana ağaca tırmanılır.
_CAPALAR = ("Database", "model_manifest.yaml")


def _cozumle_proje_koku(kaynak_dosya=None) -> Path:
    """Proje kökünü çöz. Test edilebilirlik için kaynak dosya dışarıdan verilebilir.

    2026-07-29 kök-sebep düzeltmesi: env yoksa eskiden Windows sabiti r"E:\\MITAS"e
    düşülüyordu. Linux'ta ':' ve '\\' geçerli dosya-adı karakteri olduğu için bu,
    cwd altında 'E:\\MITAS' adlı GERÇEK bir dizin yaratıyordu (2026-07-28 kanıtı:
    63 event oraya yazılmış) ve daha ciddisi ASR_KAPALI.flag kontrolünü
    (mitas_pipeline.py:2394) görünmez yapıyordu.

    Naif Path(__file__).parents[1] KULLANILMAZ: .claude/worktrees/* altındaki
    canlı worktree'de Database/ ve venvs/ yoktur; naif çözüm pipeline'ı boş
    ağaca yazdırır. Bu yüzden çapa arayarak yukarı tırmanılır.
    """
    configured = os.environ.get("MITAS_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured)

    baslangic = Path(kaynak_dosya or __file__).resolve().parent
    for aday in (baslangic, *baslangic.parents):
        if all((aday / c).exists() for c in _CAPALAR):
            return aday
    # Çapa bulunamadı (temiz checkout / CI): scripts/ -> repo kökü
    return Path(kaynak_dosya or __file__).resolve().parents[1]


PROJECT_ROOT = _cozumle_proje_koku()
CANDIDATE_ROOT = PROJECT_ROOT / "candidate_runs"
```

- [ ] **Adım 5: Testleri koş**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_roots.py -v
```

Expected: `11 passed`. `test_candidate_*` ve `test_reparse_point_*` hâlâ geçmeli — `CANDIDATE_ROOT` türetmesi değişmedi.

- [ ] **Adım 6: Bağımlı testler**

Run:
```bash
cd /opt/mitas && venvs/core/bin/python -m pytest tests/test_mitas_roots.py tests/test_kontrol_worklist.py tests/test_promote_hub.py -q
```

Expected: hepsi PASS, toplam sayı fix öncesi baseline'dan az olmamalı.

- [ ] **Adım 7: Worktree kopyasından doğrula (kritik)**

Run:
```bash
cd /tmp && env -u MITAS_PROJECT_ROOT -u MITAS_RUN_ROOT /opt/mitas/venvs/core/bin/python -c "
import sys; sys.path.insert(0, '/opt/mitas/.claude/worktrees/musing-aryabhata-1d5189/scripts')
import mitas_roots as m
print('worktree kopyasi ->', m.PROJECT_ROOT)
"
```

Expected: `worktree kopyasi -> /opt/mitas`

Worktree'nin kendi yolunu yazdırırsa fix yanlış — çapa mantığını düzelt, devam etme.

- [ ] **Adım 8: Terfi kapısı davranış değişikliğini doğrula**

Run:
```bash
cd /opt/mitas && env -u MITAS_PROJECT_ROOT -u MITAS_RUN_ROOT venvs/core/bin/python -c "
import sys; sys.path.insert(0, 'scripts')
import mitas_roots as m
print('CANDIDATE_ROOT =', m.CANDIDATE_ROOT)
try:
    print('kunye51 kabul ->', m.validate_candidate_run_root('/opt/mitas/candidate_runs/kunye51_20260714'))
except Exception as e:
    print('RED:', e)
for kotu in ('/opt/mitas', '/opt/mitas/candidate_runs'):
    try:
        m.validate_candidate_run_root(kotu); print('HATA: kabul etmemeliydi', kotu)
    except m.RootSafetyError:
        print('dogru red ->', kotu)
"
```

Expected:
```
CANDIDATE_ROOT = /opt/mitas/candidate_runs
kunye51 kabul -> /opt/mitas/candidate_runs/kunye51_20260714
dogru red -> /opt/mitas
dogru red -> /opt/mitas/candidate_runs
```

- [ ] **Adım 9: `E:\MITAS/` artığını taşı (fix'ten SONRA)**

Run:
```bash
cd /opt/mitas && mv -n -- 'E:\MITAS' /tmp/claude-1000/-opt-mitas/e_mitas_artigi_20260729 && ls -d 'E:\MITAS' 2>&1
```

Expected: `ls: 'E:\MITAS' erişilemiyor` — artık yok.

Sonra 10 dakika bekleyip (cron `*/5` iki kez koşsun) tekrar kontrol et:
```bash
cd /opt/mitas && ls -d 'E:\MITAS' 2>&1
```
Expected: hâlâ yok. Geri geldiyse kök sebep kapanmamış — Adım 4'e dön.

- [ ] **Adım 10: CI'ya eksik testleri ekle**

`.github/workflows/ci.yml`'de `python -m pytest \` listesine ekle:

```yaml
            tests/test_mitas_roots.py \
            tests/test_mitas_guard.py \
            tests/test_asr_killswitch.py \
```

- [ ] **Adım 11: Commit**

```bash
cd /opt/mitas
git add scripts/mitas_roots.py tests/test_mitas_roots.py .github/workflows/ci.yml
git commit -m "fix(roots): env yokken çapalı repo köküne düş (Windows sabiti kaldırıldı)

mitas_roots.py:28 MITAS_PROJECT_ROOT yoksa r'E:\\MITAS'e düşüyordu. Linux'ta
':' ve '\\\\' geçerli dosya-adı karakteri olduğu için cwd altında 'E:\\MITAS'
adlı gerçek dizin yaratıyordu (2026-07-28: 63 event oraya yazılmış) ve
ASR_KAPALI.flag kontrolünü görünmez yapıyordu.

Naif parents[1] KULLANILMADI: .claude/worktrees/musing-aryabhata-1d5189 canlı
bir worktree ve orada Database/ yok — naif çözüm pipeline'ı boş ağaca yazdırırdı.
Database + model_manifest.yaml çapalarıyla yukarı tırmanılıyor.

BİLİNÇLİ DAVRANIŞ DEĞİŞİKLİĞİ: env yokken validate_candidate_run_root() artık
/opt/mitas/candidate_runs/* için çalışıyor (eskiden her zaman RootSafetyError).
promote_hub.py:267 terfi kapısı bundan etkilenir; Adım 8 ile doğrulandı.

test_mitas_roots.py 2026-07-16'dan beri kırmızıydı ve CI onu koşmuyordu;
guard ve killswitch testleriyle birlikte CI listesine eklendi.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

---

# BLOK B — TEMİZLİK (ayrı plan)

Blok B bu plana **dahil değildir**; Blok A yeşillendikten sonra kendi planına
(`docs/superpowers/plans/<tarih>-karantina-tasimasi.md`) yazılacaktır.

**Neden ayrıldı:** Blok B'nin en kritik doğrulama adımı — "`E:\MITAS/` 10 dakika
cron sonrası geri geldi mi" (Görev 3 Adım 9) — Blok A'nın **çıktısıdır**. Geri
gelirse kök sebep kapanmamış demektir ve taşıma yapılmamalıdır. Ayrıca Blok B'nin
kapıları (`13_surum_denetimi.py --strict`) henüz var olmayan bir bayrağa dayanıyor.
Bir planın adımı, henüz alınmamış bir sonuca bağlıysa o adım plana yazılamaz.

Aşağıdakiler Blok B planının **girdileridir** — bu turda kanıtlandı, kaybolmasın:

### Çağatay'ın 2026-07-29 kapsam kararı

Kapandığı onaylanan: `models/QwenOmni` (49 G) · ollama `qwen36-35b-test` +
`qwen36-27b-test` + `mistral-small3.2` (54 G) · eski candidate koşuları (~18 G).
**Kapanmadığı bildirilen:** 5 itirazlı venv (`internvl`, `minicpmv`, `vlm`,
`denoise`, `ina`) — bunlar yerinde kalır.

### Kanıtı tartışmasız kalemler (3/3 mercek temiz)

| Kalem | Boyut | Kanıt |
|---|---|---|
| `venvs/nemo` | 6.2 G | RECORD sha256 denetimi: 75.240 kayıtlı yol, **0 kayıtsız dosya, 0 mismatch**; model ağırlığı yok; reçete `linux/reqs_linux/nemo.txt` (`nemo-toolkit==2.7.3`) |
| `venvs/tts` + `models/tts` | 5.6 G | kod ve manifest'te sıfır referans |
| `venvs/locateanything` | 5.2 G | manifest'te hiç geçmiyor; tek referans Windows-yollu probe |
| `hf-cache/` | 2.3 M | boş kabuk; gerçek cache `models/hf_cache` (`HF_HOME`) |

### Blok B'nin uyması gereken kısıtlar

1. **Hedef dizin `KARANTINA_2026-07-29/`, `_karantina/` DEĞİL.** `.gitignore:112`
   `/_*` kuralı `_` ile başlayan kök girişlerini ignore ediyor; ignore edilen dizin
   `git clean -x` kapsamına girer. `git check-ignore -v KARANTINA_2026-07-29/`
   çıktı vermemeli.
2. **`GERI_AL.sh` satırları `printf 'mv -n -- %q %q\n'` ile üretilir.** Git bu yolu
   `"E:\\MITAS/"` diye çift backslash'la yazıyor; `%q` olmadan geri alma sessizce
   yanlış hedefe yazar. `-n` ve `--` zorunlu.
3. **Tracked içerik `git mv` ile taşınır.** `git ls-files` sayımı: `mutfak` 68,
   `model2` 7, `requirements` 7. Düz `mv` ile taşınırsa taşıma–commit arası
   pencerede `git clean -fd` (x'siz, çok yaygın) onları siler.
4. **`vllm_bench_20260718/claude_gt/` TAŞINMAZ** — 31 film, 313 dilim elle
   yargılanmış altın standart. Aynı şekilde `kunye51_20260714` (harness canlı
   baseline'ı), `test_debug`, `test_frame_vs_master`.
5. **`linux/` ARŞİVE GİTMEZ — canlı kod.** `kurulum/02_build_venv.sh:13`
   `REQ="$KOK/linux/reqs/$AD.txt"` ve `:16` `YENI_REQS="$KOK/linux/reqs_linux"`
   okuyor/yazıyor; venv'lerin yeniden kurulabilirliğinin tek reçetesi orada —
   yani karantinanın "geri alınabilir" savunmasının dayanağı.
6. **Kapı pytest DEĞİL.** `tests/` altında taşınacak yollara **0 referans** var;
   pytest taşımadan sonra da aynen yeşil kalır. Gerçek kapılar:
   `kurulum/13_surum_denetimi.py` çıktısının önce/sonra diff'i (önce `--strict`
   bayrağı eklenmeli — `:27-28` istisnayı yutup `{}` döndürüyor),
   `harness/master_run.sh` roster'ında `ollama show` SKIP sayısı (`:46` sessizce
   atlıyor), `benchmark_templates/asr_gold_probe_benchmark.yaml` içindeki 6
   `source_path` varlık kontrolü.
7. **Bakım penceresi zorunlu:** 4 cron işi (`*/5`, `*/5`, `*/7`, `*/10`) ve
   `mitas-hub-yedek.timer` (günlük 06:30) durdurulmadan taşıma yapılmaz.
8. **`arsiv/` içeriği:** `mutfak/`, `backups/`, `linux_backup_wsl2_20260714/`,
   `Logolar/`, `requirements/`, `model2/`.
9. **`HARITA.md` 57 girişi kapsar** (`ls -A`), 49'u değil — `.claude/`, `linux/`,
   `models/`, `venvs/`, `mitas.env` dahil.
10. **`git prune --expire=now` kullanılır, `git gc` ASLA.** Düşürülmüş stash
    yedeği alındı: `scratchpad/dusurulmus_stash_2026-07-23.patch`.

---

## Başarı ölçütü (Blok A)

| Ölçüt | Hedef | Nasıl ölçülür |
|---|---|---|
| `git clean -fdx` engelleniyor | DENY | `tests/test_mitas_guard.py` 20 passed + canlı hook çağrısı (Görev 1 Adım 5) |
| `git clean -ndx` hâlâ serbest | izin | `test_zararsiz_komutlar_gecer[git clean -ndx]` |
| ASR kill-switch API'de geçerli | 409 | `tests/test_asr_killswitch.py` 15 passed + canlı `curl` (Görev 2 Adım 6) |
| İki kill-switch uygulaması ayrışmıyor | — | `test_pipeline_ile_ayni_mantik` |
| Env'siz kök doğru çözülüyor | `/opt/mitas` | Görev 3 Adım 7 (worktree kopyasından) |
| Terfi kapısı çalışıyor | kabul + 2 doğru red | Görev 3 Adım 8 |
| `E:\MITAS/` yok ve geri gelmiyor | yok | Görev 3 Adım 9 (10 dk cron sonrası tekrar bakılır) |
| `kurtarma/*` dalları duruyor | 3 satır | `git branch --list 'kurtarma/*'` |
| Üretim davranışı değişmemiş | — | `venvs/core/bin/python -m pytest tests/ -q` fix öncesi baseline'dan az geçmiyor; 3 systemd servisi `active (running)` |
| CI körlüğü kapandı | — | `ci.yml`'de 3 yeni test dosyası listeli |

**Bu planda disk kazancı hedefi YOKTUR.** Üç düzeltme de kod değişikliğidir; `df` değişmez. Disk işi Blok B planına aittir.

## Kapsam dışı (ayrı iş)

- `models/lid/...ecapa/*.ckpt` kırık symlink (hedef `C:/Users/TRT03/...`) → dil tespiti fiilen çalışmıyor
- `core/api/asr_server.py:736` `Path("E:\\").stat()` → prefetch Linux'ta sessizce hiç çalışmıyor
- `kurulum/26_kapanis_pdf.py:26` `KOK = Path("/opt/mitas")` hardcode → candidate izolasyonunu deliyor
- `venvs/asr`'da `libcublas.so.12` eksik → ASR'yi durduran şu anki fiili sebep. **Düzeltilmeden önce Görev 2 tamamlanmalı**, yoksa ASR sessizce açılır
- `scripts/` altında ~70 referanssız `.py`; `core/` içinde 14 M referanssız logo PNG'si; `outputs/` kökünde 66 tek-kullanımlık betik
- Kademe 4: `filmtest/` 66 G, `testklipler/` 9 G, `Mitas_Files/` 157 G, `models/hf_cache` VLM havuzu ~296 G
