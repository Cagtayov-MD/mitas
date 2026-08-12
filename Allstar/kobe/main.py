#!/usr/bin/env python3
"""Kobe — film sonu jeneriğinin başladığı kareyi bulur. Başka hiçbir şey yapmaz.

Kule girişi. Motor (src/motor.py) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/kobe/kobe start --input /yol/videolar
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
SCRATCH = KULE / "scratch"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

KUYRUK_SN, KARE_FPS, KALITE = 600, 2, 3      # config.yaml varsayılanları


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
        return f"kobe@{sha}" if sha else "kobe@?"
    except Exception:
        return "kobe@?"


def film_id_uret(yol: Path, kareler_modu: bool) -> str:
    """Tek kural, tahmin yok: video → uzantısız ad, kare dizini → dizin adı."""
    return yol.name if kareler_modu else yol.stem


def kare_cikar(video: str, hedef: Path) -> tuple[Path, int]:
    """Kapanış penceresini çıkar → (dizin, pencere_baslangic_sn).

    Tarif havuz_kur.sh:74-78'den birebir alınmıştır — %94.5 bu kare üretimiyle
    ölçüldü, başka tarif skoru geçersiz kılar.
    """
    hedef.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", video],
                       capture_output=True, text=True, timeout=120)
    try:
        sure = int(float(p.stdout.strip()))
    except (ValueError, AttributeError):
        raise RuntimeError(f"ffprobe sure okuyamadi: {p.stderr.strip()[:200]}")
    ss = max(0, sure - KUYRUK_SN)
    k = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-i", video,
                        "-vf", f"fps={KARE_FPS}", "-q:v", str(KALITE),
                        str(hedef / "c_%05d.png")],
                       capture_output=True, text=True, timeout=900)
    n = len(list(hedef.glob("*.png")))
    if n == 0:
        raise RuntimeError(f"kare cikmadi (rc={k.returncode}): {k.stderr.strip()[:200]}")
    return hedef, ss


def _tespit(dizin: str, config: dict):
    """Motoru çağıran TEK yer — testler burayı değiştirir."""
    import motor
    m = config.get("motor", {})
    return motor.tespit_v5(dizin, fps=m.get("fps", 25.0),
                           stride=m.get("stride", 2),
                           ocr_stride=m.get("ocr_stride", 2))


def tek(girdi: Girdi, kok: Path | None = None) -> Cikti:
    """Bir film → bir Cikti. Asla istisna sızdırmaz; her hata ARIZA olur."""
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    benim_scratch: Path | None = None
    pencere_ss = 0
    try:
        if girdi.video:
            benim_scratch = Path(SCRATCH) / girdi.film_id
            try:
                dizin, pencere_ss = kare_cikar(girdi.video, benim_scratch)
            except Exception as e:
                c = ariza(girdi.film_id, "KARE_CIKARIM", str(e)[:300])
                c.sure_sn = round(time.time() - t0, 1)
                c.motor_surumu = _surum()
                c.yaz(kok)
                return c
        else:
            dizin = Path(girdi.kareler)

        try:
            r = _tespit(str(dizin), girdi.config)
        except Exception as e:
            c = ariza(girdi.film_id, "MOTOR", f"{type(e).__name__}: {e}"[:300])
            c.sure_sn = round(time.time() - t0, 1)
            c.motor_surumu = _surum()
            c.yaz(kok)
            return c

        n = len(list(Path(dizin).glob("*.png"))) or len(list(Path(dizin).glob("*.jpg")))
        kanit = {"kare_sayisi": n, "kare_fps": float(KARE_FPS),
                 "pencere_baslangic_sn": float(pencere_ss),
                 "yontem": getattr(r, "yontem", ""),
                 "ocr_hata": getattr(r, "ocr_hata", 0)}
        if r.start_frame == -1:
            c = Cikti(film_id=girdi.film_id, durum="KREDI_YOK", kanit=kanit)
        else:
            c = Cikti(film_id=girdi.film_id, durum="BULUNDU",
                      baslangic_kare=int(r.start_frame),
                      baslangic_sn=round(pencere_ss + r.start_frame / KARE_FPS, 2),
                      guven=round(float(getattr(r, "guven", 0.0)), 3),
                      script=getattr(r, "script", "en"), kanit=kanit)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c
    finally:
        # YALNIZ Kobe'nin actigi dizin silinir. Disaridan verilen kare
        # dizinine asla dokunulmaz (tek-yazar ilkesi).
        if benim_scratch is not None:
            shutil.rmtree(benim_scratch, ignore_errors=True)


def toplu(girdi_dizini: Path, kareler_modu: bool, kok: Path | None = None) -> list[Cikti]:
    """Girdi yolundaki her öğeyi işle; _TAMAM olanı atla (kaldığı yerden devam)."""
    kok = Path(kok) if kok else OUT
    girdi_dizini = Path(girdi_dizini)
    ogeler = sorted(p for p in girdi_dizini.iterdir()
                    if (p.is_dir() if kareler_modu else p.suffix.lower()
                        in (".mp4", ".mkv", ".avi", ".mov", ".ts")))
    sonuc = []
    for p in ogeler:
        fid = film_id_uret(p, kareler_modu)
        if (kok / fid / "_TAMAM").exists():
            print(f"[atla] {fid}")
            continue
        g = Girdi(film_id=fid, **({"kareler": str(p)} if kareler_modu else {"video": str(p)}))
        c = tek(g, kok)
        sonuc.append(c)
        print(f"[{c.durum}] {fid} kare={c.baslangic_kare} sure={c.sure_sn}s")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kobe", description="jenerik baslangic tespiti")
    alt = ap.add_subparsers(dest="komut", required=True)

    a = alt.add_parser("start", help="toplu: girdi yolundaki her ogeyi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--kareler", action="store_true",
                   help="girdi yolu hazir kare dizinleri iceriyor")

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--video")
    b.add_argument("--kareler")
    b.add_argument("--film-id", required=True)

    n = ap.parse_args(argv)
    if n.komut == "start":
        toplu(Path(n.input), n.kareler)
        return 0
    try:
        g = Girdi(film_id=n.film_id, video=n.video, kareler=n.kareler)
    except GirdiHatasi as e:
        c = ariza(n.film_id, "GIRDI_HATASI", str(e))
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    print(json.dumps(tek(g).sozluk(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
