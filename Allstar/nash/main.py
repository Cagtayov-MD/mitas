#!/usr/bin/env python3
"""Nash — ham kare havuzundan jenerik metnini okur. Başka hiçbir şey yapmaz.

Kule girişi. src/ burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/nash/nash tek --kareler /yol/frames/cikis --film-id <id>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

# secim.hata etiketi → (durum, ariza_sinifi). Tek harita, dağıtık if yok.
# 'havuz_bos' ICERIK GERCEGI'dir (kareler okundu, hepsi iceriksiz) —
# 'kare_okunamadi' ARIZA'dir (kareler var, hicbiri acilamadi). Bugun uretimde
# bu ikisi ayni kutuda; kule ayirir (spec 3.1).
_HATA_HARITA = {
    "dizin_bos": ("ARIZA", "GIRDI_HATASI"),
    "kare_okunamadi": ("ARIZA", "KARE_OKUNAMADI"),
    "havuz_bos": ("METIN_YOK", None),
}
_HATA_MESAJ = {
    "dizin_bos": "kare dizini yok veya desene uyan dosya yok",
    "kare_okunamadi": "kareler var ama hicbiri acilamadi (bozuk PNG / izin / yarim yazim)",
}


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
        return f"nash@{sha}" if sha else "nash@?"
    except Exception:
        return "nash@?"


def okuyucu_kur(cfg: dict):
    """Modeli BİR KEZ yükle → `sor(png) -> str`. Toplu koşuda tek çağrılır.

    Faz 1'de src/model.py henüz YOK — bu bilerek görünür bir eksiktir. Kule
    tahmin etmez: model katmanı kurulmadan çağrılırsa ARIZA(MODEL) döner ve
    diske yazılır (Kobe'nin `--bolum giris` deseni).
    """
    import model  # noqa: F401  — Faz 2
    return model.yukle(cfg.get("okuma", {}), KULE)


def tek(girdi: Girdi, kok: Path | None = None, sor=None,
        cfg: dict | None = None) -> Cikti:
    """Bir film → bir Cikti. İstisna sızdırmaz; her yolda diske yazar."""
    import secim as secim_mod
    kok = Path(kok) if kok else OUT
    cfg = cfg if cfg is not None else _config()
    t0 = time.time()

    def _bitir(c: Cikti) -> Cikti:
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        return _bitir(ariza(girdi.film_id, sinif, mesaj[:300], kanit,
                            bolum=girdi.bolum))

    s_cfg = {**(cfg.get("secim") or {}), **(girdi.config.get("secim") or {})}
    ayar = s_cfg.get(girdi.bolum) or {}
    desen = s_cfg.get("desen", "*.png")

    try:
        s = secim_mod.sec(Path(girdi.kareler), ayar, desen)
    except Exception as e:  # noqa: BLE001 — secim cokerse bu bir ARIZA'dir
        return _ariza("GIRDI_HATASI", f"{type(e).__name__}: {e}")

    if s.hata:
        durum, sinif = _HATA_HARITA[s.hata]
        if durum == "ARIZA":
            return _ariza(sinif, _HATA_MESAJ[s.hata], s.kanit)
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", kanit=s.kanit))

    # ── okuma ────────────────────────────────────────────────────────────────
    import okuyucu as ok_mod
    if sor is None:
        try:
            sor = okuyucu_kur(cfg)
        except ok_mod.Bellek as e:
            # OOM MODEL HATASI DEGIL. Genel except'in altinda kalirsa
            # ARIZA(MODEL) olur ve "caresi parca kucultmek" bilgisi kaybolur.
            # Gercek kosuda yakalandi (LA SEGUA/giris, 2026-08-14): kart baska
            # bir surec tarafindan doluydu, kule "model bozuk" diye rapor etti.
            return _ariza("BELLEK", f"model yuklenirken OOM: {e}", s.kanit)
        except ok_mod.ModelYok as e:
            return _ariza("MODEL", str(e), s.kanit)
        except ImportError as e:
            return _ariza("MODEL",
                          f"model katmani kurulmadi (Faz 2 bekliyor): {e}", s.kanit)
        except Exception as e:  # noqa: BLE001
            return _ariza("MODEL", f"{type(e).__name__}: {e}", s.kanit)

    o_cfg = {**(cfg.get("okuma") or {}), **(girdi.config.get("okuma") or {})}
    try:
        satirlar, o_kanit = ok_mod.oku(
            s.yollar, sor, float(o_cfg.get("dedup_esigi", 0.92)))
    except ok_mod.Bellek as e:
        return _ariza("BELLEK", f"CUDA OOM — caresi parca kucultmek: {e}", s.kanit)
    except ok_mod.ModelYok as e:
        return _ariza("MODEL", str(e), s.kanit)
    except Exception as e:  # noqa: BLE001
        return _ariza("MODEL", f"{type(e).__name__}: {e}", s.kanit)

    kanit = {**s.kanit, **o_kanit}
    if not satirlar:
        # Model konustu ama tek satir cikmadi → icerik gercegi.
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", kanit=kanit))

    _, sebep = ok_mod.saglik([s["text"] for s in satirlar], o_cfg.get("saglik"))
    kanit["saglik"] = sebep
    # SAGLIK BIR BAYRAKTIR, HUKUM DEGIL — uretimde de oyle
    # (_pipe_track_kunye manifest'e yazar, icerigi korur). Tek istisna:
    #
    #   garble_yuksek → ARIZA(CIKTI_BOZUK). Cunku elimizdeki metin YANLIS;
    #     asagi akisa birakmak kunyeyi zehirler (rodeo vakasi: iki kol da
    #     coktugu icin "Kubrick/Godfather" uydurmalari kunyeye girdi).
    #   cok_kisa → YALNIZ kanita yazilir. Kisa olmasi yanlis olmasi demek
    #     degildir; 5 satirlik gercek bir jenerik ARIZA'ya cevrilirse icerik
    #     gercegi arizaya kurban gider — sozlesmenin yasakladigi seyin aynasi.
    if sebep == "garble_yuksek":
        return _ariza("CIKTI_BOZUK",
                      "okuma garble: alfanumerik oran esigin altinda", kanit)

    return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                        durum="OKUNDU", satirlar=satirlar, kanit=kanit))


def toplu(girdi_dizini: Path, kok: Path | None = None,
          bolum: str = "cikis") -> list[Cikti]:
    """Her kare dizinini işle; `_TAMAM` olanı atla. Model BİR KEZ yüklenir."""
    kok = Path(kok) if kok else OUT
    cfg = _config()
    ogeler = sorted(p for p in Path(girdi_dizini).iterdir() if p.is_dir())
    bekleyen = [p for p in ogeler if not (kok / p.name / bolum / "_TAMAM").exists()]
    for p in ogeler:
        if p not in bekleyen:
            print(f"[atla] {p.name}")

    sor = None
    if bekleyen:
        try:
            sor = okuyucu_kur(cfg)
        except Exception as e:  # noqa: BLE001 — her filme ayni ARIZA yazilacak
            print(f"[!] okuyucu kurulamadi: {type(e).__name__}: {e}")

    sonuc = []
    for p in bekleyen:
        c = tek(Girdi(film_id=p.name, kareler=str(p), bolum=bolum), kok, sor, cfg)
        sonuc.append(c)
        n = len(c.satirlar)
        ek = f" sinif={c.sinif}" if c.durum == "ARIZA" else ""
        print(f"[{c.durum}] {p.name} satir={n} sure={c.sure_sn}s{ek}")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="nash",
                                 description="ham kare havuzundan jenerik okuma")
    alt = ap.add_subparsers(dest="komut", required=True)
    BOLUM_YRD = "cikis = kapanis jenerigi (varsayilan) | giris = giris jenerigi"

    a = alt.add_parser("start", help="toplu: girdi yolundaki her kare dizinini isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--kareler", required=True)
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", choices=BOLUMLER, default="cikis", help=BOLUM_YRD)

    n = ap.parse_args(argv)
    if n.komut == "start":
        toplu(Path(n.input), bolum=n.bolum)
        return 0
    try:
        g = Girdi(film_id=n.film_id, kareler=n.kareler, bolum=n.bolum)
    except GirdiHatasi as e:
        c = ariza(n.film_id, "GIRDI_HATASI", str(e), bolum=n.bolum)
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    c = tek(g)
    print(json.dumps(c.sozluk(), ensure_ascii=False))
    return 2 if c.durum == "ARIZA" else 0


if __name__ == "__main__":
    sys.exit(main())
