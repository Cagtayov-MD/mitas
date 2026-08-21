#!/usr/bin/env python3
"""Vince Carter — video veya kare dizininden kanıtlı jenerik okuma.

Kule girişi. Motor (src/) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: ./vince start --input /yol/klipler
            ./vince tek --video /yol/klip.mp4 --film-id ornek [--bolum giris|cikis]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

KULE = Path(__file__).resolve().parent
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402
from hazirlik import (  # noqa: E402
    VideoHatasi,
    kare_dizininden_hazirla,
    kayma_hizi,
    videodan_hazirla,
)
from kanal_vlm import BellekHatasi, ModelHatasi, Motor, kos  # noqa: E402
from kanal_ocr import OcrHatasi, ocr_indeksi_uret  # noqa: E402
from birlestirici import birlestir  # noqa: E402

VIDEO_UZANTILARI = (".mp4", ".mkv", ".avi", ".mov", ".ts", ".mxf")

# Bölüm-özel eşik sözlüğü — YALNIZ burada tutulur (docs/PLAN.md §1 —
# "giriş/çıkış izolasyonu"). E1/E2 değerleri kalibre edilmiştir.
# Kural: src/ altındaki bölüm modülleri bu tabloyu KENDİLERİ okumaz / "ben giriş miyim"
# diye dallanmaz — main.py çözüp motora PARAMETRE olarak geçirir.
ESIK_GIRIS = {"E1": 0.70, "E2": 0.50}
ESIK_CIKIS = {"E1": 0.70, "E2": 0.50}


def _esik(bolum: str) -> dict:
    """Bölüme göre eşik sözlüğünü SEÇ — bu seçim YALNIZ burada yapılır."""
    return dict(ESIK_GIRIS if bolum == "giris" else ESIK_CIKIS)


def _config_yukle() -> dict:
    cfg_path = KULE / "config.yaml"
    if cfg_path.is_file():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    else:
        cfg = {}
    m = dict(cfg.get("model", {}))
    if "yol" in m and not Path(m["yol"]).is_absolute():
        m["yol"] = str((KULE / m["yol"]).resolve())
        cfg["model"] = m
    return cfg


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"vince@{sha}" if sha else "vince@?"
    except Exception:                                  # noqa: BLE001
        return "vince@?"


def film_id_uret(yol: Path) -> str:
    """Tek kural, tahmin yok: dosyanın/dizinin uzantısız adı."""
    return yol.stem


def tek(girdi: Girdi, kok: Path | None = None, motor: Motor | None = None) -> Cikti:
    """Bir video/kare dizini → bir Cikti. İstisna sızdırmaz."""
    kok = Path(kok) if kok else OUT
    t0 = time.time()

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        c = ariza(girdi.film_id, sinif, str(mesaj)[:300], kanit, bolum=girdi.bolum)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    kaynak = Path(girdi.kareler or girdi.video)
    if not kaynak.exists():
        return _ariza("GIRDI_HATASI", f"girdi yok: {kaynak}")
    if girdi.kareler and not kaynak.is_dir():
        return _ariza("GIRDI_HATASI", f"kare dizini degil: {kaynak}")
    if girdi.video and not kaynak.is_file():
        return _ariza("GIRDI_HATASI", f"video dosya degil: {kaynak}")

    cfg = _config_yukle()
    if girdi.config:
        cfg.update(girdi.config)

    # 1. Kare Hazırlığı (tek görsel reçete)
    hedef_kare_dizini = kok / girdi.film_id / girdi.bolum / "kareler"
    try:
        if girdi.video:
            manifest = videodan_hazirla(girdi.video, hedef_kare_dizini, cfg)
        else:
            manifest = kare_dizininden_hazirla(girdi.kareler, hedef_kare_dizini, cfg)
    except VideoHatasi as e:
        return _ariza("VIDEO_HATASI", str(e))
    except Exception as e:                             # noqa: BLE001
        return _ariza("VIDEO_HATASI", f"kare hazirlama hatasi: {e}")

    kare_sayisi = manifest.get("kare_sayisi", 0)
    if kare_sayisi == 0:
        c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="METIN_YOK",
                  kanit={"kare_sayisi": 0, "sebep": "hic kare yok"})
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    # 2. VLM Kanalları (Faz 0 ve Faz K)
    m_cfg = cfg.get("model", {})
    kendi_motoru = motor is None
    if kendi_motoru:
        try:
            motor = Motor(m_cfg.get("yol", str(KULE / "model/qwen3-vl-8b")),
                          dtype=str(m_cfg.get("dtype", "bfloat16")),
                          uretim=cfg.get("uretim", {}),
                          gorsel=cfg.get("gorsel"),
                          aygit=str(m_cfg.get("aygit", "cuda:0"))).yukle()
        except BellekHatasi as e:
            return _ariza("BELLEK_HATASI", str(e))
        except (ModelHatasi, Exception) as e:          # noqa: BLE001
            return _ariza("MODEL_HATASI", str(e))

    faz_kaydirma = int(cfg.get("grup", {}).get("faz_kaydirma", 4))
    try:
        faz0_sonuc = kos(manifest, hedef_kare_dizini, cfg, faz=0, motor=motor)
        fazK_sonuc = kos(manifest, hedef_kare_dizini, cfg, faz=faz_kaydirma, motor=motor)
    except BellekHatasi as e:
        return _ariza("BELLEK_HATASI", str(e))
    except (ModelHatasi, Exception) as e:              # noqa: BLE001
        return _ariza("MODEL_HATASI", str(e))
    finally:
        if kendi_motoru:
            motor.kapat()

    # 3. OCR Tanık Kanalı
    try:
        ocr_indeksi = ocr_indeksi_uret(manifest, hedef_kare_dizini, cfg=cfg)
    except OcrHatasi as e:
        return _ariza("MODEL_HATASI", f"OCR tanik hatasi: {e}")
    except Exception as e:                             # noqa: BLE001
        return _ariza("MODEL_HATASI", f"OCR kanali calistirilmadi: {e}")

    # 4. Füzyon & Birleştirici
    esikler = _esik(girdi.bolum)
    try:
        birlestirme = birlestir(manifest, ocr_indeksi, [faz0_sonuc, fazK_sonuc],
                                esikler=esikler, cfg=cfg)
    except Exception as e:                             # noqa: BLE001
        return _ariza("CIKTI_BOZUK", f"birlesim hatasi: {e}")

    satirlar = birlestirme.get("satirlar", [])
    kanit = birlestirme.get("kanit", {})
    kanit["kayma_hizi"] = kayma_hizi(manifest)
    kanit["manifest"] = {
        "kaynak": manifest.get("kaynak"),
        "kare_sayisi": kare_sayisi,
        "fps": manifest.get("fps"),
        "fps_varsayimi": manifest.get("fps_varsayimi"),
    }
    kanit["esik_secimi"] = esikler

    if not satirlar:
        c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="METIN_YOK", kanit=kanit)
    else:
        c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="OKUNDU",
                  satirlar=satirlar, kanit=kanit)

    c.sure_sn = round(time.time() - t0, 1)
    c.motor_surumu = _surum()
    c.yaz(kok)
    return c


def toplu(girdi_dizini: Path, kok: Path | None = None,
          bolum: str = "cikis") -> list[Cikti]:
    """Dizindeki her klibi işle; _TAMAM olanı atla."""
    kok = Path(kok) if kok else OUT
    girdi_p = Path(girdi_dizini)

    ogeler = []
    for p in sorted(girdi_p.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_UZANTILARI:
            ogeler.append((p, "video"))
        elif p.is_dir() and (any(p.glob("*.png")) or any(p.glob("*.jpg"))):
            ogeler.append((p, "kareler"))

    bekleyen = [
        (p, tur) for p, tur in ogeler
        if not (kok / film_id_uret(p) / bolum / "_TAMAM").exists()
    ]
    for p, _ in ogeler:
        fid = film_id_uret(p)
        if (kok / fid / bolum / "_TAMAM").exists():
            print(f"[atla] {fid}")

    cfg = _config_yukle()
    m_cfg = cfg.get("model", {})
    motor = None
    if bekleyen:
        try:
            motor = Motor(m_cfg.get("yol", str(KULE / "model/qwen3-vl-8b")),
                          dtype=str(m_cfg.get("dtype", "bfloat16")),
                          uretim=cfg.get("uretim", {}),
                          gorsel=cfg.get("gorsel"),
                          aygit=str(m_cfg.get("aygit", "cuda:0"))).yukle()
        except Exception:                              # noqa: BLE001
            motor = None

    sonuc = []
    try:
        for p, tur in bekleyen:
            fid = film_id_uret(p)
            if tur == "video":
                g = Girdi(film_id=fid, video=str(p), bolum=bolum)
            else:
                g = Girdi(film_id=fid, kareler=str(p), bolum=bolum)
            c = tek(g, kok, motor=motor)
            sonuc.append(c)
            print(f"[{c.durum}] {g.film_id} sure={c.sure_sn}s ({len(c.satirlar)} satir)")
    finally:
        if motor is not None:
            motor.kapat()

    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="vince", description="video veya kare dizininden kanitli jenerik okuma")
    alt = ap.add_subparsers(dest="komut", required=True)
    BOLUM_YRD = "cikis = kapanis jenerigi (STANDART) | giris = giris jenerigi"

    a = alt.add_parser("start", help="toplu: dizindeki her klibi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    a.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    b = alt.add_parser("tek", help="tek klip")
    kaynak = b.add_mutually_exclusive_group(required=True)
    kaynak.add_argument("--video", help="jenerik videosu")
    kaynak.add_argument("--kareler", help="hazirlanmis kare dizini")
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    b.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    n = ap.parse_args(argv)
    kok = Path(n.out) if n.out else None

    if n.komut == "start":
        toplu(Path(n.input), kok=kok, bolum=n.bolum)
        return 0

    try:
        g = Girdi(film_id=n.film_id, video=n.video, kareler=n.kareler, bolum=n.bolum)
    except GirdiHatasi as e:
        c = ariza(n.film_id or "?", "GIRDI_HATASI", str(e), bolum=n.bolum)
        c.yaz(kok or OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    c = tek(g, kok)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
