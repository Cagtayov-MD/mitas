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

def _env_int(ad: str, varsayilan: int) -> int:
    """Bozuk env değeri ('1k', ' 180 ', boş) betiği import aşamasında ÇÖKERTEMEZ
    (konsey bug-avı GLM-1/KIM-2) — fail-safe sözleşmesi exit 0 + JSON ister."""
    try:
        return int((os.environ.get(ad) or "").strip() or varsayilan)
    except (ValueError, TypeError):
        return varsayilan


MAX_KARE = _env_int("MITAS_TRACK_KUNYE_MAX_FRAMES", 100)
CAGRI_TIMEOUT = _env_int("MITAS_TRACK_KUNYE_CAGRI_TIMEOUT", 180)

# Spec: docs/superpowers/specs/2026-08-12-nash-giris-aktivasyon-design.md §3.1
# Segmente bağlı 5 sabit kod tek yerde. Varsayılan "cikis" — bugünkü davranış (§5.1).
_SEG = {
    "cikis": {"out": "track_kunye", "png": "reading_master_runaware.png",
              "man": "reading_master_runaware_manifest.json", "k3": "kunye3.txt"},
    "giris": {"out": "track_kunye_giris", "png": "giris_reading_master_runaware.png",
              "man": "giris_reading_master_runaware_manifest.json", "k3": "kunye3_giris.txt"},
}


def _ollama_kok() -> str:
    return (os.environ.get("MITAS_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")


def ollama_saglik(timeout: int = 3) -> bool:
    """Ollama ayakta mı? Uzun timeout'a hiç girmeden 3 sn'de karar (konsey S3)."""
    url = _ollama_kok() + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def master_secim(clip_dir: Path, segment: str = "cikis") -> tuple[Path | None, str | None]:
    """Kök runaware master'ı (segmente göre) + bayatlık kontrolü (konsey S1).

    'ibrahimovic_uretemedi' manifest'i = bu tur üretilemedi, diskteki PNG eski
    turdan korunmuş ("kötü yerine hiç") — bayat master okunmaz.
    """
    seg = _SEG[segment]
    png = clip_dir / seg["png"]
    man = clip_dir / seg["man"]
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


def master_kare_sayisi(clip_dir: Path, segment: str = "cikis") -> int | None:
    man = clip_dir / _SEG[segment]["man"]
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
    # SON kare zorla dahil (konsey bug-avı GLM-3): düzgün-adım son indeksi hiç
    # seçmeyebiliyor, © / "SON" kartı tam orada — yapısal çapa kaybı olurdu.
    indeksler = sorted({min(len(sayfalar) - 1, int(i * adim)) for i in range(ust_sinir)}
                       | {len(sayfalar) - 1})
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
               ronaldo_d: list[str], band: str | None, segment: str = "cikis") -> Path:
    """3 çıktının hub-kök yüzeyi (teslim/export'a YAZILMAZ — gölge sözleşmesi)."""
    p = clip_dir / f"{base} {_SEG[segment]['k3']}"
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
    ap.add_argument("--segment", choices=("cikis", "giris"), default="cikis")
    a = ap.parse_args()
    clip_dir = Path(a.clip)
    frames = Path(a.frames)
    out = clip_dir / _SEG[a.segment]["out"]
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ozet: dict = {"status": "failed", "film": clip_dir.name, "segment": a.segment}

    def bitir() -> int:
        ozet["sure_sn"] = round(time.time() - t0, 1)
        try:
            (out / "manifest.json").write_text(
                json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(ozet, ensure_ascii=False), flush=True)
        return 0

    try:
        return _govde(a, clip_dir, frames, out, ozet, bitir)
    except Exception as e:  # noqa: BLE001 — üst duvar (konsey): sözleşme her koşulda exit 0 + JSON
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="beklenmedik")
        return bitir()


def _govde(a, clip_dir: Path, frames: Path, out: Path, ozet: dict, bitir) -> int:
    if not ollama_saglik():
        ozet.update(status="skipped", reason="ollama_down", ollama_url=_ollama_kok())
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
        messi_dokum = ph.oku_deepseek(secim, cagri_timeout=CAGRI_TIMEOUT) or []
    except Exception as e:  # noqa: BLE001
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="messi_okuma")
        return bitir()
    (out / "frame_dokum.txt").write_text("\n".join(messi_dokum) + "\n", encoding="utf-8")
    _m_ok, m_sebep = deepseek_saglik(messi_dokum)

    # KOL 2 — İbrahimovic runaware master'ının deepseek okuması (salt-okunur tüketim)
    master_png, ibra_sebep = master_secim(clip_dir, a.segment)
    master_dokum: list[str] = []
    if master_png is not None:
        try:
            master_dokum = ph.oku_master(master_png, out, cagri_timeout=CAGRI_TIMEOUT) or []
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
                                  ibra_kare=master_kare_sayisi(clip_dir, a.segment)) or {}
    except Exception as e:  # noqa: BLE001
        ozet.update(status="failed", error_class=type(e).__name__,
                    error=str(e)[:300], asama="ronaldo")
        return bitir()

    base = a.base or clip_dir.name
    rk = out / "ronaldo_kunye.txt"
    ronaldo_kunye = rk.read_text(encoding="utf-8").splitlines() if rk.is_file() else []
    try:
        kunye3_yaz(clip_dir, base, messi_dokum, master_dokum, ronaldo_kunye,
                   manifest.get("confidence_band"), a.segment)
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
