#!/usr/bin/env python3
"""Jordan — mp4 girer, yazı çıkar. Başka hiçbir şey yapmaz.

Kule girişi. Motor (src/) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/jordan/jordan start --input /yol/klipler
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
SCRATCH = KULE / "scratch"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

VIDEO_UZANTILARI = (".mp4", ".mkv", ".avi", ".mov", ".ts")


def _config(ezme: dict | None = None) -> dict:
    y = KULE / "config.yaml"
    cfg = {}
    if y.exists():
        try:
            import yaml
            cfg = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        except Exception:                            # noqa: BLE001
            cfg = {}
    for k, v in (ezme or {}).items():                # çağıran tek tek ezebilir
        cfg[k] = {**cfg.get(k, {}), **v} if isinstance(v, dict) else v
    return cfg


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"jordan@{sha}" if sha else "jordan@?"
    except Exception:                                # noqa: BLE001
        return "jordan@?"


def film_id_uret(yol: Path) -> str:
    """Tek kural, tahmin yok: dosyanın uzantısız adı."""
    return yol.stem


def motor_kur(cfg: dict):
    """Modeli YÜKLEYEN tek yer — testler burayı değiştirir."""
    from model import Motor
    m = cfg.get("model", {})
    yol = Path(m.get("yol", "model/w8a8"))
    if not yol.is_absolute():
        yol = KULE / yol
    return Motor(yol, dtype=m.get("dtype", "bfloat16"),
                 dusunme=bool(m.get("dusunme", False)),
                 uretim=cfg.get("uretim", {})).yukle()


def tek(girdi: Girdi, kok: Path | None = None, motor=None) -> Cikti:
    """Bir klip → bir Cikti. İstisna sızdırmaz.

    `motor` verilirse yeniden kullanılır (toplu koşuda model bir kez yüklenir).
    """
    from model import BellekHatasi, CiktiBozuk, ModelHatasi
    from okuyucu import VideoHatasi, oku, parcala
    from ciftleyici import ciftle

    kok = Path(kok) if kok else OUT
    cfg = _config(girdi.config)
    t0 = time.time()
    benim_scratch = SCRATCH / girdi.film_id / girdi.bolum

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        c = ariza(girdi.film_id, sinif, str(mesaj)[:300], kanit, bolum=girdi.bolum)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    try:
        if not Path(girdi.video).exists():
            return _ariza("GIRDI_HATASI", f"video yok: {girdi.video}")
        try:
            parcalar = parcala(girdi.video, benim_scratch, cfg)
        except VideoHatasi as e:
            return _ariza("VIDEO_OKUNAMADI", e)

        try:
            if motor is None:
                motor = motor_kur(cfg)
            bloklar, kanit = oku(motor, parcalar, cfg)
            ciftler, kanit_c = ciftle(motor, bloklar, cfg)
        except BellekHatasi as e:
            return _ariza("BELLEK", e, {"parca_sayisi": len(parcalar)})
        except CiktiBozuk as e:
            return _ariza("CIKTI_BOZUK", e, {"parca_sayisi": len(parcalar)})
        except ModelHatasi as e:
            return _ariza("MODEL", e)
        except Exception as e:                       # noqa: BLE001
            return _ariza("MODEL", f"{type(e).__name__}: {e}")

        kanit |= kanit_c
        kanit |= {"model": str(cfg.get("model", {}).get("yol", "")),
                  "parca_sn": cfg.get("parca", {}).get("sure_sn"),
                  "bindirme_sn": cfg.get("parca", {}).get("bindirme_sn"),
                  "video_fps": cfg.get("video", {}).get("fps"),
                  "video_genislik": cfg.get("video", {}).get("genislik")}
        # Blok yoksa bu bir ARIZA DEĞİL: klipte gerçekten okunacak yazı yok.
        # (İçerik gerçeği ile arıza gerçeği burada ayrılır.)
        if not bloklar:
            c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                      durum="METIN_YOK", kanit=kanit)
        else:
            c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="OKUNDU",
                      bloklar=bloklar, ciftler=ciftler, kanit=kanit)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c
    finally:
        # YALNIZ Jordan'ın açtığı dizin silinir; girdi videosuna dokunulmaz.
        shutil.rmtree(benim_scratch, ignore_errors=True)


def toplu(girdi_dizini: Path, kok: Path | None = None,
          bolum: str = "cikis", config: dict | None = None) -> list[Cikti]:
    """Dizindeki her klibi işle; _TAMAM olanı atla. Model BİR KEZ yüklenir."""
    kok = Path(kok) if kok else OUT
    ogeler = sorted(p for p in Path(girdi_dizini).iterdir()
                    if p.suffix.lower() in VIDEO_UZANTILARI)
    bekleyen = [p for p in ogeler
                if not (kok / film_id_uret(p) / bolum / "_TAMAM").exists()]
    for p in ogeler:
        if p not in bekleyen:
            print(f"[atla] {film_id_uret(p)}")

    motor = None
    if bekleyen:
        try:
            motor = motor_kur(_config(config))
        except Exception as e:                       # noqa: BLE001
            print(f"[UYARI] model yuklenemedi, her film ayri denenecek: {e}")

    sonuc = []
    for p in bekleyen:
        g = Girdi(film_id=film_id_uret(p), video=str(p), bolum=bolum,
                  config=config or {})
        c = tek(g, kok, motor)
        sonuc.append(c)
        ek = (f" blok={len(c.bloklar)} satir={len(c.satirlar())}"
              f" cift={len(c.ciftler)}" if c.durum == "OKUNDU" else "")
        print(f"[{c.durum}] {g.film_id}{ek} sure={c.sure_sn}s")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jordan",
                                 description="mp4'ten jenerik okuma")
    alt = ap.add_subparsers(dest="komut", required=True)
    BOLUM_YRD = "cikis = kapanis jenerigi (STANDART) | giris = giris jenerigi"

    a = alt.add_parser("start", help="toplu: dizindeki her klibi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    a.add_argument("--model", help="config.yaml'daki model yolunu ezer")
    a.add_argument("--dtype", help="bfloat16 | float16 — config.yaml'i ezer")

    b = alt.add_parser("tek", help="tek klip")
    b.add_argument("--video", required=True)
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    b.add_argument("--model", help="config.yaml'daki model yolunu ezer")
    b.add_argument("--dtype", help="bfloat16 | float16 — config.yaml'i ezer")

    n = ap.parse_args(argv)
    m = {k: v for k, v in (("yol", n.model), ("dtype", n.dtype)) if v}
    ezme = {"model": m} if m else {}

    if n.komut == "start":
        toplu(Path(n.input), bolum=n.bolum, config=ezme)
        return 0
    try:
        g = Girdi(film_id=n.film_id, video=n.video, bolum=n.bolum, config=ezme)
    except GirdiHatasi as e:
        c = ariza(n.film_id or "?", "GIRDI_HATASI", str(e), bolum=n.bolum)
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    c = tek(g)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
