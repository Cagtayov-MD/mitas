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


class ConfigHatasi(RuntimeError):
    """Kule yapılandırması bozukken sessiz varsayılana düşülmez."""


class _ArizaSinyali(Exception):
    """İç adımlardan ARIZA'ya çevrilmek üzere yukarı atılır."""

    def __init__(self, sinif: str, mesaj: str) -> None:
        super().__init__(mesaj)
        self.sinif, self.mesaj = sinif, mesaj


def _config() -> dict:
    y = KULE / "config.yaml"
    if not y.exists():
        raise ConfigHatasi(f"config bulunamadi: {y}")
    try:
        import yaml
        belge = yaml.safe_load(y.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ConfigHatasi(
            f"config okunamadi: {type(exc).__name__}: {exc}") from exc
    if not isinstance(belge, dict):
        raise ConfigHatasi("config kok nesnesi sozluk olmali")
    return belge


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"lebron@{sha}" if sha else "lebron@?"
    except Exception:
        return "lebron@?"


def _derle(dizin: Path, film_id: str):
    """Kompozitörü çağıran TEK yer — testler burayı değiştirir.

    437 filmlik ölçümde seçilen birleşik motor artık kalıcı LeBron
    ``derleyici.py`` modülüdür; deneysel Magic çalışma zamanı adı değildir.
    """
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


def _model_kapat() -> None:
    """Özel Ollama ve alt süreçlerini deterministik olarak kapat."""
    global _MODEL_SOR
    if _MODEL_SOR is not None:
        kapat = getattr(_MODEL_SOR, "close", None)
        if callable(kapat):
            kapat()
        _MODEL_SOR = None


def _pid_vram_mb() -> float | None:
    try:
        probe = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"], capture_output=True,
            text=True, timeout=2, check=False)
        total = 0.0
        bulundu = False
        for line in probe.stdout.splitlines():
            alanlar = [x.strip() for x in line.split(",")]
            if len(alanlar) >= 2 and int(alanlar[0]) == os.getpid():
                total += float(alanlar[1])
                bulundu = True
        return total if bulundu else 0.0
    except Exception:
        return None


def _line_grounding_supported(sor) -> bool:
    """Sadece açıkça ilan edilmiş test/arka uç yeteneğine ikinci çağrı yap."""
    if bool(getattr(sor, "line_grounding_supported", False)):
        return True
    capabilities = getattr(sor, "capabilities", None)
    return isinstance(capabilities, dict) and bool(
        capabilities.get("line_grounding") or capabilities.get("grounding"))


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

        # Kompozisyonun zaten açtığı Paddle ile tüm piksel kapılarını önce
        # hesapla. GGUF ancak Paddle nesnesi bırakıldıktan sonra yüklenir.
        kutu_haritasi = {}
        paddle_satir_haritasi = {}
        for p in yollar:
            kanit = derleyici.paddle_satir_kaniti(derleyici.kare_oku(p))
            if kanit is None:
                kutu_haritasi[str(p)] = None
                continue
            kutu_haritasi[str(p)] = kanit["kutu_n"]
            paddle_satir_haritasi[p.name] = {
                "width": kanit["width"], "height": kanit["height"],
                "items": kanit["satirlar"],
            }
        derleyici.release_ocr_engine()
        paddle_kalinti_mb = _pid_vram_mb()

        try:
            sor = _model_sor(o)
        except ModelYok as e:
            raise _ArizaSinyali("MODEL", str(e)) from e
        except Bellek as e:
            raise _ArizaSinyali("BELLEK", str(e)) from e

        def _kutu(p: Path):
            return kutu_haritasi.get(str(p))

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
        r["paddle_release_vram_mb"] = paddle_kalinti_mb
        r["paddle_satir_haritasi"] = paddle_satir_haritasi
        if os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}:
            if _line_grounding_supported(sor):
                from proof import ground_bands
                r["grounding"], r["grounding_failures"] = ground_bands(yollar, sor)
                r["proof_strategy"] = "model_line_grounding"
            else:
                # Private Ollama'ın ``image[[...]]`` yanıtı satır kanıtı
                # değildir.  Free OCR'den sonra ona yeniden sormak hem faydasız
                # hem de sahte COMPLETE üretimine açıktı.
                r["grounding_unsupported"] = "backend_has_no_line_grounding"
                r["proof_strategy"] = "paddle_exact"
        olcum = getattr(sor, "metrics", None)
        if callable(olcum):
            r["model_olcum"] = olcum()
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
    proof_context = {"master_path": None, "manifest": None, "reading": None,
                     "input_dir": Path(girdi.kareler)}

    def _bitir(c: Cikti) -> Cikti:
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        extras = {}
        if os.environ.get("MITAS_OKUMA_V2", "").lower() in {"1", "true", "yes"}:
            from proof import build_packet, fallback_packet
            try:
                extras["lebron.okuma.json"] = build_packet(
                    film_id=girdi.film_id, section=girdi.bolum, legacy=c.sozluk(),
                    master_path=proof_context["master_path"],
                    manifest=proof_context["manifest"], reading=proof_context["reading"],
                    input_dir=proof_context["input_dir"], output_dir=hedef_kok)
            except Exception as e:  # proof, birincil Free OCR sonucunu yok edemez
                extras["lebron.okuma.json"] = fallback_packet(
                    girdi.film_id, girdi.bolum, c.sozluk(), e)
        c.yaz(kok, extras)
        return c

    def _ariza(sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
        return _bitir(ariza(girdi.film_id, sinif, mesaj[:300], kanit=kanit,
                            bolum=girdi.bolum, uretilen=uretilen))

    # Eski tamam işareti yeni koşu boyunca tüketiciyi yanıltmasın. Master
    # korunur; yeni sonuç yalnız ``uretilen`` künyesiyle yayımlanır.
    try:
        for eski in ("_TAMAM", "lebron.txt", "lebron.okuma.json"):
            (hedef_kok / eski).unlink(missing_ok=True)
    except OSError as exc:
        return _ariza("CIKTI", f"eski cikti gecersizlestirilemedi: {exc}")

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
             "olcum_yolu": manifest.get("olcum_yolu"),
             "girdi_modu": manifest.get("girdi_modu"),
             "bicak": manifest.get("bicak"),
             "collapse_recovery": manifest.get("collapse_recovery")}

    if kanvas is None:
        # Derleyicinin tek kelimesi ("kare_yok") ÜÇ ayrı gerçeği örtüyor.
        # Kule ayırır (spec 3.4) — Nash'in kapattığı körlüğün aynısı.
        d = manifest.get("durum")
        if d == "boy_asimi":
            return _ariza("BOY_ASIMI", f"master boyu {manifest.get('boy')} > "
                                       f"{derleyici.H_MAKS}", kanit)
        if d == "cokme_kurtarma_ariza":
            # Kurtarma parçası üretilemedi — DERLEME arızasıdır, "metinsiz"
            # içerik gerçeği değildir (OkumaCoktu ile aynı ders).
            return _ariza("MOTOR", manifest.get("sebep")
                          or "cokme kurtarma parcasi uretilemedi", kanit)
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

    proof_context["master_path"] = master_yolu
    proof_context["manifest"] = manifest

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
    try:
        ayar = girdi.config or _config()
    except ConfigHatasi as exc:
        return _ariza("YAPILANDIRMA", str(exc), kanit)
    try:
        r = _oku(master_yolu, girdi.bolum, girdi.film_id, ayar)
    except _ArizaSinyali as e:
        return _ariza(e.sinif, e.mesaj, kanit)
    except Exception as e:
        return _ariza("OKUYUCU", f"{type(e).__name__}: {e}", kanit)

    proof_context["reading"] = r

    satirlar = r.get("satirlar") or []
    kanit |= {k: r[k] for k in (
        "bant_n", "hata_n", "elenen_n", "kutu_durum", "bant_y0",
        "paddle_release_vram_mb", "model_olcum") if k in r}
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
    a.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    b = alt.add_parser("tek", help="tek kare klasoru")
    b.add_argument("--kareler", required=True)
    b.add_argument("--film-id", required=True)
    b.add_argument("--bolum", type=_virgullu_liste(BOLUMLER, "bolum"), default=["cikis"],
                   help=BOLUM_YRD)
    b.add_argument("--out", help="cikti kok dizinini ezer (varsayilan: out/)")

    n = ap.parse_args(argv)
    kok = Path(n.out) if n.out else None
    if n.komut == "start":
        sonuclar = toplu(Path(n.input), kok=kok, bolum=n.bolum)
        return 2 if sonuclar and all(c.durum == "ARIZA" for c in sonuclar) else 0

    hata_var = False
    for b_deger in n.bolum:
        try:
            g = Girdi(film_id=n.film_id, kareler=n.kareler, bolum=b_deger)
        except GirdiHatasi as e:
            c = ariza(n.film_id, "GIRDI_HATASI", str(e), bolum=b_deger)
            c.yaz(kok or OUT)
        else:
            c = tek(g, kok=kok)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        if c.durum == "ARIZA":
            hata_var = True
    return 2 if hata_var else 0


if __name__ == "__main__":
    try:
        _rc = main()
    finally:
        _model_kapat()
    sys.exit(_rc)
