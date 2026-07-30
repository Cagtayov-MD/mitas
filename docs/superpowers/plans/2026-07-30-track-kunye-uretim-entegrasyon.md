# track_kunye Üretim Entegrasyonu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MESSİ+deepseek+RONALDO zincirini mitas_pipeline'ın karar-sonrası gölge bölgesine bağla: film başına 3 çıktı (messi/ibra-okuma/ronaldo-mix), event'ler, hub yüzeyi ve batch doğrulayıcı.

**Architecture:** Yeni `scripts/_pipe_track_kunye.py` alt-süreci, mitas_pipeline'ın MASTER-PNG bloğundan hemen sonra (LEGACY GÖLGE VL'den önce) video_vl deseninde fail-safe çağrılır; runaware çıkış master'ını SALT-OKUR tüketir, `clip_dir/track_kunye/` + kökte `<ad> kunye3.txt` üretir. Karar/PDF/teslim/reasons'a dokunulmaz.

**Tech Stack:** Python 3.12 (`/opt/mitas/venvs/ocr/bin/python`), cv2, Ollama (deepseek-ocr), duckdb, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md` — sapma görürsen DUR, SAPMA raporu ver.
- Test komutu HER ZAMAN: `/opt/mitas/venvs/ocr/bin/python -m pytest <dosya> -q` (sistem python'u DEĞİL).
- DOKUNULMAZ BÖLGE: `OCR-worktree/master_png_monitor.py`, `harness/master_dup/ibrahimovic.py`, `OCR-worktree/db_compose_master.py`, `scripts/mitas_pipeline.py` 4061-4118 MASTER-PNG bloğu, `scripts/_jenerik_dense.py`. Bunlara TEK SATIR dokunma.
- `OCR-worktree/py/uret_ex.py` ASLA stage edilmez (Çağatay'ın commit'lenmemiş deneyi).
- Testlerde GPU/model çağrısı YASAK — pilot_hat fonksiyonları monkeypatch'lenir.
- Kod stili: mevcut dosyalardaki gibi Türkçe fonksiyon adları/yorumlar; yorum yalnız kodun gösteremediği kısıtı söyler.
- Commit mesajı Türkçe, `git commit -F <dosya>` ile (tırnak güvenliği); sonunda: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- `_pipe_track_kunye.py` HER durumda exit 0 döner (fail-safe gölge sözleşmesi); durum son-satır JSON ile bildirilir.

---

### Task 1: pilot_hat üretim uyarlamaları

**Files:**
- Modify: `harness/track_kunye/pilot_hat.py`
- Test: `harness/track_kunye/test_pilot_hat_uretim.py` (yeni)

**Interfaces:**
- Produces: `havuz_derle_dizin(kare_dizin: Path, desen: str = "*.png") -> tuple[list[Path], dict]` (istatistik dönüşte; dict anahtarları: kare, esik, grup, alarm, sayfa, ikinci_gecis_ek — boş dizinde {"kare": 0, "sayfa": 0}); `oku_deepseek(sayfalar, cagri_timeout: int = 900)`; `oku_master(master_png, out_dir, bant_h=1100, bindirme=120, cagri_timeout: int = 900)`; modül sabitleri `OLLAMA` (MITAS_OLLAMA_URL env'li) ve `KB_DUCKDB` (MITAS_KB_DUCKDB env'li). Task 2 bunları kullanır.
- Consumes: mevcut `messi.havuz_derle/ikinci_gecis`, `ronaldo.capraz`.

- [ ] **Step 1: Failing testleri yaz**

`harness/track_kunye/test_pilot_hat_uretim.py` (yeni dosya, tamamı):

```python
"""pilot_hat üretim uyarlamaları: env-aware yollar + dizin-parametreli havuz."""
import importlib
import os
import sys
from pathlib import Path

import numpy as np
import cv2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _yeniden_yukle():
    import pilot_hat
    return importlib.reload(pilot_hat)


def test_ollama_url_env_ile_degisir(monkeypatch):
    monkeypatch.setenv("MITAS_OLLAMA_URL", "http://ornek:9999")
    ph = _yeniden_yukle()
    assert ph.OLLAMA == "http://ornek:9999/api/generate"
    monkeypatch.delenv("MITAS_OLLAMA_URL")
    ph = _yeniden_yukle()
    assert ph.OLLAMA == "http://127.0.0.1:11434/api/generate"


def test_kb_yolu_env_ile_degisir(monkeypatch):
    monkeypatch.setenv("MITAS_KB_DUCKDB", "/tmp/olmayan.duckdb")
    ph = _yeniden_yukle()
    assert ph.KB_DUCKDB == "/tmp/olmayan.duckdb"


def test_havuz_derle_dizin_istatistigi_donusте(tmp_path):
    ph = _yeniden_yukle()
    # 6 sentetik kare: 3 farklı "sayfa" (içerikli, std>=3), aralarda tekrar
    rng = np.random.default_rng(7)
    desenler = [rng.integers(0, 255, (120, 160), dtype=np.uint8) for _ in range(3)]
    sira = [0, 0, 1, 1, 2, 2]
    for i, d in enumerate(sira):
        cv2.imwrite(str(tmp_path / f"c_{i:04d}.png"), desenler[d])
    secim, ist = ph.havuz_derle_dizin(tmp_path, "*.png")
    assert isinstance(secim, list) and isinstance(ist, dict)
    assert ist["kare"] == 6
    assert ist["sayfa"] >= 1
    assert all(p.parent == tmp_path for p in secim)


def test_havuz_derle_dizin_bos_dizin(tmp_path):
    ph = _yeniden_yukle()
    secim, ist = ph.havuz_derle_dizin(tmp_path, "*.png")
    assert secim == []
    assert ist == {"kare": 0, "sayfa": 0}


def test_havuz_derle_eski_imza_calisiyor(tmp_path, monkeypatch):
    # geriye-uyum: havuz_derle(slug) EX kökünden okur ve SON_HAVUZ_ISTATISTIK doldurur
    ph = _yeniden_yukle()
    monkeypatch.setattr(ph, "EX", tmp_path)
    kok = tmp_path / "deneme-exit_frames"
    kok.mkdir()
    rng = np.random.default_rng(3)
    for i in range(3):
        cv2.imwrite(str(kok / f"exit_{i:06d}.png"),
                    rng.integers(0, 255, (100, 140), dtype=np.uint8))
    secim = ph.havuz_derle("deneme")
    assert isinstance(secim, list)
    assert ph.SON_HAVUZ_ISTATISTIK.get("sayfa") is not None


def test_oku_deepseek_cagri_timeout_parametresi(monkeypatch, tmp_path):
    ph = _yeniden_yukle()
    gorulen = {}
    def sahte_iste(model, prompt, imgs=None, num_predict=2048, num_ctx=8192, timeout=900):
        gorulen["timeout"] = timeout
        return "SATIR BIR"
    monkeypatch.setattr(ph, "ollama_iste", sahte_iste)
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), np.zeros((10, 10), dtype=np.uint8))
    ph.oku_deepseek([p], cagri_timeout=42)
    assert gorulen["timeout"] == 42
```

- [ ] **Step 2: Testlerin KIRMIZI olduğunu doğrula**

Run: `cd /opt/mitas/harness/track_kunye && /opt/mitas/venvs/ocr/bin/python -m pytest test_pilot_hat_uretim.py -q`
Expected: FAIL/ERROR — `OLLAMA` env okumuyor, `KB_DUCKDB` yok, `havuz_derle_dizin` yok, `cagri_timeout` yok.

- [ ] **Step 3: pilot_hat.py'yi uyarla**

`harness/track_kunye/pilot_hat.py` içinde ŞU değişiklikleri yap (başka hiçbir şeye dokunma):

(a) `import base64, difflib, json, time, unicodedata, urllib.request` satırına `os` ekle:
```python
import base64, difflib, json, os, time, unicodedata, urllib.request
```

(b) `OLLAMA = "http://127.0.0.1:11434/api/generate"` satırını şununla değiştir:
```python
OLLAMA = os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"
KB_DUCKDB = os.environ.get("MITAS_KB_DUCKDB", "/opt/mitas/Mitas_Files/MitaData/mitas.duckdb")
```

(c) `havuz_derle` fonksiyonunun TAMAMINI şu iki fonksiyonla değiştir:
```python
def havuz_derle_dizin(kare_dizin: Path, desen: str = "*.png") -> tuple[list[Path], dict]:
    """Dizin-parametreli havuz derleme (üretim yüzeyi) — istatistik DÖNÜŞTE, global yok."""
    yollar = sorted(Path(kare_dizin).glob(desen))
    griler, gecerli = [], []
    for p in yollar:
        im = cv2.imread(str(p))
        if im is None:
            continue
        griler.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        gecerli.append(p)
    if not griler:
        return [], {"kare": 0, "sayfa": 0}
    sonuc = havuz_mod.havuz_derle(griler)
    ekler = havuz_mod.ikinci_gecis(griler, sonuc)
    ist = {"kare": len(griler), "esik": sonuc.istatistik.esik,
           "grup": sonuc.istatistik.grup_sayisi, "alarm": sonuc.istatistik.alarm,
           "sayfa": len(sonuc.sayfalar), "ikinci_gecis_ek": len(ekler)}
    return [gecerli[i] for i in sorted(set(sonuc.sayfalar) | set(ekler))], ist


def havuz_derle(slug: str) -> list[Path]:
    secim, ist = havuz_derle_dizin(EX / f"{slug}-exit_frames", "exit_*.png")
    global SON_HAVUZ_ISTATISTIK
    SON_HAVUZ_ISTATISTIK = {k: ist.get(k) for k in
                            ("esik", "grup", "alarm", "sayfa", "ikinci_gecis_ek")}
    return secim
```

(d) `kb_yukle` içindeki `duckdb.connect("/opt/mitas/Mitas_Files/MitaData/mitas.duckdb", read_only=True)` satırını:
```python
    con = duckdb.connect(KB_DUCKDB, read_only=True)
```

(e) `oku_deepseek(sayfalar: list[Path]) -> list[str]:` imzasını
`def oku_deepseek(sayfalar: list[Path], cagri_timeout: int = 900) -> list[str]:` yap ve içindeki
`ollama_iste(...)` çağrısına `timeout=cagri_timeout` argümanı ekle (num_predict=2048'in yanına).

(f) `oku_master` imzasına `cagri_timeout: int = 900` parametresi ekle ve son satırı
`return oku_deepseek(yollar, cagri_timeout=cagri_timeout)` yap.

- [ ] **Step 4: Testlerin YEŞİL olduğunu doğrula + regresyon**

Run: `cd /opt/mitas/harness/track_kunye && /opt/mitas/venvs/ocr/bin/python -m pytest test_pilot_hat_uretim.py test_messi.py test_ronaldo.py test_metrik.py test_taze_pilot.py test_pilot_hat_ronaldo.py -q`
Expected: hepsi PASS (önceki 57 + yeni 6), 1 skip olabilir.

- [ ] **Step 5: Commit**

```bash
cd /opt/mitas && git add harness/track_kunye/pilot_hat.py harness/track_kunye/test_pilot_hat_uretim.py
git commit -F /tmp/claude-1000/-opt-mitas/db7a3c41-434c-4002-8294-e264a8fec711/scratchpad/c1.txt
```
c1.txt içeriği:
```
feat(pilot_hat): üretim uyarlamaları — env-aware yollar + dizin-parametreli havuz

MITAS_OLLAMA_URL / MITAS_KB_DUCKDB env'leri; havuz_derle_dizin istatistiği
dönüş değerinde taşır (global yarış riski üretime taşınmaz; eski imza
harness için korunur); oku_deepseek/oku_master cagri_timeout parametresi.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

### Task 2: scripts/_pipe_track_kunye.py

**Files:**
- Create: `scripts/_pipe_track_kunye.py`
- Test: `tests/test_pipe_track_kunye.py` (yeni)

**Interfaces:**
- Consumes (Task 1): `pilot_hat.havuz_derle_dizin`, `oku_deepseek(cagri_timeout=)`, `oku_master(cagri_timeout=)`, `kb_yukle`, `ronaldo_kos`.
- Produces (Task 3 bunun CLI'sını çağırır): `_pipe_track_kunye.py --clip <dir> --frames <dir> [--base "<ad>"]`; çıktılar `clip_dir/track_kunye/{frame_dokum.txt, master_dokum.txt, ronaldo_kunye.txt, ronaldo_fark.json, manifest.json}` + kökte `<base> kunye3.txt`; stdout son satırı JSON: `{"status": "done|skipped|failed", "film", "band", ...}`; HER durumda exit 0.

- [ ] **Step 1: Failing testleri yaz**

`tests/test_pipe_track_kunye.py` (yeni dosya, tamamı):

```python
"""_pipe_track_kunye: gölge blok betiği — GPU'suz, pilot_hat monkeypatch'li."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

BETIK = Path("/opt/mitas/scripts/_pipe_track_kunye.py")


def _modul_yukle():
    spec = importlib.util.spec_from_file_location("_pipe_track_kunye", BETIK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sahte_pilot_hat(messi_satirlar, master_satirlar, band="green"):
    ph = types.ModuleType("pilot_hat")
    ph.havuz_derle_dizin = lambda d, desen="*.png": (
        sorted(Path(d).glob("*.png")), {"kare": 4, "sayfa": 2, "esik": 30,
                                        "grup": 2, "alarm": False, "ikinci_gecis_ek": 0})
    ph.oku_deepseek = lambda sayfalar, cagri_timeout=900: list(messi_satirlar)
    ph.oku_master = lambda png, out, bant_h=1100, bindirme=120, cagri_timeout=900: list(master_satirlar)
    ph.kb_yukle = lambda: {"neill archer", "john connell"}
    def ronaldo_kos(slug, out_dir, messi_dokum, master_dokum, kb, kb_tok,
                    kare_toplam, messi_kare, ibra_kare):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ronaldo_kunye.txt").write_text(
            "\n".join(messi_dokum + master_dokum) + "\n", encoding="utf-8")
        (out_dir / "ronaldo_fark.json").write_text("{}", encoding="utf-8")
        return {"film": slug, "confidence_band": band, "common_blind": False,
                "coverage_ratio": 0.5, "structural_anchor_missing": False,
                "birlesik_n": len(messi_dokum) + len(master_dokum)}
    ph.ronaldo_kos = ronaldo_kos
    return ph


def _klip_kur(tmp_path, kare_n=4, master=True, master_status=None):
    clip = tmp_path / "DENEME FILM 1999-0001-1-0000-00-1"
    frames = clip / "frames" / "cikis"
    frames.mkdir(parents=True)
    import numpy as np, cv2
    for i in range(kare_n):
        cv2.imwrite(str(frames / f"c_{i:04d}.png"),
                    np.full((60, 80), 40 + 30 * i, dtype=np.uint8))
    if master:
        cv2.imwrite(str(clip / "reading_master_runaware.png"),
                    np.full((200, 80), 128, dtype=np.uint8))
    if master_status is not None:
        (clip / "reading_master_runaware_manifest.json").write_text(
            json.dumps({"status": master_status, "frames": 58}), encoding="utf-8")
    return clip, frames


def _kostur(m, clip, frames, monkeypatch, ph=None, ollama=True, argv_ek=()):
    monkeypatch.setattr(m, "ollama_saglik", lambda timeout=3: ollama)
    if ph is not None:
        monkeypatch.setitem(sys.modules, "pilot_hat", ph)
    monkeypatch.setattr(sys, "argv",
                        ["_pipe_track_kunye.py", "--clip", str(clip),
                         "--frames", str(frames), "--base", "DENEME FILM", *argv_ek])
    rc = m.main()
    assert rc == 0
    return json.loads((clip / "track_kunye" / "manifest.json").read_text(encoding="utf-8"))


def test_ollama_down_skipped(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path)
    ozet = _kostur(m, clip, frames, monkeypatch, ollama=False)
    assert ozet["status"] == "skipped" and ozet["reason"] == "ollama_down"


def test_frames_bos_skipped(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, kare_n=0)
    ozet = _kostur(m, clip, frames, monkeypatch,
                   ph=_sahte_pilot_hat(["A"], ["B"]))
    assert ozet["status"] == "skipped" and ozet["reason"] == "frames_bos"


def test_mutlu_yol_5_dosya_ve_kunye3(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, master=True, master_status=None)
    messi = ["Tamino - Neill Archer"] * 30   # sağlık dedektörü 200 karakteri geçsin
    ibra = ["Sarastro - John Connell"] * 20
    ozet = _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, ibra))
    assert ozet["status"] == "done" and ozet["band"] == "green"
    tk = clip / "track_kunye"
    for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt",
               "ronaldo_fark.json", "manifest.json"):
        assert (tk / ad).stat().st_size > 0, ad
    k3 = clip / "DENEME FILM kunye3.txt"
    icerik = k3.read_text(encoding="utf-8")
    assert "MESSİ" in icerik and "İBRAHİMOVİC" in icerik and "RONALDO" in icerik
    assert "green" in icerik


def test_master_yok_ibra_bos_ama_devam(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, master=False)
    messi = ["Tamino - Neill Archer"] * 30
    ozet = _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, []))
    assert ozet["status"] == "done"
    assert ozet["ibra_atlandi_sebep"] == "master_yok"
    assert (clip / "track_kunye" / "master_dokum.txt").read_text(encoding="utf-8").strip() == ""


def test_master_bayat_atlanir(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, _ = _klip_kur(tmp_path, master=True, master_status="ibrahimovic_uretemedi")
    png, sebep = m.master_secim(clip)
    assert png is None and sebep == "master_bayat"


def test_master_saglam_secilir(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, _ = _klip_kur(tmp_path, master=True, master_status="ok")
    png, sebep = m.master_secim(clip)
    assert png is not None and sebep is None
    assert m.master_kare_sayisi(clip) == 58


def test_ornekle_kronolojik_ve_raporlu():
    m = _modul_yukle()
    girdi = list(range(250))
    secim, dusen = m.ornekle(girdi, ust_sinir=100)
    assert len(secim) == 100 and dusen == 150
    assert secim == sorted(secim)          # kronoloji korunur
    assert secim[0] == 0                   # baş düşmez
    kisa, d2 = m.ornekle([1, 2, 3], ust_sinir=100)
    assert kisa == [1, 2, 3] and d2 == 0


def test_deepseek_saglik():
    m = _modul_yukle()
    assert m.deepseek_saglik([]) == (False, "bos_cikti")
    assert m.deepseek_saglik(["kisa"]) == (False, "cok_kisa")
    cop = ["@#!% ^^&* ()[]" * 30]
    assert m.deepseek_saglik(cop)[1] == "garble_yuksek"
    temiz = ["Directed by John Smith and produced by the whole team"] * 10
    assert m.deepseek_saglik(temiz) == (True, "ok")
```

- [ ] **Step 2: Testlerin KIRMIZI olduğunu doğrula**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_pipe_track_kunye.py -q`
Expected: hepsi ERROR — `/opt/mitas/scripts/_pipe_track_kunye.py` yok.

- [ ] **Step 3: Betiği yaz**

`scripts/_pipe_track_kunye.py` (yeni dosya, tamamı):

```python
#!/usr/bin/env python3
"""track_kunye gölge bloğu: MESSİ + İBRAHİMOVİC-okuma + RONALDO (mix) — 3 çıktı.

Spec: docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md
GÖLGE SÖZLEŞMESİ: karar/PDF/teslim/reasons'a DOKUNMAZ; tüm çıktılar yan dosya.
Runaware master SALT-OKUNUR tüketilir; üretim zinciri dokunulmaz bölge.
HER durumda exit 0 (fail-safe); durum stdout son-satır JSON'unda.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
sys.path.insert(0, str(PROJE / "harness" / "track_kunye"))

MAX_KARE = int(os.environ.get("MITAS_TRACK_KUNYE_MAX_FRAMES", "100") or 100)
CAGRI_TIMEOUT = int(os.environ.get("MITAS_TRACK_KUNYE_CAGRI_TIMEOUT", "180") or 180)


def ollama_saglik(timeout: int = 3) -> bool:
    """Ollama ayakta mı? Uzun timeout'a hiç girmeden 3 sn'de karar (konsey S3)."""
    url = os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def master_secim(clip_dir: Path) -> tuple[Path | None, str | None]:
    """Kök runaware çıkış master'ı + bayatlık kontrolü (konsey S1).

    'ibrahimovic_uretemedi' manifest'i = bu tur üretilemedi, diskteki PNG eski
    turdan korunmuş ("kötü yerine hiç") — bayat master okunmaz.
    """
    png = clip_dir / "reading_master_runaware.png"
    man = clip_dir / "reading_master_runaware_manifest.json"
    if not png.is_file():
        return None, "master_yok"
    if man.is_file():
        try:
            durum = json.loads(man.read_text(encoding="utf-8")).get("status")
        except Exception:
            durum = None
        if durum == "ibrahimovic_uretemedi":
            return None, "master_bayat"
    return png, None


def master_kare_sayisi(clip_dir: Path) -> int | None:
    man = clip_dir / "reading_master_runaware_manifest.json"
    if not man.is_file():
        return None
    try:
        n = json.loads(man.read_text(encoding="utf-8")).get("frames")
        return int(n) if n is not None else None
    except Exception:
        return None


def ornekle(sayfalar: list, ust_sinir: int = MAX_KARE) -> tuple[list, int]:
    """Kronolojik düzgün-adımlı örnekleme; düşürülen raporlanır (sessiz kırpma yasak)."""
    if len(sayfalar) <= ust_sinir:
        return list(sayfalar), 0
    adim = len(sayfalar) / ust_sinir
    indeksler = sorted({min(len(sayfalar) - 1, int(i * adim)) for i in range(ust_sinir)})
    secim = [sayfalar[i] for i in indeksler]
    return secim, len(sayfalar) - len(secim)


def deepseek_saglik(metinler: list[str]) -> tuple[bool, str]:
    """Ucuz çöküş dedektörü (konsey S4): rodeo-sınıfı boş/garble döküm işaretlenir."""
    if not metinler:
        return False, "bos_cikti"
    birlesik = "\n".join(metinler)
    if len(birlesik) < 200:
        return False, "cok_kisa"
    alnum = sum(1 for c in birlesik if c.isalnum())
    if alnum / max(1, len(birlesik)) < 0.30:
        return False, "garble_yuksek"
    return True, "ok"


def kunye3_yaz(clip_dir: Path, base: str, messi_d: list[str], master_d: list[str],
               ronaldo_d: list[str], band: str | None) -> Path:
    """3 çıktının hub-kök yüzeyi (teslim/export'a YAZILMAZ — gölge sözleşmesi)."""
    p = clip_dir / f"{base} kunye3.txt"
    icerik = [f"# 3-KOLLU KÜNYE (gölge) — güven bandı: {band or 'yok'}",
              "", "## 1) MESSİ (framehavuz + deepseek)", *messi_d,
              "", "## 2) İBRAHİMOVİC (runaware master + deepseek)", *master_d,
              "", "## 3) RONALDO (mix)", *ronaldo_d, ""]
    p.write_text("\n".join(icerik), encoding="utf-8")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--base", default="")
    a = ap.parse_args()
    clip_dir = Path(a.clip)
    frames = Path(a.frames)
    out = clip_dir / "track_kunye"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ozet: dict = {"status": "failed", "film": clip_dir.name}

    def bitir() -> int:
        ozet["sure_sn"] = round(time.time() - t0, 1)
        try:
            (out / "manifest.json").write_text(
                json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(ozet, ensure_ascii=False), flush=True)
        return 0

    if not ollama_saglik():
        ozet.update(status="skipped", reason="ollama_down",
                    ollama_url=os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434"))
        return bitir()
    if not frames.is_dir() or not any(frames.glob("*.png")):
        ozet.update(status="skipped", reason="frames_bos")
        return bitir()

    try:
        import pilot_hat as ph
    except Exception as e:  # noqa: BLE001
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="import")
        return bitir()

    # KOL 1 — MESSİ seçimi + deepseek okuma
    secim, havuz_ist = ph.havuz_derle_dizin(frames, "*.png")
    if not secim:
        ozet.update(status="skipped", reason="messi_havuz_bos", havuz=havuz_ist)
        return bitir()
    secim, dusen = ornekle(secim)
    try:
        messi_dokum = ph.oku_deepseek(secim, cagri_timeout=CAGRI_TIMEOUT)
    except Exception as e:  # noqa: BLE001
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="messi_okuma")
        return bitir()
    (out / "frame_dokum.txt").write_text("\n".join(messi_dokum) + "\n", encoding="utf-8")
    _m_ok, m_sebep = deepseek_saglik(messi_dokum)

    # KOL 2 — İbrahimovic runaware master'ının deepseek okuması (salt-okunur tüketim)
    master_png, ibra_sebep = master_secim(clip_dir)
    master_dokum: list[str] = []
    if master_png is not None:
        try:
            master_dokum = ph.oku_master(master_png, out, cagri_timeout=CAGRI_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            ibra_sebep = f"okuma_hatasi:{type(e).__name__}"
    (out / "master_dokum.txt").write_text("\n".join(master_dokum) + "\n", encoding="utf-8")
    if master_dokum:
        _i_ok, i_sebep = deepseek_saglik(master_dokum)
    else:
        i_sebep = ibra_sebep or "bos"

    # KOL 3 — RONALDO çaprazı (saf metin, ucuz)
    try:
        kb = ph.kb_yukle()
        kb_tok = {t for ad in kb for t in ad.split() if len(t) >= 3}
        kare_toplam = sum(1 for _ in frames.glob("*.png"))
        manifest = ph.ronaldo_kos(clip_dir.name, out, messi_dokum, master_dokum,
                                  kb, kb_tok, kare_toplam=kare_toplam,
                                  messi_kare=len(secim),
                                  ibra_kare=master_kare_sayisi(clip_dir))
    except Exception as e:  # noqa: BLE001
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="ronaldo")
        return bitir()

    base = a.base or clip_dir.name
    ronaldo_kunye = (out / "ronaldo_kunye.txt").read_text(encoding="utf-8").splitlines()
    try:
        kunye3_yaz(clip_dir, base, messi_dokum, master_dokum, ronaldo_kunye,
                   manifest.get("confidence_band"))
    except Exception as e:  # noqa: BLE001
        ozet["kunye3_hata"] = f"{type(e).__name__}: {e}"[:200]

    ozet.update(status="done", band=manifest.get("confidence_band"),
                common_blind=manifest.get("common_blind"),
                coverage_ratio=manifest.get("coverage_ratio"),
                structural_anchor_missing=manifest.get("structural_anchor_missing"),
                birlesik_n=manifest.get("birlesik_n"),
                havuz=havuz_ist, secilen_kare=len(secim), dusurulen_n=dusen,
                messi_satir=len(messi_dokum), ibra_satir=len(master_dokum),
                deepseek_saglik={"messi": m_sebep, "ibra": i_sebep},
                ibra_atlandi_sebep=ibra_sebep)
    return bitir()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Testlerin YEŞİL olduğunu doğrula**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_pipe_track_kunye.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
cd /opt/mitas && git add scripts/_pipe_track_kunye.py tests/test_pipe_track_kunye.py
git commit -F /tmp/claude-1000/-opt-mitas/db7a3c41-434c-4002-8294-e264a8fec711/scratchpad/c2.txt
```
c2.txt içeriği:
```
feat(track_kunye): _pipe_track_kunye gölge betiği — 3 çıktı + korkuluklar

Ollama sağlık-kontrolü (3 sn fail-fast), Messi kare üst-sınırı (100,
düşürülen raporlu), runaware manifest bayatlık kontrolü, deepseek-çöküş
dedektörü, hub-kök kunye3 yüzeyi, her durumda exit 0 + son-satır JSON.
Konsey kırmızı-takım kabulleri (S1-S4) uygulandı.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

### Task 3: mitas_pipeline gölge bloğu

**Files:**
- Modify: `scripts/mitas_pipeline.py` (yalnız EK — LEGACY GÖLGE VL bloğunun önüne; 4061-4118 MASTER-PNG bloğuna DOKUNMA)
- Test: `tests/test_track_kunye_blok.py` (yeni)

**Interfaces:**
- Consumes (Task 2): `_pipe_track_kunye.py` CLI + son-satır JSON `{"status","band","common_blind",...}`.
- Produces: env bayrakları `MITAS_TRACK_KUNYE` (default "1"), `MITAS_TRACK_KUNYE_TIMEOUT` (default "1200"); event'ler `track_kunye_completed|skipped|failed`, `ronaldo_band_red|ronaldo_band_null|ronaldo_common_blind`; `_DURUM.json`'da `track_kunye` alanı. Task 4-5 bunları doğrular.

- [ ] **Step 1: Failing kaynak-denetim testini yaz**

`tests/test_track_kunye_blok.py` (yeni dosya, tamamı):

```python
"""mitas_pipeline track_kunye gölge bloğu — kaynak-denetim testleri.

4187 satırlık main() runtime'da koşturulamaz; bu testler bloğun varlığını,
sıralamasını (MASTER-PNG'den SONRA) ve fail-safe desenini kaynak üzerinde
doğrular (emsal: test_prod_defaults_ps1_mirror).
"""
from pathlib import Path

KAYNAK = Path("/opt/mitas/scripts/mitas_pipeline.py").read_text(encoding="utf-8")


def test_blok_var_ve_betigi_cagiriyor():
    assert "_pipe_track_kunye.py" in KAYNAK
    assert 'os.environ.get("MITAS_TRACK_KUNYE", "1")' in KAYNAK


def test_blok_master_sonrasi_legacy_oncesi():
    master_i = KAYNAK.index("KANONİK MASTER-PNG")
    blok_i = KAYNAK.index("_pipe_track_kunye.py")
    legacy_i = KAYNAK.index("LEGACY GÖLGE VL")
    assert master_i < blok_i < legacy_i


def test_blok_fail_safe_ve_timeout():
    i = KAYNAK.index("TRACK-KUNYE GÖLGE")
    parca = KAYNAK[i:i + 4000]
    assert "except Exception" in parca
    assert 'MITAS_TRACK_KUNYE_TIMEOUT", "1200"' in parca
    assert "track_kunye_failed" in parca


def test_event_adlari():
    for ad in ("track_kunye_completed", "track_kunye_skipped",
               "ronaldo_band_red", "ronaldo_band_null", "ronaldo_common_blind"):
        assert ad in KAYNAK, ad


def test_master_bloguna_dokunulmadi():
    # dokunulmaz bölgenin imza satırları aynen duruyor
    assert '_mp_runner = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"' in KAYNAK
    assert 'os.environ.get("MITAS_MASTER_PNG_TIMEOUT", "300")' in KAYNAK
```

- [ ] **Step 2: KIRMIZI doğrula**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_track_kunye_blok.py -q`
Expected: ilk 4 test FAIL (blok yok), son test PASS.

- [ ] **Step 3: Bloğu ekle**

`scripts/mitas_pipeline.py` içinde ŞU satırı bul (yaklaşık 4120. satır):

```python
    # ===== LEGACY GÖLGE VL — paralel debug kapalıysa eski davranışı koru =====
```

ve HEMEN ÖNÜNE şu bloğu ekle (Edit: old_string = yukarıdaki satır, new_string = aşağıdaki blok + o satır):

```python
    # ===== TRACK-KUNYE GÖLGE (2026-07-30): MESSİ + İBRA-OKUMA + RONALDO — 3 çıktı =====
    # Spec: docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md
    # ÜRETİME DOKUNMAZ: karar/PDF/teslim verildi; çıktılar clip_dir/track_kunye/ + kökte
    # "<ad> kunye3.txt". MASTER-PNG bloğundan SONRA koşmak ZORUNDA (runaware'i salt-okur).
    # FAIL-SAFE: hata/timeout ASLA pipeline'ı/kararı bozmaz. Kill: MITAS_TRACK_KUNYE=0.
    if (os.environ.get("MITAS_TRACK_KUNYE", "1").strip().lower() not in ("0", "false", "off", "no")
            and not args.no_ocr):
        _tk_t = time.perf_counter()
        _tk_ad = video.name if video is not None else clip_dir.name
        try:
            if cikis_frames.is_dir() and any(cikis_frames.glob("*.png")):
                _tk_cmd = [str(PY_OCR), str(HERE / "_pipe_track_kunye.py"),
                           "--clip", str(clip_dir), "--frames", str(cikis_frames),
                           "--base", file_base(trt, title)]
                _rctk, _outtk, _errtk = run(
                    _tk_cmd,
                    timeout=int(os.environ.get("MITAS_TRACK_KUNYE_TIMEOUT", "1200") or 1200))
                _jtk = last_json(_outtk) or {}
                timings["track_kunye"] = round(time.perf_counter() - _tk_t, 2)
                _tk_status = str(_jtk.get("status") or ("done" if _rctk == 0 else "failed"))
                _tk_band = _jtk.get("band")
                log_event("track_kunye_completed" if _tk_status == "done" else
                          ("track_kunye_skipped" if _tk_status == "skipped"
                           else "track_kunye_failed"),
                          level="info" if _tk_status == "done" else "warn",
                          summary=f"{_tk_ad}: track-kunye {_tk_status} "
                                  f"(band={_tk_band}, {timings['track_kunye']} sn).",
                          module="track-kunye", media_id=media_id, filename=_tk_ad,
                          duration_seconds=timings["track_kunye"],
                          detail={"clip_id": clip_id, "ozet": _jtk,
                                  "stderr": (_errtk or "")[-300:] if _rctk else None})
                if _tk_status == "done" and _tk_band in ("red", None):
                    log_event("ronaldo_band_red" if _tk_band == "red" else "ronaldo_band_null",
                              level="warn",
                              summary=f"{_tk_ad}: Ronaldo güven bandı {_tk_band or 'yok'} — göz-QC önerilir.",
                              module="track-kunye", media_id=media_id, filename=_tk_ad,
                              detail={"clip_id": clip_id, "common_blind": _jtk.get("common_blind")})
                if _tk_status == "done" and _jtk.get("common_blind"):
                    log_event("ronaldo_common_blind", level="warn",
                              summary=f"{_tk_ad}: ortak-körlük bayrağı — kapsama düşük, içerik-tamlık garantisi YOK.",
                              module="track-kunye", media_id=media_id, filename=_tk_ad,
                              detail={"clip_id": clip_id, "coverage_ratio": _jtk.get("coverage_ratio")})
                summary_obj["track_kunye"] = {"status": _tk_status, "band": _tk_band,
                                              "dir": str(clip_dir / "track_kunye")}
                write_json(clip_dir / "_DURUM.json", summary_obj)
            else:
                log_event("track_kunye_skipped", level="info",
                          summary=f"{_tk_ad}: track-kunye atlandı — frames/cikis yok/boş.",
                          module="track-kunye", media_id=media_id, filename=_tk_ad,
                          detail={"clip_id": clip_id})
        except Exception as _tke:  # noqa: BLE001 — gölge blok ASLA pipeline'ı bozmaz
            log_event("track_kunye_failed", level="warn",
                      summary=f"{_tk_ad}: track-kunye atlandı ({type(_tke).__name__}).",
                      module="track-kunye", media_id=media_id, filename=_tk_ad,
                      error=str(_tke)[:300], detail={"clip_id": clip_id})

```

- [ ] **Step 4: YEŞİL doğrula + sözdizimi**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_track_kunye_blok.py -q && /opt/mitas/venvs/ocr/bin/python -m py_compile scripts/mitas_pipeline.py && echo DERLENDI`
Expected: 5 passed + DERLENDI.

- [ ] **Step 5: Commit**

```bash
cd /opt/mitas && git add scripts/mitas_pipeline.py tests/test_track_kunye_blok.py
git commit -F /tmp/claude-1000/-opt-mitas/db7a3c41-434c-4002-8294-e264a8fec711/scratchpad/c3.txt
```
c3.txt içeriği:
```
feat(pipeline): track_kunye gölge bloğu — MASTER-PNG sonrası, fail-safe

MITAS_TRACK_KUNYE=1 default; video_vl deseni: subprocess + timeout(1200) +
timings + yapılandırılmış event'ler (completed/skipped/failed +
ronaldo_band_red/null + ronaldo_common_blind) + _DURUM.json yüzeyi.
Karar/PDF/teslim/reasons'a dokunulmaz; MASTER-PNG bloğu aynen korundu.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

### Task 4: track_kunye_batch_dogrula.py

**Files:**
- Create: `scripts/track_kunye_batch_dogrula.py`
- Test: `tests/test_track_kunye_batch_dogrula.py` (yeni)

**Interfaces:**
- Consumes: clip_dir yapısı (Task 2 çıktıları), `/opt/mitas/outputs/system_events.jsonl` (log_event havuzu — mitas_pipeline.py:117).
- Produces: CLI `track_kunye_batch_dogrula.py --liste <clip_dir satırlı txt> [--events <jsonl>]`; stdout tablo + `N/M PASSED`; eksikte exit 1. Task 5 bunu 15-film kanıtı olarak koşar.

- [ ] **Step 1: Failing testleri yaz**

`tests/test_track_kunye_batch_dogrula.py` (yeni dosya, tamamı):

```python
"""batch doğrulayıcı: sentetik clip_dir + event dosyasıyla, GPU'suz."""
import importlib.util
import json
from pathlib import Path

BETIK = Path("/opt/mitas/scripts/track_kunye_batch_dogrula.py")


def _modul_yukle():
    spec = importlib.util.spec_from_file_location("tk_dogrula", BETIK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _klip_kur(tmp_path, mid="1999-0001-1-0000-00-1", tam=True, band="green",
              status="done"):
    clip = tmp_path / f"DENEME FILM {mid}"
    (clip / "pdf").mkdir(parents=True)
    (clip / "pdf" / "kunye.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 11000 + b"\n%%EOF")
    tk = clip / "track_kunye"
    tk.mkdir()
    if tam:
        for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt"):
            (tk / ad).write_text("icerik\n", encoding="utf-8")
        (tk / "ronaldo_fark.json").write_text("{}", encoding="utf-8")
        (clip / "DENEME FILM kunye3.txt").write_text("# 3-KOLLU\n", encoding="utf-8")
    (tk / "manifest.json").write_text(json.dumps(
        {"status": status, "band": band, "film": clip.name}), encoding="utf-8")
    return clip


def _olaylar_yaz(tmp_path, mid, kinds):
    p = tmp_path / "system_events.jsonl"
    with p.open("a", encoding="utf-8") as f:
        for k in kinds:
            f.write(json.dumps({"kind": k, "media_id": mid, "ts": "t"}) + "\n")
    return p


TAM_OLAYLAR = ["credit_qc1_passed", "credit_validate_completed", "track_kunye_completed"]


def test_saglikli_klip_gecer(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True, sonuc


def test_bos_dosya_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    (clip / "track_kunye" / "ronaldo_kunye.txt").write_text("", encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("ronaldo_kunye" in e for e in sonuc["eksikler"])


def test_bozuk_pdf_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    (clip / "pdf" / "kunye.pdf").write_bytes(b"PDF DEGIL")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("pdf" in e.lower() for e in sonuc["eksikler"])


def test_qc1_olayi_yoksa_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1",
                      ["credit_validate_completed", "track_kunye_completed"])
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("qc1" in e.lower() for e in sonuc["eksikler"])


def test_skipped_gecerli_sebeple_uyarili_gecer(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path, tam=False, band=None, status="skipped")
    man = clip / "track_kunye" / "manifest.json"
    man.write_text(json.dumps({"status": "skipped", "reason": "frames_bos",
                               "film": clip.name}), encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1",
                      ["credit_qc1_passed", "credit_validate_completed",
                       "track_kunye_skipped"])
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True and sonuc["uyari"] == "skipped:frames_bos"


def test_band_null_sebepsiz_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path, band=None, status="done")
    man = clip / "track_kunye" / "manifest.json"
    man.write_text(json.dumps({"status": "done", "band": None, "film": clip.name,
                               "ibra_atlandi_sebep": None, "common_blind": False}),
                   encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("band" in e.lower() for e in sonuc["eksikler"])
```

- [ ] **Step 2: KIRMIZI doğrula**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_track_kunye_batch_dogrula.py -q`
Expected: hepsi ERROR — betik yok.

- [ ] **Step 3: Betiği yaz**

`scripts/track_kunye_batch_dogrula.py` (yeni dosya, tamamı):

```python
#!/usr/bin/env python3
"""15-film (ve sonrası) batch doğrulayıcı — "istisnasız bağlı çalışıyor" kanıtı.

Spec: docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md
Kullanım:
  /opt/mitas/venvs/ocr/bin/python scripts/track_kunye_batch_dogrula.py \
      --liste kliplerim.txt [--events /opt/mitas/outputs/system_events.jsonl]
kliplerim.txt: satır başına bir clip_dir mutlak yolu.
Çıktı: film×kontrol tablosu + "N/M PASSED"; eksik varsa exit 1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MID_DESEN = re.compile(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)")
VARSAYILAN_EVENTS = "/opt/mitas/outputs/system_events.jsonl"


def olaylari_yukle(yol: Path) -> list[dict]:
    olaylar = []
    p = Path(yol)
    if not p.is_file():
        return olaylar
    for satir in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            olaylar.append(json.loads(satir))
        except Exception:
            continue
    return olaylar


def _pdf_saglam(pdf: Path) -> bool:
    """fitz ocr-venv'de yok — magic-byte + boyut + EOF kontrolü yeterli."""
    if not pdf.is_file() or pdf.stat().st_size <= 10240:
        return False
    veri = pdf.read_bytes()
    return veri.startswith(b"%PDF") and b"%%EOF" in veri[-2048:]


def klip_dogrula(clip_dir: Path, olaylar: list[dict]) -> dict:
    eksikler: list[str] = []
    uyari = ""
    mid_m = MID_DESEN.search(clip_dir.name)
    mid = mid_m.group(1) if mid_m else ""
    film_olaylari = [e for e in olaylar if e.get("media_id") == mid] if mid else []
    kinds = {str(e.get("kind") or "") for e in film_olaylari}

    # K1 — PDF
    if not _pdf_saglam(clip_dir / "pdf" / "kunye.pdf"):
        eksikler.append("pdf/kunye.pdf yok/bozuk/kucuk")

    # K2 — QC olay zinciri (media_id ile)
    if not any(k.startswith("credit_qc1") for k in kinds):
        eksikler.append("QC1 olayı yok (credit_qc1_*)")
    if not any(("validate" in k) or ("qc2" in k.lower()) for k in kinds):
        eksikler.append("QC2/validate olayı yok")
    if not any(k.startswith("track_kunye") for k in kinds):
        eksikler.append("track_kunye olayı yok")

    # K3 — track_kunye çıktıları + manifest tutarlılığı
    tk = clip_dir / "track_kunye"
    man_p = tk / "manifest.json"
    man: dict = {}
    if man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
        except Exception:
            eksikler.append("manifest.json bozuk")
    else:
        eksikler.append("track_kunye/manifest.json yok")
    durum = man.get("status")
    if durum == "done":
        for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt",
                   "ronaldo_fark.json"):
            p = tk / ad
            if ad == "ronaldo_kunye.txt":
                if not p.is_file() or p.stat().st_size == 0:
                    eksikler.append(f"{ad} yok/0-bayt")
            elif not p.is_file():
                eksikler.append(f"{ad} yok")
        if man.get("band") is None and not man.get("ibra_atlandi_sebep") \
                and not man.get("common_blind"):
            eksikler.append("band null ama sebep yok (ibra_atlandi/common_blind boş)")
        if not list(clip_dir.glob("* kunye3.txt")):
            eksikler.append("kök kunye3.txt yok")
    elif durum == "skipped":
        if man.get("reason"):
            uyari = f"skipped:{man['reason']}"
        else:
            eksikler.append("skipped ama reason yok")
    elif durum is not None:
        eksikler.append(f"track_kunye status={durum}")

    return {"film": clip_dir.name, "gecti": not eksikler,
            "eksikler": eksikler, "uyari": uyari}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", required=True)
    ap.add_argument("--events", default=VARSAYILAN_EVENTS)
    a = ap.parse_args()
    klipler = [Path(s.strip()) for s in Path(a.liste).read_text(encoding="utf-8").splitlines()
               if s.strip()]
    olaylar = olaylari_yukle(Path(a.events))
    gecen = 0
    for clip in klipler:
        s = klip_dogrula(clip, olaylar)
        durum = "PASS" if s["gecti"] else "FAIL"
        if s["uyari"]:
            durum += f" ({s['uyari']})"
        print(f"{durum:28s} {s['film']}")
        for e in s["eksikler"]:
            print(f"    - {e}")
        gecen += 1 if s["gecti"] else 0
    print(f"\n{gecen}/{len(klipler)} PASSED")
    return 0 if gecen == len(klipler) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: YEŞİL doğrula**

Run: `/opt/mitas/venvs/ocr/bin/python -m pytest tests/test_track_kunye_batch_dogrula.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /opt/mitas && git add scripts/track_kunye_batch_dogrula.py tests/test_track_kunye_batch_dogrula.py
git commit -F /tmp/claude-1000/-opt-mitas/db7a3c41-434c-4002-8294-e264a8fec711/scratchpad/c4.txt
```
c4.txt içeriği:
```
feat(track_kunye): batch doğrulayıcı — "istisnasız bağlı" kanıt scripti

Film başına: PDF magic-byte sağlığı, media_id'li QC1/QC2+validate+track_kunye
olay zinciri, 5-dosya + 0-bayt + band-sebep tutarlılığı, kök kunye3 yüzeyi.
Çıktı N/M PASSED; eksikte exit 1. (Konsey S6 birleşimi: GLM + Nemotron.)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

### Task 5: Smoke + 15-film testi + sabah raporu (ORKESTRATÖR koşar — subagent'a verilmez)

**Files:**
- Kullan: `scratchpad/test15_klipler.tsv` (15 film, slug/media_id/dosya-adı)
- Üret: koşu listesi txt (clip_dir'ler), `outputs/taze_pilot/../` DEĞİL — üretim Database klasörleri; sabah raporu `docs/GUNLUK.md` girişi

- [ ] Tek-film smoke: 15-lik listeden 1 film, worker'ın kullandığı komutla:
  `cd /opt/mitas && ./venvs/... scripts/mitas_pipeline.py --video "<GVFS yolu>" --profile film` (worker komut şekli: asr_server.py:758-1017'deki gibi; --no-copy-source worker'a özgü, tek koşuda kullanılmaz). Bitince: `clip_dir/track_kunye/` 5 dosya + kökte kunye3 + `outputs/system_events.jsonl`'de track_kunye_* + PDF kontrol.
- [ ] Sorun çıkarsa düzelt (systematic-debugging), commit'le, smoke'u tekrarla.
- [ ] Kalan 14 filmi sıralı koş (GPU tek-sıra; arka plan görev + bitiş bildirimi).
- [ ] `track_kunye_batch_dogrula.py --liste <15 clip_dir>` → hedef 15/15 PASSED; FAIL'leri düzelt-tekrarla ("qc1 qc2 gerekli tüm süreçleri düzelt revize et").
- [ ] vahsi-afrika S5 analizi (pilot çıktılarından, GPU'suz): ronaldo_fark.json + üç kol
  skor detayı → metrik tuzağı mı birleşim hatası mı; sabah karar maddesine yaz.
- [ ] Sabah raporu: GUNLUK.md girişi (yapılan/öğrenilen/bekleyen + 15-film tablo + band
  dağılımı + düzeltilen hatalar + açık kararlar) + Çağatay'a özet mesaj.

## Self-Review Notları

- Spec kapsama: gölge blok (T3), betik+korkuluklar S1-S4 (T2), pilot_hat env/dizin (T1),
  doğrulayıcı S6 (T4), 15-film protokol (T5). PDF-dokunma-yok ve giriş-kapsam-dışı
  kararları kod gerektirmez (T3'ün "yalnız EK" kısıtı + spec).
- Tip tutarlılığı: `havuz_derle_dizin -> tuple[list[Path], dict]` T1=T2; manifest
  status değerleri "done|skipped|failed" T2=T3=T4; band "green|yellow|red|None" T2=T3=T4.
- Placeholder taraması: yok — tüm kod blokları tam.
