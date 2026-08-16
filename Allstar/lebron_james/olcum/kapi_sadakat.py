#!/usr/bin/env python3
"""SADAKAT KAPISI — kule çıktısı üretimin çıktısıyla BİT-BİREBİR aynı mı?

Taşımanın doğruluğu iddia edilmez, ÖLÇÜLÜR. Bu betik iki yolu aynı kare
klasöründe koşturup master PNG'lerin SHA-256'sını karşılaştırır:

  ÜRETİM : harness/master_dup/lebron_james.compose_lebron(ims=...)
           kareler db_compose_master.rd_cached + nat_sort_key ile yüklenir,
           PNG db_compose_master.wr ile yazılır  (master_png_monitor.py:139-166)
  KULE   : Allstar/lebron_james  (main.tek → src/derleyici.derle)

EŞİK: sapma 0. Tek sapma bile kapıyı kapatır ve sebebi bulunmadan ilerlenmez.

Kapı DIŞARIYI çağırır — bu kasıtlıdır ve kule kuralını ihlal etmez: burası
kulenin kodu değil, ölçüm yatağı. Karşılaştırılacak şey zaten dışarıdadır.

Kullanım:
  ../../kobe/venv/bin/python kapi_sadakat.py --n 8
  ../../kobe/venv/bin/python kapi_sadakat.py --hepsi        # 440 film, saatler
  ../../kobe/venv/bin/python kapi_sadakat.py --film acemiler-cetesi-exit_frames
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
KOK = KULE.parents[1]                      # proje kökü
EX_KARE_ROOT = Path(os.environ.get("MITAS_EX_KARE_ROOT",
                                   Path.home() / "Ex_Frame"))
URETIM_MOTOR = KOK / "harness" / "master_dup"
URETIM_DC = KOK / "OCR-worktree" / "db_compose_master.py"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _uretim_yolu(kare_dizini: Path, gecici: Path) -> tuple[str | None, dict]:
    """Bugünkü üretim yolunu BİREBİR koştur → (sha256, manifest)."""
    import importlib.util
    if str(URETIM_MOTOR) not in sys.path:
        sys.path.insert(0, str(URETIM_MOTOR))
    spec = importlib.util.spec_from_file_location("dcmaster", str(URETIM_DC))
    dc = importlib.util.module_from_spec(spec)
    sys.modules["dcmaster"] = dc
    spec.loader.exec_module(dc)
    import lebron_james as uretim

    import glob
    frames = sorted(glob.glob(str(kare_dizini / "*.png")), key=dc.nat_sort_key)
    ims = [im for im in (dc.rd_cached(f) for f in frames) if im is not None]
    if len(ims) < 2:
        return None, {"durum": "kare_yok", "kare": len(ims)}
    master, manifest = uretim.compose_lebron("uretim", ims=ims)
    if master is None:
        return None, manifest
    gecici.parent.mkdir(parents=True, exist_ok=True)
    dc.wr(gecici, master)
    return _sha(gecici.read_bytes()), manifest


def _kule_yolu(kare_dizini: Path, film_id: str, kok: Path) -> tuple[str | None, dict]:
    """Kuleyi koştur → (sha256, cikti sozlugu)."""
    sys.path.insert(0, str(KULE))
    sys.path.insert(0, str(KULE / "src"))
    import main
    from sozlesme import Girdi
    c = main.tek(Girdi(film_id=film_id, kareler=str(kare_dizini)), kok)
    p = kok / film_id / "cikis" / "master.png"
    return (_sha(p.read_bytes()) if p.is_file() else None), c.sozluk()


def kiyasla(kare_dizini: Path, calisma: Path) -> dict:
    fid = kare_dizini.name
    t0 = time.time()
    u_sha, u_man = _uretim_yolu(kare_dizini, calisma / "uretim" / f"{fid}.png")
    k_sha, k_cikti = _kule_yolu(kare_dizini, fid, calisma / "kule")
    return {
        "film": fid,
        "uretim_sha": u_sha, "kule_sha": k_sha,
        "ayni": (u_sha == k_sha) and u_sha is not None,
        "ikisi_de_uretemedi": u_sha is None and k_sha is None,
        "uretim_durum": u_man.get("durum"), "kule_durum": k_cikti.get("durum"),
        "uretim_boy": (u_man.get("size") or [None, None])[1],
        "kule_boy": (k_cikti.get("uretilen") or [{}])[0].get("boy"),
        "sure_sn": round(time.time() - t0, 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kapi_sadakat")
    ap.add_argument("--n", type=int, default=8, help="ilk N film")
    ap.add_argument("--hepsi", action="store_true")
    ap.add_argument("--film", help="tek dizin adi")
    ap.add_argument("--kok", default=str(EX_KARE_ROOT))
    ap.add_argument("--cikti", default=str(KULE / "raporlar" / "kapi_sadakat.json"))
    a = ap.parse_args(argv)

    kok = Path(a.kok)
    if not kok.is_dir():
        print(json.dumps({"hata": f"kare koku yok: {kok}"}, ensure_ascii=False))
        return 2
    dizinler = sorted(d for d in kok.iterdir() if d.is_dir())
    if a.film:
        dizinler = [d for d in dizinler if d.name == a.film]
    elif not a.hepsi:
        dizinler = dizinler[:a.n]

    calisma = Path("/tmp/lebron_kapi")
    sonuc = []
    for i, d in enumerate(dizinler, 1):
        try:
            r = kiyasla(d, calisma)
        except Exception as e:  # noqa: BLE001 — bir film patlarsa kapı devam eder
            r = {"film": d.name, "ayni": False, "hata": f"{type(e).__name__}: {e}"}
        sonuc.append(r)
        isaret = "✓" if r.get("ayni") else ("=" if r.get("ikisi_de_uretemedi") else "✗")
        print(f"[{i}/{len(dizinler)}] {isaret} {r['film']} "
              f"uretim={r.get('uretim_boy')} kule={r.get('kule_boy')} "
              f"{r.get('sure_sn', '?')}s", flush=True)

    ayni = sum(1 for r in sonuc if r.get("ayni"))
    esit_bos = sum(1 for r in sonuc if r.get("ikisi_de_uretemedi"))
    sapma = [r for r in sonuc if not r.get("ayni") and not r.get("ikisi_de_uretemedi")]
    ozet = {"film": len(sonuc), "birebir": ayni, "ikisi_de_uretemedi": esit_bos,
            "sapma": len(sapma), "GECTI": len(sapma) == 0,
            "sapanlar": [r["film"] for r in sapma]}
    Path(a.cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(a.cikti).write_text(json.dumps({"ozet": ozet, "filmler": sonuc},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False))
    return 0 if ozet["GECTI"] else 1


if __name__ == "__main__":
    sys.exit(main())
