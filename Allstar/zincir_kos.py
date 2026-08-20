#!/usr/bin/env python3
"""ALLSTAR ZİNCİRİ — Kobe → Nash → LeBron → Jordan, 26 film × 2 bölüm.

Girdi:  Allstar/sheriff/output/<film_id>/<bolum>/  (hazır kareler)
        /home/cagatay/Belgeler/pdfler/*.mp4        (Jordan klibi için kaynak)

Akış (bölüm başına, SIRAYLA):
  1. KOBE    sınırı bulur → sınır içindeki ardışık kareleri ve klibi yazar
  2. NASH    ana kare dizinini Kobe'den bağımsız okur
  3. LEBRON  Kobe'nin ardışık zaman serisinden master PNG kurar ve okur
  4. JORDAN  Kobe'nin kestiği klibi okur

Tasarım kararları:
  * SIRAYLA koşar — dört kule de GPU istiyor, paralel çalıştırmak VRAM
    çakışması demek. Yavaş ama güvenli.
  * DEVAM EDİLEBİLİR — çıktıda `_TAMAM` varsa o adım atlanır. Koşu kesilirse
    baştan başlamaz.
  * BİR FİLM PATLARSA ZİNCİR DURMAZ — hata kaydedilir, sıradakine geçilir.
    Gece koşusunda tek bozuk film 25 sağlamı engellememeli.
  * Her adımın çıktısı ham hâliyle log'a yazılır; sonunda özet JSON.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

KOK = Path(__file__).resolve().parent
KARE_KOK = KOK / "sheriff" / "output"
VIDEO_KOK = Path("/home/cagatay/Belgeler/pdfler")
BOLUMLER = ("giris", "cikis")

# (ad, kule dizini, çıktı kökü) — çıktı kökü _TAMAM aramak için
KULELER = ("kobe", "nash", "lebron_james", "jordan")


def log(mesaj: str, dosya) -> None:
    satir = f"[{datetime.now():%H:%M:%S}] {mesaj}"
    print(satir, flush=True)
    dosya.write(satir + "\n")
    dosya.flush()


def video_bul(film_id: str) -> Path | None:
    """Film-id'yi dosya adında geçiren mp4'ü bul."""
    for p in sorted(VIDEO_KOK.glob("*.mp4")):
        if film_id in p.name:
            return p
    return None


def tamam_mi(kule: str, film_id: str, bolum: str) -> bool:
    return (KOK / kule / "out" / film_id / bolum / "_TAMAM").is_file()


def kos(kule: str, argv: list[str], zaman_asimi: int, logf) -> dict:
    """Tek kule çağrısı. Asla exception fırlatmaz — sonucu sözlük döner."""
    komut = [str(KOK / kule / "venv" / "bin" / "python"),
             str(KOK / kule / "main.py")] + argv
    t0 = time.time()
    try:
        r = subprocess.run(komut, capture_output=True, text=True,
                           timeout=zaman_asimi, cwd=str(KOK / kule))
    except subprocess.TimeoutExpired:
        log(f"    {kule}: ZAMAN ASIMI ({zaman_asimi} sn)", logf)
        return {"ok": False, "sebep": "zaman_asimi", "sure": zaman_asimi}
    except Exception as e:                                # noqa: BLE001
        log(f"    {kule}: BASLATILAMADI {type(e).__name__}: {e}", logf)
        return {"ok": False, "sebep": f"baslatilamadi: {e}"[:200]}
    sure = time.time() - t0
    son = (r.stdout or "").strip().splitlines()
    durum = "?"
    if son:
        try:
            durum = json.loads(son[-1]).get("durum", "?")
        except Exception:                                 # noqa: BLE001
            durum = son[-1][:80]
    if r.returncode != 0:
        # ARIZA bir ÇÖKME DEĞİLDİR — kule sözleşmesi gereği arızayı sıfırdan
        # farklı çıkış koduyla bildirir (LeBron COKME'de rc=2 döner). İlk
        # sürüm bunu "script hatası" sayıp 5 sağlam ARIZA raporunu hata
        # gibi gösterdi. Kule geçerli bir durum yazdıysa ONU raporlarız.
        if durum in ("ARIZA", "METIN_YOK", "KREDI_YOK"):
            log(f"    {kule}: {durum}  ({sure:.0f} sn)", logf)
            return {"ok": True, "durum": durum, "sure": round(sure, 1)}
        hata = (r.stderr or "").strip().splitlines()
        log(f"    {kule}: rc={r.returncode} {hata[-1][:150] if hata else ''}", logf)
        return {"ok": False, "sebep": f"rc={r.returncode}", "durum": durum,
                "sure": round(sure, 1)}
    log(f"    {kule}: {durum}  ({sure:.0f} sn)", logf)
    return {"ok": True, "durum": durum, "sure": round(sure, 1)}


GERI_PAY_SN = 10.0     # Kobe'nin kendi klip payiyla ayni (main.py:GERI_PAY_SN)


def video_sure(video: Path) -> float | None:
    """ffprobe ile toplam süre. Çıkış segment ofsetini bundan türetiyoruz."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, timeout=120)
        return float((r.stdout or "").strip())
    except Exception:                                     # noqa: BLE001
        return None


def klip_kes(film_id: str, bolum: str, video: Path | None, logf) -> Path | None:
    """Kobe'nin bulduğu sınırdan jenerik penceresini kes.

    Kobe `--kareler` ile koştuğu için klip üretemiyor (klip video girdisi
    ister, ve kule ikisini birden kabul etmez). Sınırı Kobe buluyor, kesimi
    burada yapıyoruz — böylece havuz ve klip AYNI tespitten türüyor.

    Kesim `-c copy`: yeniden kodlama yok. Ölçüldü (2026-08-19) ki yeniden
    kodlanmış klip ile stream-copy klip aynı pencerede bile 43 satırın
    3'ünü değiştiriyor; kodlamaya hiç dokunmamak en az sapmalı yol.
    Başlangıçta 10 sn geri pay var — anahtar-kare yuvarlaması jeneriğin
    ilk satırını kırpmasın diye (Kobe kendi klibinde de aynı payı kullanır).
    """
    if video is None or not video.is_file():
        return None
    kj = KOK / "kobe" / "out" / film_id / bolum / "kobe.json"
    if not kj.is_file():
        return None
    try:
        d = json.loads(kj.read_text(encoding="utf-8"))
        bas = float(d.get("baslangic_sn") or 0.0)
        ham_bit = d.get("bitis_sn")
        bit = float(ham_bit) if ham_bit is not None else None
        kanit = d.get("kanit") or {}
        kare_n = float(kanit.get("kare_sayisi") or 0)
        kare_fps = float(kanit.get("kare_fps") or 0)
    except Exception:                                     # noqa: BLE001
        return None

    # ZAMAN EKSENİ — iki kez yanıldığım yer, o yüzden açıkça yazıyorum:
    #
    # Kobe'nin `baslangic_sn`'i TAM FİLMİN değil, SHERIFF'İN KESTİĞİ
    # SEGMENTİN eksenindedir. Girişte segment filmin başından başlar
    # (ofset 0), ÇIKIŞTA ise SONUNDAN geriye doğru alınır.
    #
    # Ölçüldü (GÜNEŞ, 2026-08-20): film 2751,4 sn · çıkış segmenti 960 kare
    # / 2 fps = 480 sn · Kobe bas_sn=453,5 → mutlak 2724,9 sn, yani filmin
    # bitişinden 26 sn önce. İlk sürüm 453,5'i tam filme uygulayıp yanlış
    # pencereden "sona kadar" kesti: ~38 dakikalık klip, Jordan zaman aşımı.
    ofset = 0.0
    if bolum == "cikis":
        if kare_n <= 0 or kare_fps <= 0:
            log("    klip: cikis ofseti hesaplanamadi (kare_sayisi/fps yok)", logf)
            return None
        toplam = video_sure(video)
        if toplam is None:
            return None
        ofset = max(0.0, toplam - (kare_n / kare_fps))

    bas_kes = max(0.0, ofset + bas - GERI_PAY_SN)
    sure = None if bit is None else (ofset + bit - bas_kes) + GERI_PAY_SN
    if sure is not None and sure <= 0:
        return None
    hedef = KOK / "kobe" / "out" / film_id / bolum / "jenerik_klip.mp4"
    if hedef.is_file() and hedef.stat().st_size > 0:
        return hedef
    komut = ["ffmpeg", "-y", "-v", "error", "-ss", f"{bas_kes:.3f}"]
    if sure is not None:
        komut += ["-t", f"{sure:.3f}"]
    komut += ["-i", str(video), "-an", "-c", "copy", str(hedef)]
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=600)
    except Exception as e:                                # noqa: BLE001
        log(f"    ffmpeg baslatilamadi: {e}", logf)
        return None
    if r.returncode != 0 or not hedef.is_file() or hedef.stat().st_size == 0:
        log(f"    ffmpeg rc={r.returncode}: {(r.stderr or '')[:120]}", logf)
        return None
    bitis_yazi = "sona kadar" if sure is None else f"{bas_kes + sure:.0f} sn"
    log(f"    klip: {bas_kes:.0f} sn → {bitis_yazi}"
        f" ({hedef.stat().st_size // 1024} KB)", logf)
    return hedef


def bolum_isle(film_id: str, bolum: str, logf, atla_tamam: bool) -> dict:
    sonuc: dict[str, dict] = {}
    kare_dizin = KARE_KOK / film_id / bolum
    if not kare_dizin.is_dir():
        log(f"  {bolum}: kare dizini yok, atlandi", logf)
        return {"atlandi": "kare_yok"}

    # ---- 1. KOBE -----------------------------------------------------
    # Kobe --video ve --kareler'den TAM OLARAK birini kabul eder ("kule
    # sessizce bir tarafi secmez"). Kareyle kosuyoruz; Jordan'in klibini
    # Kobe'nin BULDUGU SINIRDAN asagida biz kesiyoruz — boylece havuz ve
    # klip ayni sinirdan turer, iki ayri tespit calismaz.
    video = video_bul(film_id)
    if atla_tamam and tamam_mi("kobe", film_id, bolum):
        log(f"  {bolum}: kobe zaten TAMAM, atlandi", logf)
        sonuc["kobe"] = {"ok": True, "durum": "ATLANDI"}
    else:
        sonuc["kobe"] = kos("kobe",
                            ["tek", "--kareler", str(kare_dizin),
                             "--film-id", film_id, "--uret", "kare",
                             "--bolum", bolum], 1800, logf)

    # ---- 2. NASH -----------------------------------------------------
    # Nash Kobe'nin fallback'i degil, ana kare dizininin bagimsiz okuyucusudur.
    # Bu cagrinin Kobe havuzu/sonucuyla hicbir baglantisi olmamali.
    if atla_tamam and tamam_mi("nash", film_id, bolum):
        sonuc["nash"] = {"ok": True, "durum": "ATLANDI"}
    else:
        sonuc["nash"] = kos("nash",
                            ["tek", "--kareler", str(kare_dizin),
                             "--film-id", film_id, "--bolum", bolum],
                            1800, logf)

    havuz = KOK / "kobe" / "out" / film_id / bolum / "kareler"
    if not havuz.is_dir() or not any(havuz.glob("*.png")):
        nash_durum = sonuc.get("nash", {}).get("durum", "sonuclandi")
        log(f"  {bolum}: kobe havuzu bos — lebron/jordan atlandi; "
            f"nash bagimsiz ele alindi ({nash_durum})", logf)
        return sonuc

    # ---- 3. LEBRON ---------------------------------------------------
    if atla_tamam and tamam_mi("lebron_james", film_id, bolum):
        sonuc["lebron"] = {"ok": True, "durum": "ATLANDI"}
    else:
        sonuc["lebron"] = kos("lebron_james",
                              ["tek", "--kareler", str(havuz),
                               "--film-id", film_id, "--bolum", bolum],
                              1800, logf)

    # ---- 4. JORDAN ---------------------------------------------------
    # Jordan yalniz --video alir. TAM bolumu vermek 40+ dk surer (olculdu
    # 2026-08-19: 102 sn'lik klip 67 sn); o yuzden Kobe'nin sinirindan
    # jenerik penceresini kesiyoruz.
    klip = klip_kes(film_id, bolum, video, logf)
    if klip is None:
        log(f"  {bolum}: klip kesilemedi — jordan atlandi", logf)
        sonuc["jordan"] = {"ok": False, "sebep": "klip_yok"}
    elif atla_tamam and tamam_mi("jordan", film_id, bolum):
        sonuc["jordan"] = {"ok": True, "durum": "ATLANDI"}
    else:
        sonuc["jordan"] = kos("jordan",
                              ["tek", "--video", str(klip),
                               "--film-id", film_id, "--bolum", bolum],
                              2400, logf)
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser(description="Allstar zinciri: kobe->nash->lebron->jordan")
    ap.add_argument("--film", help="yalniz bu film-id (deneme icin)")
    ap.add_argument("--bolum", choices=BOLUMLER, help="yalniz bu bolum")
    ap.add_argument("--bastan", action="store_true",
                    help="_TAMAM olsa bile yeniden kos")
    a = ap.parse_args()

    filmler = sorted(d.name for d in KARE_KOK.iterdir() if d.is_dir())
    if a.film:
        filmler = [f for f in filmler if f == a.film]
        if not filmler:
            print(f"[HATA] film bulunamadi: {a.film}")
            return 1
    bolumler = [a.bolum] if a.bolum else list(BOLUMLER)

    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_yolu = KOK / f"zincir_{damga}.log"
    ozet_yolu = KOK / f"zincir_{damga}.json"
    tumu: dict[str, dict] = {}

    with log_yolu.open("w", encoding="utf-8") as logf:
        log(f"ZINCIR BASLADI — {len(filmler)} film x {len(bolumler)} bolum", logf)
        log(f"log: {log_yolu}", logf)
        t0 = time.time()
        for i, film in enumerate(filmler, 1):
            log(f"[{i}/{len(filmler)}] {film}", logf)
            tumu[film] = {}
            for bolum in bolumler:
                try:
                    tumu[film][bolum] = bolum_isle(film, bolum, logf,
                                                   not a.bastan)
                except Exception as e:                    # noqa: BLE001
                    log(f"  {bolum}: BEKLENMEYEN {type(e).__name__}: {e}", logf)
                    tumu[film][bolum] = {"hata": f"{type(e).__name__}: {e}"[:200]}
                ozet_yolu.write_text(json.dumps(tumu, ensure_ascii=False,
                                                indent=1), encoding="utf-8")
        gecen = time.time() - t0
        log(f"ZINCIR BITTI — {gecen/60:.0f} dakika", logf)

        sayac: dict[str, int] = {}
        for film in tumu.values():
            for bolum in film.values():
                for kule, r in (bolum or {}).items():
                    if isinstance(r, dict):
                        anahtar = f"{kule}:{r.get('durum') or r.get('sebep') or '?'}"
                        sayac[anahtar] = sayac.get(anahtar, 0) + 1
        log("--- OZET ---", logf)
        for k in sorted(sayac):
            log(f"  {k}: {sayac[k]}", logf)
        log(f"ozet json: {ozet_yolu}", logf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
