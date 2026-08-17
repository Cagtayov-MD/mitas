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
CIKIS = SRC / "cikis"     # E2: karar motoru — DONMUŞ, dosyaya sıfır diff
ORTAK = SRC / "ortak"     # E2: aletler — motor'un tembel importları (kutu, icerik)
SCRATCH = KULE / "scratch"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))      # giris paketi (from giris import ...)
sys.path.insert(0, str(CIKIS))    # import motor
sys.path.insert(0, str(ORTAK))    # import kutu / import icerik (motor.py içindeki
                                  # tembel importlar — dosyaya dokunmadan çözülür)

from sozlesme import BOLUMLER, Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

KUYRUK_SN, KARE_FPS, KALITE = 600, 2, 3      # config.yaml varsayılanları
GIRIS_PENCERE_SN = 240    # MITAS_OCR_HEAD değeri — 600 DEĞİL (kapanış simetrisinden uydurulmuştu)
GERI_PAY_SN = 10          # artefakt onset'ten bu kadar ÖNCE başlar
URET_TIPLERI = ("yok", "kare", "klip")


class _ArizaSinyali(Exception):
    """tek()'in iç adımlarından ARIZA'ya çevrilmek üzere yukarı atılır."""

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
        return f"kobe@{sha}" if sha else "kobe@?"
    except Exception:
        return "kobe@?"


def film_id_uret(yol: Path, kareler_modu: bool) -> str:
    """Tek kural, tahmin yok: video → uzantısız ad, kare dizini → dizin adı."""
    return yol.name if kareler_modu else yol.stem


def kare_cikar(video: str, hedef: Path, bolum: str = "cikis") -> tuple[Path, int]:
    """Bölüme duyarlı pencere çıkarımı → (dizin, pencere_baslangic_sn).

    cikis: ss = sure-KUYRUK_SN(600), sonuna kadar. Tarif havuz_kur.sh:74-78'den
    BİREBİR alınmıştır — %94.5 bu kare üretimiyle ölçüldü, DEĞİŞTİRİLMEDİ.
    giris: ss = 0, uzunluk = GIRIS_PENCERE_SN(240) — MITAS_OCR_HEAD değeri.
    """
    hedef.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", video],
                       capture_output=True, text=True, timeout=120)
    try:
        sure = int(float(p.stdout.strip()))
    except (ValueError, AttributeError):
        raise RuntimeError(f"ffprobe sure okuyamadi: {p.stderr.strip()[:200]}")
    if bolum == "giris":
        ss = 0
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-i", video,
               "-t", str(GIRIS_PENCERE_SN), "-vf", f"fps={KARE_FPS}",
               "-q:v", str(KALITE), str(hedef / "c_%05d.png")]
    else:
        ss = max(0, sure - KUYRUK_SN)
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-i", video,
               "-vf", f"fps={KARE_FPS}", "-q:v", str(KALITE),
               str(hedef / "c_%05d.png")]
    k = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
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


def kare_havuzu_yaz_secili(kaynak_yollari: list[str], hedef: Path) -> int:
    """GİRİŞ kare havuzu: `giris.havuz.sec()`'in seçtiği (ARDIŞIK OLMAYAN) tek
    tek yolları hedefe KOPYALA. `kare_havuzu_yaz`'ın aksine bir ARALIK değil,
    önceden seçilmiş bir liste alır."""
    hedef.mkdir(parents=True, exist_ok=True)
    n = 0
    for yol in kaynak_yollari:
        p = Path(yol)
        shutil.copy2(p, hedef / p.name)
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


def klip_kes_araligi(video: str, hedef: Path, bas_sn: float, bit_sn: float) -> Path:
    """GİRİŞ klibi: bas_sn'den bit_sn'e kadar SESSİZ klip — çıkıştaki gibi
    filmin SONUNA gitmez, jenerik bitince (bit_sn = sinir.bul()'un bitis_sn'i)
    durur. `-t` süre (bit_sn-bas_sn) OUTPUT tarafında verilir; `-ss` INPUT
    tarafında (hızlı seek). Testler burayı değiştirir."""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_suffix(".mp4.tmp")
    sure = max(0.0, bit_sn - bas_sn)
    # -f mp4 ZORUNLU: gecici dosya ".mp4.tmp" ile bitiyor, ffmpeg uzantidan
    # format cikaramiyor (bkz. klip_kes docstring — ayni regresyon burada da var).
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{bas_sn:.3f}",
                        "-i", video, "-t", f"{sure:.3f}", "-c:v", "copy", "-an",
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


def _artefakt_uret_cikis(uret: str, girdi: Girdi, dizin: Path, kok: Path,
                         onset_kare: int, pencere_ss: float) -> dict:
    """ÇIKIŞ artefaktı üret → `uretilen` künyesinin bir elemanı.

    İkisi de onset'ten GERI_PAY_SN önce başlar; aynı jeneriğin iki temsili
    farklı yerden başlarsa kıyas bozulur.
    """
    hedef_kok = Path(kok) / girdi.film_id / girdi.bolum
    geri_kare = int(round(GERI_PAY_SN * KARE_FPS))
    if uret == "kare":
        ilk = max(1, onset_kare - geri_kare)
        havuz = hedef_kok / "kareler"
        adet = kare_havuzu_yaz(Path(dizin), havuz, ilk)
        return {"tip": "kare", "yol": "kareler", "adet": adet, "secim": "aralik",
                "ilk_kare": ilk, "geri_pay_sn": GERI_PAY_SN}
    bas_sn = max(0.0, pencere_ss + onset_kare / KARE_FPS - GERI_PAY_SN)
    p = klip_kes(girdi.video, hedef_kok / "klip" / "klip.mp4", bas_sn)
    return {"tip": "klip", "yol": "klip/klip.mp4", "baslangic_sn": round(bas_sn, 2),
            "sessiz": True, "geri_pay_sn": GERI_PAY_SN,
            "boyut_bayt": p.stat().st_size if p.exists() else 0}


def _artefakt_uret_giris(uret: str, girdi: Girdi, dizin: Path, kok: Path,
                         sinir_sonuc: dict) -> dict:
    """GİRİŞ artefaktı üret → `uretilen` künyesinin bir elemanı.

    `sinir_sonuc`: sinir.bul()'un BULUNDU çıktısı (baslangic_*/bitis_* dolu).
    kare: (b) HAVUZ'un seçtiği kareler — ARDIŞIK ARALIK DEĞİL. klip:
    baslangic_sn-GERI_PAY_SN → bitis_sn (çıkıştaki gibi filmin sonuna GİTMEZ).
    """
    hedef_kok = Path(kok) / girdi.film_id / girdi.bolum
    if uret == "kare":
        from giris import havuz
        h = havuz.sec(str(dizin), sinir_sonuc, girdi.config)
        adet = kare_havuzu_yaz_secili(h["kareler"], hedef_kok / "kareler")
        return {"tip": "kare", "yol": "kareler", "adet": adet, "secim": "havuz",
                "taranan": h["taranan"], "elenen_footage": h["elenen_footage"],
                "dedup_temsilci": h["dedup_temsilci"]}
    bas_sn = max(0.0, sinir_sonuc["baslangic_sn"] - GERI_PAY_SN)
    bit_sn = sinir_sonuc["bitis_sn"]
    p = klip_kes_araligi(girdi.video, hedef_kok / "klip" / "klip.mp4", bas_sn, bit_sn)
    return {"tip": "klip", "yol": "klip/klip.mp4", "baslangic_sn": round(bas_sn, 2),
            "bitis_sn": round(bit_sn, 2), "sessiz": True, "geri_pay_sn": GERI_PAY_SN,
            "boyut_bayt": p.stat().st_size if p.exists() else 0}


def _uret_ayristir(uret: str) -> list[str]:
    """'kare,klip' → ['kare','klip']; sırayı korur, tekilleştirir."""
    parcalar = [p.strip() for p in (uret or "").split(",") if p.strip()]
    if not parcalar:
        parcalar = ["yok"]
    return list(dict.fromkeys(parcalar))


def _cikis_sonucu(girdi: Girdi, dizin: Path, pencere_ss: float,
                  gercek_uretler: list[str], kok: Path) -> Cikti:
    """ÇIKIŞ bölümü karar + artefakt(lar). Hata → _ArizaSinyali (tek() yakalar)."""
    try:
        r = _tespit(str(dizin), girdi.config)
    except Exception as e:
        raise _ArizaSinyali("MOTOR", f"{type(e).__name__}: {e}") from e

    n = len(list(Path(dizin).glob("*.png"))) or len(list(Path(dizin).glob("*.jpg")))
    kanit = {"kare_sayisi": n, "kare_fps": float(KARE_FPS),
             "pencere_baslangic_sn": float(pencere_ss),
             "yontem": getattr(r, "yontem", ""),
             "ocr_hata": getattr(r, "ocr_hata", 0)}
    # E1 (2026-08-17): kanıt telemetrisi — üretim (scripts/_jenerik_pool.py) manifest'in
    # `v5` alt-nesnesini bugün motor.Sonuc'tan attribute erişimiyle dolduruyordu; kule
    # CLI'dan çağrılınca bu alanlar JSON'da taşınmak zorunda. KARAR alanlarını
    # (durum/baslangic_*/guven/script) değiştirmez — yalnız kanıt genişler. Sonuc'un
    # default'larıyla aynı varsayılanlar (kredi_yok erken-dönüşünde alanlar defaultta
    # kalır — motor.py Sonuc docstring'i).
    kanit |= {"tip": getattr(r, "tip", ""),
              "scroll_orani": getattr(r, "scroll_orani", 0.0),
              "ardisik_scroll": getattr(r, "ardisik_scroll", 0),
              "son_capa": getattr(r, "son_capa", 0.0),
              "aday_sayisi": getattr(r, "aday_sayisi", 0),
              "notlar": getattr(r, "notlar", ""),
              "suphe": list(getattr(r, "suphe", []) or []),
              "suphe_geri_kare": getattr(r, "suphe_geri_kare", -1)}
    if r.start_frame == -1:
        return Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                     durum="KREDI_YOK", kanit=kanit)
    c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="BULUNDU",
              baslangic_kare=int(r.start_frame),
              baslangic_sn=round(pencere_ss + r.start_frame / KARE_FPS, 2),
              guven=round(float(getattr(r, "guven", 0.0)), 3),
              script=getattr(r, "script", "en"), kanit=kanit)
    if gercek_uretler:
        uretilen = []
        for u in gercek_uretler:
            try:
                uretilen.append(_artefakt_uret_cikis(u, girdi, dizin, kok,
                                                      int(r.start_frame), pencere_ss))
            except Exception as e:
                raise _ArizaSinyali(f"URETIM_{u.upper()}", f"{type(e).__name__}: {e}") from e
        c.uretilen = uretilen
    return c


def _giris_sonucu(girdi: Girdi, dizin: Path, pencere_ss: float,
                  gercek_uretler: list[str], kok: Path) -> Cikti:
    """GİRİŞ bölümü karar + artefakt(lar). Hata → _ArizaSinyali (tek() yakalar).

    (a) SINIR (`giris.sinir.bul`) çağrılır — motor patlarsa ARIZA(GIRIS_SINIR),
    sessizce sabit pencereye düşmek YASAK. Bulunamazsa (found=False) KREDI_YOK.
    Bulunduysa (b) HAVUZ yalnız `--uret kare` istenince çalışır (pahalı OCR).
    """
    from giris import sinir
    try:
        b = sinir.bul(str(dizin), girdi.config)
    except Exception as e:
        raise _ArizaSinyali("GIRIS_SINIR", f"{type(e).__name__}: {e}") from e

    n = len(list(Path(dizin).glob("*.png"))) or len(list(Path(dizin).glob("*.jpg")))
    kanit = dict(b.get("kanit") or {})
    kanit.update({"kare_sayisi": n, "kare_fps": float(KARE_FPS),
                  "pencere_baslangic_sn": float(pencere_ss)})
    if not b.get("bulundu"):
        return Cikti(film_id=girdi.film_id, bolum=girdi.bolum,
                     durum="KREDI_YOK", kanit=kanit)
    c = Cikti(film_id=girdi.film_id, bolum=girdi.bolum, durum="BULUNDU",
              baslangic_kare=b["baslangic_kare"], baslangic_sn=b["baslangic_sn"],
              bitis_kare=b["bitis_kare"], bitis_sn=b["bitis_sn"],
              guven=b["guven"], kanit=kanit)
    if gercek_uretler:
        uretilen = []
        for u in gercek_uretler:
            try:
                uretilen.append(_artefakt_uret_giris(u, girdi, dizin, kok, b))
            except Exception as e:
                raise _ArizaSinyali(f"URETIM_{u.upper()}", f"{type(e).__name__}: {e}") from e
        c.uretilen = uretilen
    return c


def tek(girdi: Girdi, kok: Path | None = None, uret: str = "yok") -> Cikti:
    """Bir film → bir Cikti (+ istenirse artefakt(lar)). İstisna sızdırmaz.

    `uret`: "yok" (varsayılan, yalnız karar) | tek tür ("kare"/"klip") |
    virgüllü çoklu ("kare,klip"). `uretilen` HER ZAMAN liste (tek elemanlı
    olsa bile). Yalnız `BULUNDU` durumunda üretilir.

    `girdi.bolum`: "cikis" (STANDART) motoru (`src/motor.py`) çağırır;
    "giris" `giris/sinir.py` + `giris/havuz.py`'yi çağırır (bkz.
    src/giris/TASARIM.md). İkisi bağımsız çalışır, birinin ARIZA'sı diğerini
    etkilemez (ayrı ayrı `tek()` çağrılır, CLI bunu yönetir).
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

    parcalar = _uret_ayristir(uret)
    for u in parcalar:
        if u not in URET_TIPLERI:
            return _ariza("GIRDI_HATASI", f"uret={u!r} gecersiz — {URET_TIPLERI}")
    if "yok" in parcalar and len(parcalar) > 1:
        return _ariza("GIRDI_HATASI", "'yok' baska uret turuyle birlikte kullanilamaz")
    gercek_uretler = [u for u in parcalar if u != "yok"]
    if "klip" in gercek_uretler and not girdi.video:
        # Kare dizininden klip kesilemez. Sessizce atlamak YASAK — istenen
        # cikti uretilemiyorsa bu gizlenmez.
        return _ariza("GIRDI_HATASI",
                      "klip icin video gerekli; --kareler ile klip kesilemez")
    try:
        if girdi.video:
            benim_scratch = Path(SCRATCH) / girdi.film_id
            try:
                dizin, pencere_ss = kare_cikar(girdi.video, benim_scratch, girdi.bolum)
            except Exception as e:
                return _ariza("KARE_CIKARIM", str(e))
        else:
            dizin = Path(girdi.kareler)

        try:
            if girdi.bolum == "giris":
                c = _giris_sonucu(girdi, dizin, pencere_ss, gercek_uretler, kok)
            else:
                c = _cikis_sonucu(girdi, dizin, pencere_ss, gercek_uretler, kok)
        except _ArizaSinyali as e:
            return _ariza(e.sinif, e.mesaj)

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
          uret: str = "yok", bolum: str | list[str] = "cikis") -> list[Cikti]:
    """Girdi yolundaki her öğeyi HER bölüm için işle; _TAMAM'ı bölüm bazında
    atla (kaldığı yerden devam). `bolum` tek string veya liste olabilir."""
    kok = Path(kok) if kok else OUT
    girdi_dizini = Path(girdi_dizini)
    bolumler = [bolum] if isinstance(bolum, str) else list(bolum)
    ogeler = sorted(p for p in girdi_dizini.iterdir()
                    if (p.is_dir() if kareler_modu else p.suffix.lower()
                        in (".mp4", ".mkv", ".avi", ".mov", ".ts")))
    sonuc = []
    for p in ogeler:
        fid = film_id_uret(p, kareler_modu)
        for b in bolumler:
            if (kok / fid / b / "_TAMAM").exists():
                print(f"[atla] {fid}/{b}")
                continue
            g = Girdi(film_id=fid, bolum=b,
                      **({"kareler": str(p)} if kareler_modu else {"video": str(p)}))
            c = tek(g, kok, uret)
            sonuc.append(c)
            ek = f" uretilen={','.join(u['tip'] for u in c.uretilen)}" if c.uretilen else ""
            print(f"[{c.durum}] {fid}/{b} kare={c.baslangic_kare} sure={c.sure_sn}s{ek}")
    return sonuc


def _virgullu_liste(gecerliler: tuple[str, ...], ad: str):
    """argparse `type=`: 'a,b' → ['a','b'] + geçerlilik denetimi. `choices=`
    virgüllü girdiyi anlamadığı için kendi ayrıştırıcımız gerekiyor."""
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
    ap = argparse.ArgumentParser(prog="kobe", description="jenerik baslangic tespiti")
    alt = ap.add_subparsers(dest="komut", required=True)

    BOLUM_YRD = ("cikis = kapanis jenerigi | giris = giris jenerigi. Virgullu "
                 "coklu secim olur: 'giris,cikis'. Varsayilan: cikis.")
    URET_YRD = ("istege bagli artefakt: 'kare' = kare havuzu, 'klip' = SESSIZ "
                f"mp4. Virgullu coklu secim olur: 'kare,klip'. Ikisi de "
                f"onset'ten {GERI_PAY_SN} sn ONCE baslar. 'klip' video girdisi "
                "ister. Varsayilan: yok.")

    a = alt.add_parser("start", help="toplu: girdi yolundaki her ogeyi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--kareler", action="store_true",
                   help="girdi yolu hazir kare dizinleri iceriyor")
    a.add_argument("--uret", type=_virgullu_liste(URET_TIPLERI, "uret"),
                   default=["yok"], help=URET_YRD)
    a.add_argument("--bolum", type=_virgullu_liste(BOLUMLER, "bolum"),
                   default=["cikis"], help=BOLUM_YRD)

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--video")
    b.add_argument("--kareler")
    b.add_argument("--film-id", required=True)
    b.add_argument("--uret", type=_virgullu_liste(URET_TIPLERI, "uret"),
                   default=["yok"], help=URET_YRD)
    b.add_argument("--bolum", type=_virgullu_liste(BOLUMLER, "bolum"),
                   default=["cikis"], help=BOLUM_YRD)

    n = ap.parse_args(argv)
    uret_str = ",".join(n.uret)
    if n.komut == "start":
        toplu(Path(n.input), n.kareler, uret=uret_str, bolum=n.bolum)
        return 0

    # tek: her istenen bolum icin BAGIMSIZ calisir — biri ARIZA olsa digeri
    # etkilenmez, her biri kendi out/<film>/<bolum>/kobe.json'unu yazar.
    hata_var = False
    for b_deger in n.bolum:
        try:
            g = Girdi(film_id=n.film_id, video=n.video, kareler=n.kareler,
                      bolum=b_deger)
        except GirdiHatasi as e:
            c = ariza(n.film_id, "GIRDI_HATASI", str(e), bolum=b_deger)
            c.yaz(OUT)
        else:
            c = tek(g, uret=uret_str)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        if c.durum == "ARIZA":
            hata_var = True
    return 2 if hata_var else 0


if __name__ == "__main__":
    sys.exit(main())
