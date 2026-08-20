#!/usr/bin/env python3
"""Jordan — video veya manifestli kare havuzu girer, yazı çıkar.

Kule girişi. Motor (src/) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/jordan/jordan start --input /yol/klipler
"""
from __future__ import annotations

import argparse
import hashlib
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
    # 27B'nin ihtiyatlı pilot grup boyu backend'e özeldir. Bu değer tek başına
    # VRAM garantisi değildir; Sheriff ayrıca exclusive rezervasyon yapmalıdır.
    # Çağıran açıkça --grup-kare verdiyse bu varsayılanı doğal olarak ezer.
    grup_ezildi = "kare_sayisi" in ((ezme or {}).get("grup", {}) or {})
    if (str(cfg.get("model", {}).get("backend", "transformers")).lower() == "llama_mtmd"
            and not grup_ezildi):
        cfg.setdefault("grup", {})["kare_sayisi"] = int(
            cfg.get("llama_mtmd", {}).get("grup_kare", 6))
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
    m = cfg.get("model", {})
    backend = str(m.get("backend", "transformers")).strip().lower()
    if backend == "llama_mtmd":
        from model_27b import LlamaMtmdMotor
        l = cfg.get("llama_mtmd", {})
        return LlamaMtmdMotor(
            l.get("model", ""), mmproj=l.get("mmproj", ""),
            llama_cli=l.get("binary", ""),
            timeout_s=int(l.get("timeout_s", 600)),
            max_new_tokens=int(l.get("max_new_tokens", 1024)),
            image_min_tokens=l.get("image_min_tokens"),
            image_max_tokens=l.get("image_max_tokens"),
            gpu_layers=int(l.get("gpu_layers", 99)),
            oom_retry=int(l.get("oom_retry", 1)),
            retry_cooldown_s=float(l.get("retry_cooldown_s", 2.0)),
        ).yukle()
    if backend != "transformers":
        from model import ModelHatasi
        raise ModelHatasi(f"bilinmeyen model.backend: {backend}")

    from model import Motor
    yol = Path(m.get("yol", "model/qwen2.5-vl-7b"))
    if not yol.is_absolute():
        yol = KULE / yol
    # `gorsel` islemci butcesidir (min_pixels/max_pixels). Gecirilmezse model
    # varsayilani yurur — olculen kazanan kurulumdan 12 kat genis bir tavan.
    return Motor(yol, dtype=m.get("dtype", "float16"),
                 dusunme=bool(m.get("dusunme", False)),
                 uretim=cfg.get("uretim", {}),
                 gorsel=cfg.get("gorsel", {})).yukle()


def tek(girdi: Girdi, kok: Path | None = None, motor=None) -> Cikti:
    """Bir video/kare havuzu → bir Cikti. İstisna sızdırmaz.

    `motor` verilirse yeniden kullanılır (toplu koşuda model bir kez yüklenir).
    """
    from model import BellekHatasi, CiktiBozuk, ModelHatasi
    from okuyucu import VideoHatasi, kare_havuzu, oku, parcala
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
        kaynak = Path(girdi.kareler or girdi.video)
        if not kaynak.exists():
            return _ariza("GIRDI_HATASI", f"girdi yok: {kaynak}")
        try:
            if girdi.kareler:
                if not kaynak.is_dir():
                    return _ariza("GIRDI_HATASI", f"kare havuzu dizin degil: {kaynak}")
                gruplar = kare_havuzu(
                    girdi.kareler, benim_scratch, cfg, bolum=girdi.bolum)
            else:
                if not kaynak.is_file():
                    return _ariza("GIRDI_HATASI", f"video dosya degil: {kaynak}")
                gruplar = parcala(girdi.video, benim_scratch, cfg)
        except VideoHatasi as e:
            sinif = "KARE_HAVUZU_OKUNAMADI" if girdi.kareler else "VIDEO_OKUNAMADI"
            return _ariza(sinif, e)

        try:
            if motor is None:
                motor = motor_kur(cfg)
            bloklar, kanit = oku(motor, gruplar, cfg)
            if cfg.get("ciftleme_atla"):
                ciftler, kanit_c = [], {"cift_sayisi": 0, "cift_eleme": 0, "cift_atlandi": 1}
            else:
                ciftler, kanit_c = ciftle(motor, bloklar, cfg)
        except BellekHatasi as e:
            return _ariza("BELLEK", e, {"grup_sayisi": len(gruplar)})
        except CiktiBozuk as e:
            return _ariza("CIKTI_BOZUK", e, {"grup_sayisi": len(gruplar)})
        except ModelHatasi as e:
            return _ariza("MODEL", e)
        except Exception as e:                       # noqa: BLE001
            return _ariza("MODEL", f"{type(e).__name__}: {e}")

        kanit |= kanit_c
        istem_anahtari = str(getattr(motor, "istem_anahtari", "okuma"))
        istem = str(cfg.get("istem", {}).get(istem_anahtari)
                    or cfg.get("istem", {}).get("okuma", ""))
        kanit |= {"model": str(getattr(motor, "yol", cfg.get("model", {}).get("yol", ""))),
                  "model_backend": str(cfg.get("model", {}).get("backend", "transformers")),
                  "girdi_modu": "frame_pool" if girdi.kareler else "video",
                  "grup_kare": cfg.get("grup", {}).get("kare_sayisi"),
                  "bindirme_kare": cfg.get("grup", {}).get("bindirme_kare"),
                  "video_fps": cfg.get("video", {}).get("fps"),
                  "video_genislik": cfg.get("video", {}).get("genislik"),
                  "istem_sha256": hashlib.sha256(istem.encode("utf-8")).hexdigest()}
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
        # YALNIZ Jordan'ın açtığı dizin silinir; dış girdiye dokunulmaz.
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
                                 description="video veya kare havuzundan jenerik okuma")
    alt = ap.add_subparsers(dest="komut", required=True)
    BOLUM_YRD = "cikis = kapanis jenerigi (STANDART) | giris = giris jenerigi"

    a = alt.add_parser("start", help="toplu: dizindeki her klibi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    a.add_argument("--model", help="config.yaml'daki model yolunu ezer")
    a.add_argument("--dtype", help="bfloat16 | float16 — config.yaml'i ezer")
    a.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    b = alt.add_parser("tek", help="tek klip")
    kaynak = b.add_mutually_exclusive_group(required=True)
    kaynak.add_argument("--video", help="bağımsız/geriye uyumlu video girdisi")
    kaynak.add_argument("--kareler", help="frames.jsonl içeren doğrulanmış kare havuzu")
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)
    b.add_argument("--model", help="config.yaml'daki model yolunu ezer")
    b.add_argument("--dtype", help="bfloat16 | float16 — config.yaml'i ezer")
    b.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")
    for alt_ap in (a, b):        # config supurmesi icin ezme bayraklari
        alt_ap.add_argument("--backend", choices=("transformers", "llama_mtmd"),
                            help="model calisma zamani; varsayilan config.yaml")
        alt_ap.add_argument("--suzgec", help="video.suzgec'i ezer (ffmpeg -vf)")
        alt_ap.add_argument("--fps", type=float, help="video.fps'i ezer")
        alt_ap.add_argument("--grup-kare", type=int,
                            help="tek model cagrisindaki ayri resim sayisi")
        alt_ap.add_argument("--bindirme-kare", type=int,
                            help="komsu resim gruplarinin ortak kare sayisi")
        alt_ap.add_argument("--greedy", action="store_true",
                            help="ornekleme kapali: do_sample=False, temperature=0")
        alt_ap.add_argument("--ciftlemesiz", action="store_true",
                            help="gecis 2'yi (rol/isim eslestirme) atla")
        alt_ap.add_argument("--ciftle", action="store_true",
                            help="varsayilan kapali metin-only rol/isim gecisini ac")
        alt_ap.add_argument("--mmproj", help="llama_mtmd mmproj yolunu ezer")
        alt_ap.add_argument("--llama-cli", help="llama-mtmd-cli yolunu ezer")
        alt_ap.add_argument("--image-min-tokens", type=int,
                            help="llama_mtmd resim basina alt token butcesi")
        alt_ap.add_argument("--image-max-tokens", type=int,
                            help="llama_mtmd resim basina ust token butcesi")

    n = ap.parse_args(argv)
    m = {k: v for k, v in (("backend", n.backend), ("dtype", n.dtype)) if v}
    llama = {k: v for k, v in (
        ("mmproj", n.mmproj), ("binary", n.llama_cli),
        ("image_min_tokens", n.image_min_tokens),
        ("image_max_tokens", n.image_max_tokens),
    ) if v is not None}
    if n.model:
        if n.backend == "llama_mtmd":
            llama["model"] = n.model
        else:
            m["yol"] = n.model
    v = {k: val for k, val in (("suzgec", n.suzgec), ("fps", n.fps)) if val is not None}
    gr = {k: val for k, val in (("kare_sayisi", n.grup_kare),
                                ("bindirme_kare", n.bindirme_kare)) if val is not None}
    ur = {"do_sample": False, "temperature": 0.0} if n.greedy else {}
    ezme = {k: val for k, val in (("model", m), ("llama_mtmd", llama),
                                  ("video", v), ("grup", gr),
                                  ("uretim", ur)) if val}
    if n.ciftlemesiz:
        ezme["ciftleme_atla"] = True
    if n.ciftle:
        ezme["ciftleme_atla"] = False
    kok = Path(n.out) if n.out else None

    if n.komut == "start":
        toplu(Path(n.input), kok=kok, bolum=n.bolum, config=ezme)
        return 0
    try:
        g = Girdi(film_id=n.film_id, video=n.video or "", kareler=n.kareler or "",
                  bolum=n.bolum, config=ezme)
    except GirdiHatasi as e:
        c = ariza(n.film_id or "?", "GIRDI_HATASI", str(e), bolum=n.bolum)
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    c = tek(g, kok)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
