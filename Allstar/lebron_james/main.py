#!/usr/bin/env python3
"""Lebron — kare klasörünü master PNG'ye bağlar, sonra okur. Başka bir şey yapmaz.

Kule girişi. Derleyici (src/derleyici.py) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/lebron_james/lebron tek --kareler /yol --film-id X

DURUM: Faz 1 tamam — derleyici çalışıyor, okuyucu (Faz 2) bekliyor.
Okuyucu kurulmadan çağrılırsa master YAZILIR ve açık ARIZA(OKUYUCU_HAZIR_DEGIL)
dönülür. Eksik gizlenmez, GÖRÜNÜR olur.

Spec: docs/superpowers/specs/2026-08-15-allstar-lebron-kulesi-design.md
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
OUT = KULE / "out"
SCRATCH = KULE / "scratch"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402


class _ArizaSinyali(Exception):
    """İç adımlardan ARIZA'ya çevrilmek üzere yukarı atılır."""

    def __init__(self, sinif: str, mesaj: str) -> None:
        super().__init__(mesaj)
        self.sinif, self.mesaj = sinif, mesaj


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
        return f"lebron@{sha}" if sha else "lebron@?"
    except Exception:
        return "lebron@?"


def _derle(dizin: Path, film_id: str):
    """Derleyiciyi çağıran TEK yer — testler burayı değiştirir."""
    import derleyici
    return derleyici, derleyici.derle(film_id, kare_dizini=str(dizin))


_MODEL_SOR = None      # toplu koşuda model BİR KEZ yüklenir


def _model_sor(ayar: dict):
    """Modeli yükleyen TEK yer. İlk çağrıda yükler, sonra aynı `sor`'u döndürür."""
    global _MODEL_SOR
    if _MODEL_SOR is None:
        import model
        _MODEL_SOR = model.yukle(ayar, KULE)
    return _MODEL_SOR


def _oku(master_yolu: Path, bolum: str, film_id: str, ayar: dict) -> dict:
    """Okuyucuyu çağıran TEK yer — testler burayı değiştirir.

    Master bantlanır (1100 px / 120 bindirme), her bant modele sorulur, satırlar
    süzgeçlerden geçer. Bantlar kulenin scratch'ine yazılır ve iş bitince silinir
    — kule kendi açtığını kapatır.
    """
    import derleyici
    import okuyucu
    from okuyucu import Bellek, ModelYok, OkumaCoktu

    im = derleyici.kare_oku(master_yolu)
    if im is None:
        raise _ArizaSinyali("MASTER_OKUNAMADI", f"master acilamadi: {master_yolu}")

    o = ayar.get("okuyucu", {})
    ofsetler = okuyucu.bant_sinirlari(
        im.shape[0], o.get("bant_h", okuyucu.BANT_H), o.get("bindirme", okuyucu.BINDIRME))
    bant_dizini = SCRATCH / film_id / bolum
    bant_dizini.mkdir(parents=True, exist_ok=True)
    yollar = []
    try:
        for i, y in enumerate(ofsetler):
            p = bant_dizini / f"bant_{i:03d}.png"
            derleyici.yaz(p, im[y:min(y + o.get("bant_h", okuyucu.BANT_H), im.shape[0])])
            yollar.append(p)

        try:
            sor = _model_sor(o)
        except ModelYok as e:
            raise _ArizaSinyali("MODEL", str(e)) from e
        except Bellek as e:
            raise _ArizaSinyali("BELLEK", str(e)) from e

        def _kutu(p: Path):
            return derleyici.kutu_sayisi(derleyici.kare_oku(p))

        try:
            r = okuyucu.oku(yollar, sor, _kutu)
        except Bellek as e:
            raise _ArizaSinyali("BELLEK", str(e)) from e
        except ModelYok as e:
            raise _ArizaSinyali("MODEL", str(e)) from e
        except OkumaCoktu as e:
            # Hepsi patladiysa "yazi yok" DEMEK YASAK — bu ariza gercegidir.
            raise _ArizaSinyali("OKUMA_COKTU", str(e)) from e
        # Bant ofsetleri künyeye girer: hangi satır master'ın neresinden geldi.
        r["bant_y0"] = ofsetler
        return r
    finally:
        shutil.rmtree(bant_dizini, ignore_errors=True)


def tek(girdi: Girdi, kok: Path | None = None) -> Cikti:
    """Bir kare klasörü → bir Cikti (+ master.png). İstisna sızdırmaz.

    Master PNG kompozisyon başarılıysa OKUMA SONUCUNDAN BAĞIMSIZ yazılır:
    okuyucu çökse bile artefakt paylaşılır ve arızanın hangi tarafta olduğu
    (derleme mi, okuma mı) gözle görülür kalır (spec 3.2).
    """
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    hedef_kok = Path(kok) / girdi.film_id / girdi.bolum
    uretilen: list[dict] = []

    def _bitir(c: Cikti) -> Cikti:
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        return _bitir(ariza(girdi.film_id, sinif, mesaj[:300], kanit=kanit,
                            bolum=girdi.bolum, uretilen=uretilen))

    dizin = Path(girdi.kareler)
    if not dizin.is_dir():
        return _ariza("GIRDI_HATASI", f"dizin yok: {dizin}")

    # --- DERLEME -----------------------------------------------------------
    try:
        derleyici, (kanvas, manifest) = _derle(dizin, girdi.film_id)
    except Exception as e:
        return _ariza("MOTOR", f"{type(e).__name__}: {e}")

    bulunan = len(derleyici.kareler(dizin))
    acilan = int(manifest.get("kare") or 0)
    kanit = {"kare_bulunan": bulunan, "kare_kullanilan": acilan,
             "derleyici_durum": manifest.get("durum"),
             "segment": manifest.get("segment"),
             "sinif_sayimi": manifest.get("sinif_sayimi"),
             "scroll_dy_medyan": manifest.get("scroll_dy_medyan"),
             "olcum_yolu": manifest.get("olcum_yolu")}

    if kanvas is None:
        # Derleyicinin tek kelimesi ("kare_yok") ÜÇ ayrı gerçeği örtüyor.
        # Kule ayırır (spec 3.4) — Nash'in kapattığı körlüğün aynısı.
        d = manifest.get("durum")
        if d == "boy_asimi":
            return _ariza("BOY_ASIMI", f"master boyu {manifest.get('boy')} > "
                                       f"{derleyici.H_MAKS}", kanit)
        if bulunan == 0:
            return _ariza("GIRDI_HATASI", f"dizinde kare yok: {dizin}", kanit)
        ims_acilan = len(derleyici.kareleri_yukle(dizin)[0])
        if ims_acilan == 0:
            return _ariza("KARE_OKUNAMADI",
                          f"{bulunan} dosya var, hicbiri acilamadi", kanit)
        if ims_acilan < 2:
            return _ariza("GIRDI_HATASI",
                          f"baglamak icin en az 2 kare gerekli, {ims_acilan} var", kanit)
        # Kareler açıldı, derleyici geçerli segment bulamadı → İÇERİK gerçeği.
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", kanit=kanit))

    # --- MASTER YAZ (okuma sonucundan BAĞIMSIZ) ----------------------------
    hedef_kok.mkdir(parents=True, exist_ok=True)
    master_yolu = hedef_kok / "master.png"
    try:
        derleyici.yaz(master_yolu, kanvas)
    except Exception as e:
        return _ariza("MOTOR", f"master yazilamadi: {type(e).__name__}: {e}", kanit)

    uretilen = [{"tip": "master", "yol": "master.png",
                 "en": int(manifest["size"][0]), "boy": int(manifest["size"][1]),
                 "segment": manifest.get("segment"), "kare": acilan,
                 "boyut_bayt": master_yolu.stat().st_size}]

    # --- ÇÖKÜŞ DEDEKTÖRÜ ---------------------------------------------------
    # Master yazıldıktan SONRA bakılır: çıktı reddedilse bile diskte durup
    # gözle incelenebilsin ("neden çökmüş" sorusu kanıtsız kalmasın).
    kare_h = _kare_yuksekligi(derleyici, dizin)
    if kare_h and derleyici.cokmus(manifest, acilan, kare_h):
        return _ariza("COKME",
                      f"{acilan} kare tek segmente cokmus "
                      f"(boy={manifest['size'][1]} <= 2x{kare_h})", kanit)

    # --- OKUMA -------------------------------------------------------------
    ayar = girdi.config or _config()
    try:
        r = _oku(master_yolu, girdi.bolum, girdi.film_id, ayar)
    except _ArizaSinyali as e:
        return _ariza(e.sinif, e.mesaj, kanit)
    except Exception as e:
        return _ariza("OKUYUCU", f"{type(e).__name__}: {e}", kanit)

    satirlar = r.get("satirlar") or []
    kanit |= {k: r[k] for k in ("bant_n", "hata_n", "elenen_n", "kutu_durum",
                                "bant_y0") if k in r}
    # Elenen satırlar YOK EDİLMEZ, künyeye yazılır: yanlış eleme yapıyorsak
    # görünür olsun (Nash'in aynı kararı).
    if r.get("elenen"):
        kanit["elenen"] = r["elenen"][:50]

    if not satirlar:
        return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                            durum="METIN_YOK", uretilen=uretilen, kanit=kanit))
    return _bitir(Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="OKUNDU",
                        satirlar=satirlar, uretilen=uretilen, kanit=kanit))


def _kare_yuksekligi(derleyici, dizin: Path) -> int:
    """İlk açılabilen karenin yüksekliği — çöküş dedektörünün ölçeği."""
    for p in derleyici.kareler(dizin):
        im = derleyici.kare_oku(p)
        if im is not None:
            return int(im.shape[0])
    return 0


def toplu(girdi_dizini: Path, kok: Path | None = None,
          bolum: str | list[str] = "cikis") -> list[Cikti]:
    """Girdi yolundaki her alt dizini işle; _TAMAM'ı bölüm bazında atla."""
    kok = Path(kok) if kok else OUT
    girdi_dizini = Path(girdi_dizini)
    bolumler = [bolum] if isinstance(bolum, str) else list(bolum)
    ogeler = sorted(p for p in girdi_dizini.iterdir() if p.is_dir())
    sonuc = []
    for p in ogeler:
        fid = p.name
        for b in bolumler:
            if (kok / fid / b / "_TAMAM").exists():
                print(f"[atla] {fid}/{b}")
                continue
            c = tek(Girdi(film_id=fid, kareler=str(p), bolum=b), kok)
            sonuc.append(c)
            ek = f" boy={c.uretilen[0]['boy']}" if c.uretilen else ""
            print(f"[{c.durum}] {fid}/{b}{ek} sure={c.sure_sn}s"
                  + (f" ({c.sinif})" if c.sinif else ""))
    return sonuc


def _virgullu_liste(gecerliler: tuple[str, ...], ad: str):
    """argparse `type=`: 'a,b' → ['a','b'] + geçerlilik denetimi."""
    def _ayristir(deger: str) -> list[str]:
        parcalar = [p.strip() for p in deger.split(",") if p.strip()]
        if not parcalar:
            raise argparse.ArgumentTypeError(f"--{ad} bos olamaz")
        gecersiz = [p for p in parcalar if p not in gecerliler]
        if gecersiz:
            raise argparse.ArgumentTypeError(
                f"--{ad} gecersiz deger(ler) {gecersiz} — gecerli: {list(gecerliler)}")
        return list(dict.fromkeys(parcalar))
    return _ayristir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lebron", description="kareler → master PNG → metin")
    alt = ap.add_subparsers(dest="komut", required=True)

    BOLUM_YRD = ("cikis | giris — RAF ETIKETI, karar degil. Motor ikisinde de "
                 "ayni. Virgullu coklu secim olur: 'giris,cikis'. Varsayilan: cikis.")

    a = alt.add_parser("start", help="toplu: girdi yolundaki her alt dizini isle")
    a.add_argument("--input", required=True)
    a.add_argument("--bolum", type=_virgullu_liste(BOLUMLER, "bolum"), default=["cikis"],
                   help=BOLUM_YRD)

    b = alt.add_parser("tek", help="tek kare klasoru")
    b.add_argument("--kareler", required=True)
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", type=_virgullu_liste(BOLUMLER, "bolum"), default=["cikis"],
                   help=BOLUM_YRD)

    n = ap.parse_args(argv)
    if n.komut == "start":
        toplu(Path(n.input), bolum=n.bolum)
        return 0

    hata_var = False
    for b_deger in n.bolum:
        try:
            g = Girdi(film_id=n.film_id, kareler=n.kareler, bolum=b_deger)
        except GirdiHatasi as e:
            c = ariza(n.film_id, "GIRDI_HATASI", str(e), bolum=b_deger)
            c.yaz(OUT)
        else:
            c = tek(g)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        if c.durum == "ARIZA":
            hata_var = True
    return 2 if hata_var else 0


if __name__ == "__main__":
    sys.exit(main())
