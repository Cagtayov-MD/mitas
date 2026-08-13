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

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

KUYRUK_SN, KARE_FPS, KALITE = 600, 2, 3      # config.yaml varsayılanları
GERI_PAY_SN = 10          # artefakt onset'ten bu kadar ÖNCE başlar
URET_TIPLERI = ("yok", "kare", "klip")


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


def kare_havuzu_yaz(kaynak: Path, hedef: Path, ilk_kare: int) -> int:
    """Kaynak dizindeki `ilk_kare`'den sonuna kadar olan kareleri hedefe KOPYALA.

    Kopyalar, taşımaz: kaynak dışarıdan verilmiş olabilir ve Kobe kendi
    yaratmadığına dokunmaz (tek-yazar ilkesi). Dosya adları korunur —
    `motor._kare_no()` addaki sayıyı mutlak kare numarası olarak okur.
    """
    import motor
    hedef.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in motor.kareler(str(kaynak)):
        if motor._kare_no(p) >= ilk_kare:
            shutil.copy2(p, hedef / Path(p).name)
            n += 1
    return n


def klip_kes(video: str, hedef: Path, bas_sn: float) -> Path:
    """bas_sn'den filmin SONUNA kadar SESSİZ klip. Testler burayı değiştirir.

    `-c:v copy` yeniden kodlamaz (hızlı, kayıpsız) ama `-ss` girdi tarafında
    olduğu için en yakın keyframe'e GERİ yaslanır. Bu kabul edilebilir: kayma
    daima ERKEN yöndedir ve zaten GERI_PAY_SN payı var. Erken zararsız, geç
    cast kaybettirir (üretim asimetrisi).
    """
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_suffix(".mp4.tmp")
    # -f mp4 ZORUNLU: gecici dosya ".mp4.tmp" ile bitiyor, ffmpeg uzantidan
    # format cikaramiyor ("Unable to choose an output format"). Atomik yazim
    # icin gecici ad sart, o yuzden format acikca verilir.
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{bas_sn:.3f}",
                        "-i", video, "-c:v", "copy", "-an",
                        "-movflags", "+faststart", "-f", "mp4", str(gecici)],
                       capture_output=True, text=True, timeout=1800)
    if not gecici.exists() or gecici.stat().st_size == 0:
        gecici.unlink(missing_ok=True)
        raise RuntimeError(f"klip kesilemedi (rc={r.returncode}): "
                           f"{r.stderr.strip()[:200]}")
    os.replace(gecici, hedef)
    return hedef


def _tespit(dizin: str, config: dict):
    """Motoru çağıran TEK yer — testler burayı değiştirir."""
    import motor
    m = config.get("motor", {})
    return motor.tespit_v5(dizin, fps=m.get("fps", 25.0),
                           stride=m.get("stride", 2),
                           ocr_stride=m.get("ocr_stride", 2))


def _artefakt_uret(uret: str, girdi: Girdi, dizin: Path, kok: Path,
                   onset_kare: int, pencere_ss: float) -> dict:
    """İstenen artefaktı üret → `uretilen` künyesi.

    İkisi de onset'ten GERI_PAY_SN önce başlar; aynı jeneriğin iki temsili
    farklı yerden başlarsa kıyas bozulur.
    """
    hedef_kok = Path(kok) / girdi.film_id / girdi.bolum
    geri_kare = int(round(GERI_PAY_SN * KARE_FPS))
    if uret == "kare":
        ilk = max(1, onset_kare - geri_kare)
        havuz = hedef_kok / "kareler"
        adet = kare_havuzu_yaz(Path(dizin), havuz, ilk)
        return {"tip": "kare", "yol": "kareler", "adet": adet,
                "ilk_kare": ilk, "geri_pay_sn": GERI_PAY_SN}
    bas_sn = max(0.0, pencere_ss + onset_kare / KARE_FPS - GERI_PAY_SN)
    p = klip_kes(girdi.video, hedef_kok / "klip" / "klip.mp4", bas_sn)
    return {"tip": "klip", "yol": "klip/klip.mp4", "baslangic_sn": round(bas_sn, 2),
            "sessiz": True, "geri_pay_sn": GERI_PAY_SN,
            "boyut_bayt": p.stat().st_size if p.exists() else 0}


def tek(girdi: Girdi, kok: Path | None = None, uret: str = "yok") -> Cikti:
    """Bir film → bir Cikti (+ istenirse artefakt). İstisna sızdırmaz.

    `uret`: "yok" (varsayılan, yalnız karar) | "kare" (kare havuzu) |
    "klip" (sessiz mp4). Artefakt DAİMA onset'ten GERI_PAY_SN önce başlar ve
    filmin sonuna kadar sürer. Yalnız `BULUNDU` durumunda üretilir.
    """
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    benim_scratch: Path | None = None
    pencere_ss = 0
    def _ariza(sinif: str, mesaj: str) -> Cikti:
        """Tek arıza çıkış noktası — sure/surum atlanmasın, yazım unutulmasın."""
        c = ariza(girdi.film_id, sinif, mesaj[:300], bolum=girdi.bolum)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    if girdi.bolum == "giris":
        # GIRIS JENERIGI HENUZ DESTEKLENMIYOR — ve bu bilerek GORUNUR bir
        # arizadir. Motorun temel ayraci (motor.py SON_ERISIM=0.82: "aday
        # pencerenin son %18'ine ULASMALI, yoksa kredi degildir") giris
        # jenerigi icin TERS calisir: giristen sonra film HER ZAMAN devam eder.
        # Motoru giris karelerine dogrultmak neredeyse her filme KREDI_YOK
        # dedirtir - emin, sessiz ve sistematik olarak yanlis. Ayrica giris
        # icin ne olcum yatagi (havuz_kur.sh TAIL_S=600 -> yalniz son 10 dk)
        # ne de dogrulanmis GT var. Tahmin etmektense ariza demek dogrudur.
        return _ariza("BOLUM_HAZIR_DEGIL",
                      "giris jenerigi tespiti henuz yok. Motorun ayraci "
                      "SON_ERISIM=0.82 kapanisa ozgudur ve giriste ters calisir; "
                      "giris icin ayri GT + ayri karar mantigi gerekir "
                      "(bkz. KATALOG.md 7). Kobe tahmin etmez.")
    if uret not in URET_TIPLERI:
        return _ariza("GIRDI_HATASI", f"uret={uret!r} gecersiz — {URET_TIPLERI}")
    if uret == "klip" and not girdi.video:
        # Kare dizininden klip kesilemez. Sessizce atlamak YASAK — istenen
        # cikti uretilemiyorsa bu gizlenmez.
        return _ariza("GIRDI_HATASI",
                      "klip icin video gerekli; --kareler ile klip kesilemez")
    try:
        if girdi.video:
            benim_scratch = Path(SCRATCH) / girdi.film_id
            try:
                dizin, pencere_ss = kare_cikar(girdi.video, benim_scratch)
            except Exception as e:
                return _ariza("KARE_CIKARIM", str(e))
        else:
            dizin = Path(girdi.kareler)

        try:
            r = _tespit(str(dizin), girdi.config)
        except Exception as e:
            return _ariza("MOTOR", f"{type(e).__name__}: {e}")

        n = len(list(Path(dizin).glob("*.png"))) or len(list(Path(dizin).glob("*.jpg")))
        kanit = {"kare_sayisi": n, "kare_fps": float(KARE_FPS),
                 "pencere_baslangic_sn": float(pencere_ss),
                 "yontem": getattr(r, "yontem", ""),
                 "ocr_hata": getattr(r, "ocr_hata", 0)}
        if r.start_frame == -1:
            c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                      durum="KREDI_YOK", kanit=kanit)
        else:
            c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="BULUNDU",
                      baslangic_kare=int(r.start_frame),
                      baslangic_sn=round(pencere_ss + r.start_frame / KARE_FPS, 2),
                      guven=round(float(getattr(r, "guven", 0.0)), 3),
                      script=getattr(r, "script", "en"), kanit=kanit)
            # Artefakt — kobe.json'dan ONCE uretilir, cunku `yaz()` _TAMAM'i
            # basar ve tuketici kurali "_TAMAM varsa her sey hazir"dir.
            if uret != "yok":
                try:
                    c.uretilen = _artefakt_uret(uret, girdi, dizin, kok,
                                                int(r.start_frame), pencere_ss)
                except Exception as e:
                    return _ariza(f"URETIM_{uret.upper()}",
                                  f"{type(e).__name__}: {e}")
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c
    finally:
        # YALNIZ Kobe'nin actigi dizin silinir. Disaridan verilen kare
        # dizinine asla dokunulmaz (tek-yazar ilkesi).
        if benim_scratch is not None:
            shutil.rmtree(benim_scratch, ignore_errors=True)


def toplu(girdi_dizini: Path, kareler_modu: bool, kok: Path | None = None,
          uret: str = "yok", bolum: str = "cikis") -> list[Cikti]:
    """Girdi yolundaki her öğeyi işle; _TAMAM olanı atla (kaldığı yerden devam)."""
    kok = Path(kok) if kok else OUT
    girdi_dizini = Path(girdi_dizini)
    ogeler = sorted(p for p in girdi_dizini.iterdir()
                    if (p.is_dir() if kareler_modu else p.suffix.lower()
                        in (".mp4", ".mkv", ".avi", ".mov", ".ts")))
    sonuc = []
    for p in ogeler:
        fid = film_id_uret(p, kareler_modu)
        if (kok / fid / bolum / "_TAMAM").exists():
            print(f"[atla] {fid}")
            continue
        g = Girdi(film_id=fid, bolum=bolum,
                  **({"kareler": str(p)} if kareler_modu else {"video": str(p)}))
        c = tek(g, kok, uret)
        sonuc.append(c)
        ek = f" {c.uretilen['tip']}={c.uretilen['yol']}" if c.uretilen else ""
        print(f"[{c.durum}] {fid} kare={c.baslangic_kare} sure={c.sure_sn}s{ek}")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kobe", description="jenerik baslangic tespiti")
    alt = ap.add_subparsers(dest="komut", required=True)

    BOLUM_YRD = ("cikis = kapanis jenerigi (STANDART, calisir) | "
                 "giris = giris jenerigi — HENUZ YOK, acik ARIZA doner")
    URET_YRD = ("istege bagli artefakt: 'kare' = kare havuzu, 'klip' = SESSIZ "
                f"mp4. Ikisi de onset'ten {GERI_PAY_SN} sn ONCE baslar ve "
                "filmin sonuna kadar surer. 'klip' video girdisi ister.")

    a = alt.add_parser("start", help="toplu: girdi yolundaki her ogeyi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--kareler", action="store_true",
                   help="girdi yolu hazir kare dizinleri iceriyor")
    a.add_argument("--uret", choices=URET_TIPLERI, default="yok", help=URET_YRD)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--video")
    b.add_argument("--kareler")
    b.add_argument("--film-id", required=True)
    b.add_argument("--uret", choices=URET_TIPLERI, default="yok", help=URET_YRD)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)

    n = ap.parse_args(argv)
    if n.komut == "start":
        toplu(Path(n.input), n.kareler, uret=n.uret, bolum=n.bolum)
        return 0
    try:
        g = Girdi(film_id=n.film_id, video=n.video, kareler=n.kareler,
                  bolum=n.bolum)
    except GirdiHatasi as e:
        c = ariza(n.film_id, "GIRDI_HATASI", str(e), bolum=n.bolum)
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    c = tek(g, uret=n.uret)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
