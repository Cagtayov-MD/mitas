#!/usr/bin/env python3
"""McGrady — künye kimlik/doğrulama kulesi (QC2'nin yeni evi). Başka hiçbir şey yapmaz.

Kule girişi. Motor (src/motor.py) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma:
    Allstar/mcgrady/mcgrady tek --girdi in/paket.json --film-id 2025-1307-1-0000-50-0
    Allstar/mcgrady/mcgrady start --input in          # toplu, _TAMAM olanı atlar

Çıktı daima out/<film_id>/mcgrady.json + _TAMAM. Çağıran çıktı yolunu seçmez.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import Cikti, GirdiHatasi, ariza, paket_oku  # noqa: E402


def _config() -> dict:
    y = KULE / "config.yaml"
    if not y.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return "mcgrady@" + sha if sha else "mcgrady@?"
    except Exception:
        return "mcgrady@?"


def zemin_env_uygula(config: dict) -> None:
    """config.yaml'daki zemin yollarını env'e YAZ (kule kendi zeminini ilan eder;
    config değeri boşsa env/dokunulmaz). Anahtar adları motor modüllerinin
    okuduğı env'lerle aynıdır."""
    zemin = config.get("zemin") or {}
    esleme = {
        "wikidata_duckdb": "MITAS_WIKIDATA_DUCKDB",
        "imdb_duckdb": "MITAS_IMDB_DUCKDB",
        "web_cache_dir": "MITAS_WEB_CACHE_DIR",
    }
    for cfg_ana, env_adi in esleme.items():
        deger = zemin.get(cfg_ana)
        if deger:
            os.environ[env_adi] = str(deger)


def tek(girdi_yolu: str, film_id: str, kok: Path | None = None) -> Cikti:
    """Bir paket → bir Cikti. İstisna sızdırmaz; motor eksikse ARIZA(MOTOR_EKSIK)."""
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    try:
        paket = paket_oku(girdi_yolu)
    except GirdiHatasi as e:
        c = ariza(film_id, "GIRDI_HATASI", str(e)[:300])
        c.sure_sn, c.motor_surumu = round(time.time() - t0, 1), _surum()
        return c
    profile = paket.get("profile", "film")
    try:
        import motor
        cfg = _config()
        zemin_env_uygula(cfg)
        r = motor.calistir(paket, cfg, afis_dizini=(kok / film_id))
    except Exception as e:  # MotorArizasi dahil — geniş yakalama bilinçli (kobe kalıbı)
        sinif = getattr(e, "sinif", None) or "MOTOR"
        c = ariza(film_id, sinif, (type(e).__name__ + ": " + str(e))[:300], profile=profile)
        c.sure_sn, c.motor_surumu = round(time.time() - t0, 1), _surum()
        c.yaz(kok)
        return c
    c = Cikti(
        film_id=film_id, profile=profile, durum=r["durum"],
        kimlik=r["kimlik"], oneriler=r["oneriler"], yonetmen=r["yonetmen"],
        web_oneri=r["web_oneri"], garble=r["garble"], afis=r["afis"],
        karar_onerileri=r["karar_onerileri"], kanit=r["kanit"],
        sure_sn=round(time.time() - t0, 1), motor_surumu=_surum(),
    )
    c.yaz(kok)
    return c


def toplu(girdi_dizini: Path, kok: Path | None = None) -> list[Cikti]:
    """Klasördeki her *.json paketini işle; _TAMAM varsa atla (kaldığı yerden devam)."""
    kok = Path(kok) if kok else OUT
    sonuc = []
    for p in sorted(Path(girdi_dizini).glob("*.json")):
        fid = p.stem
        if (kok / fid / "_TAMAM").exists():
            print("[atla] " + fid)
            continue
        c = tek(str(p), fid, kok)
        sonuc.append(c)
        print("[" + c.durum + "] " + fid + " sure=" + str(c.sure_sn) + "s")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mcgrady",
                                 description="kunye kimlik/dogrulama kulesi (QC2)")
    alt = ap.add_subparsers(dest="komut", required=True)

    a = alt.add_parser("start", help="toplu: girdi klasöründeki her paketi işle")
    a.add_argument("--input", required=True, help="paket (*.json) klasörü — örn. in/")
    a.add_argument("--out", help="çıktı kök dizinini ezer (varsayılan: out/)")

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--girdi", required=True, help="girdi paketi (mcgrady.girdi/v1 JSON)")
    b.add_argument("--film-id", required=True)
    b.add_argument("--out", help="çıktı kök dizinini ezer (varsayılan: out/)")

    n = ap.parse_args(argv)
    kok = Path(n.out) if n.out else None
    if n.komut == "start":
        toplu(Path(n.input), kok)
        return 0
    c = tek(n.girdi, n.film_id, kok)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
