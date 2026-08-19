"""Ana havuz icin metin-kutusu tabanli kare secimi ve Paddle worker koprusu.

Bu modul jenerik siniri aramaz. Worker detection + recognition'i tek kare
acilisinda yapar; secim yalniz kutularla bos kareleri, altyaziyi ve kalici kanal
logosunu ayirir. Okunan satirlar ayni analizden temporal uzlasmaya gider; OCR
ikinci kez cagrilmaz. Paddle ayri alt surecte calisir (`metin_worker.py`).
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import havuz as havuz_mod


class DetectorArizasi(RuntimeError):
    """Detection-only worker kurulamadiginda/sonuc uretemediginde."""


def worker_komutu(detector_python, worker, girdi, cikti, cfg: dict) -> list[str]:
    """Worker CLI satırını kurar — bayrak eşlemesi test edilebilir olsun diye ayrı."""
    komut = [str(detector_python), str(worker), "--input", str(girdi),
             "--output", str(cikti), "--device", str(cfg.get("device", "gpu")),
             "--model", str(cfg.get("model", "PP-OCRv6_medium_det")),
             "--rec-model", str(cfg.get(
                 "rec_model", "latin_PP-OCRv5_mobile_rec")),
             "--rec-batch", str(int(cfg.get("rec_batch", 8))),
             "--det-thresh", str(float(cfg.get("det_thresh", 0.2))),
             "--box-thresh", str(float(cfg.get("box_thresh", 0.45))),
             "--unclip-ratio", str(float(cfg.get("unclip_ratio", 1.4)))]
    kule = Path(worker).parent.parent
    for anahtar, bayrak in (("model_dir", "--model-dir"),
                            ("rec_model_dir", "--rec-model-dir")):
        if cfg.get(anahtar):
            model_yolu = Path(str(cfg[anahtar]))
            if not model_yolu.is_absolute():
                model_yolu = kule / model_yolu
            komut.extend([bayrak, str(model_yolu)])
    if not bool(cfg.get("mkldnn", True)):
        komut.append("--no-mkldnn")
    if bool(cfg.get("kirpim_keskinlestir", False)):
        komut.append("--kirpim-keskinlestir")
    return komut


def tara(yollar: list[Path], ayar: dict | None = None) -> tuple[dict, dict]:
    """Paddle worker'i ayri surecte calistirip kare -> kutu analizini don."""
    cfg = ayar or {}
    if not yollar:
        return {}, {"detector_sure_sn": 0.0, "detector_kare": 0}
    worker = Path(__file__).with_name("metin_worker.py")
    if not worker.is_file():
        raise DetectorArizasi(f"detector worker yok: {worker}")

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="nash-det-") as gecici:
        gecici_yol = Path(gecici)
        girdi = gecici_yol / "frames.json"
        cikti = gecici_yol / "boxes.json"
        girdi.write_text(json.dumps([str(p.resolve()) for p in yollar]),
                         encoding="utf-8")
        detector_python = Path(str(cfg.get("python") or
                                   (worker.parent.parent / "detector_venv/bin/python")))
        if not detector_python.is_file():
            raise DetectorArizasi(
                f"detector ortami yok: {detector_python} — ./venv_kur.sh")
        komut = worker_komutu(detector_python, worker, girdi, cikti, cfg)
        try:
            sonuc = subprocess.run(
                komut, capture_output=True, text=True, shell=False,
                timeout=float(cfg.get("timeout_seconds", 600)))
        except subprocess.TimeoutExpired as exc:
            raise DetectorArizasi(
                f"detector {cfg.get('timeout_seconds', 600)} sn zaman asimi") from exc
        if sonuc.returncode or not cikti.is_file():
            ayrinti = (sonuc.stderr or sonuc.stdout or "sonuc dosyasi yok").strip()
            raise DetectorArizasi(
                f"detector worker rc={sonuc.returncode}: {ayrinti[-500:]}")
        try:
            belge = json.loads(cikti.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DetectorArizasi(f"detector sonucu bozuk: {exc}") from exc
    if not isinstance(belge, dict) or not isinstance(belge.get("frames"), dict):
        raise DetectorArizasi("detector sonucu frames nesnesi tasimiyor")
    meta = belge.get("meta") if isinstance(belge.get("meta"), dict) else {}
    return belge["frames"], {
        "detector_sure_sn": round(time.monotonic() - t0, 3),
        "detector_kare": len(belge["frames"]),
        "detector_model": meta.get("model"),
        "paddle_rec_model": meta.get("recognition_model"),
        "detector_device": meta.get("device"),
        "paddle_full_ocr": bool(meta.get("full_ocr")),
        "paddle_peak_vram_mb": meta.get("peak_vram_mb"),
    }


def sec(*, yollar: list[Path], griler: list | None, analizler: dict, ayar: dict,
        imza_fn: Callable | None = None) -> tuple[list[Path], dict]:
    """Detection sonucundan metin bloklari ve temsilci kareleri sec."""
    imza_fn = imza_fn or havuz_mod.imza
    kare_indeksi = {p.name: i for i, p in enumerate(yollar)}
    gri_haritasi = {p.name: g for p, g in zip(yollar, griler or [])}

    def kare_imzasi(p: Path) -> int:
        # Uretim worker'i OCR icin actigi kareden ayni dHash'i hesaplar. Bu
        # sayede ana surec yuzlerce PNG'yi yeniden decode edip RAM'de tutmaz.
        onbellek = (analizler.get(p.name) or {}).get("dhash")
        if isinstance(onbellek, int) and not isinstance(onbellek, bool):
            return onbellek
        if p.name not in gri_haritasi:
            raise DetectorArizasi(f"kare imzasi yok: {p.name}")
        return imza_fn(gri_haritasi[p.name])
    hata_n = sum(1 for p in yollar if (analizler.get(p.name) or {}).get("error"))
    basarili_n = sum(1 for p in yollar if p.name in analizler
                     and not (analizler.get(p.name) or {}).get("error"))
    if basarili_n == 0:
        raise DetectorArizasi("detector hicbir kareyi analiz edemedi")

    kalici = _kalici_logo_imzalari(yollar, analizler,
                                   float(ayar.get("logo_kalici_oran", 0.80)))
    logo_kutusu_elendi = 0
    altyazi_elendi = 0
    metinli: list[tuple[int, Path, list[list[float]]]] = []
    for p in yollar:
        analiz = analizler.get(p.name) or {}
        if analiz.get("error"):
            continue
        kutular = [_kutu_dogrula(k) for k in (analiz.get("boxes") or [])]
        kutular = [k for k in kutular if k is not None]
        temiz = []
        for kutu in kutular:
            if _logo_adayi(kutu) and _kutu_imzasi(kutu) in kalici:
                logo_kutusu_elendi += 1
                continue
            temiz.append(kutu)
        if not temiz:
            continue
        if all(_y_merkez(k) >= float(ayar.get("altyazi_y", 0.80)) for k in temiz):
            altyazi_elendi += 1
            continue
        metinli.append((kare_indeksi[p.name], p, temiz))

    bosluk = max(0, int(ayar.get("blok_bosluk", 2)))
    bloklar = _bloklara_ayir(metinli, bosluk)
    nedenler: dict[str, set[str]] = {}

    def ekle(p: Path, neden: str) -> None:
        nedenler.setdefault(p.name, set()).add(neden)

    adim = max(1, int(ayar.get("ornek_adim", 4)))
    dhash_esigi = max(1, int(ayar.get("dhash_degisim", 64)))
    for blok in bloklar:
        ekle(blok[0][1], "blok_ilk")
        ekle(blok[-1][1], "blok_son")
        son_ornek = blok[0][0]
        onceki_imza = kare_imzasi(blok[0][1])
        for indeks, p, _ in blok[1:]:
            if indeks - son_ornek >= adim:
                ekle(p, "zaman_adimi")
                son_ornek = indeks
            simdiki = kare_imzasi(p)
            if havuz_mod.hamming(onceki_imza, simdiki) >= dhash_esigi:
                ekle(p, "dhash_degisim")
            onceki_imza = simdiki

    adaylar = [p for p in yollar if p.name in nedenler]
    tavan = max(0, int(ayar.get("tavan", 100)))
    secilen = _tavana_indir(adaylar, nedenler, tavan)
    secilen_adlar = {p.name for p in secilen}
    blok_ozet = [{"bas": b[0][1].name, "son": b[-1][1].name, "kare": len(b)}
                 for b in bloklar]
    kanit = {
        "strateji": "text_run",
        "detector_basarili": basarili_n,
        "detector_hata_n": hata_n,
        "metinli_kare": len(metinli),
        "altyazi_elendi": altyazi_elendi,
        "logo_kutusu_elendi": logo_kutusu_elendi,
        "kalici_logo_imza_n": len(kalici),
        "metin_blok_n": len(bloklar),
        "metin_bloklari": blok_ozet,
        "aday_kare": len(adaylar),
        "secilen_kare": len(secilen),
        "dusurulen_n": max(0, len(adaylar) - len(secilen)),
        "tavan": tavan,
        "ornek_adim": adim,
        "dhash_degisim": dhash_esigi,
        "secim_nedenleri": {
            ad: sorted(nedenler[ad]) for ad in nedenler if ad in secilen_adlar},
    }
    return secilen, kanit


def _bloklara_ayir(metinli: list[tuple[int, Path, list]], bosluk: int) -> list[list]:
    bloklar: list[list] = []
    for kayit in metinli:
        if not bloklar or kayit[0] - bloklar[-1][-1][0] > bosluk + 1:
            bloklar.append([kayit])
        else:
            bloklar[-1].append(kayit)
    return bloklar


def _tavana_indir(adaylar: list[Path], nedenler: dict[str, set[str]],
                  tavan: int) -> list[Path]:
    if tavan <= 0 or len(adaylar) <= tavan:
        return adaylar
    oncelikli = [p for p in adaylar if nedenler[p.name] &
                 {"blok_ilk", "blok_son", "dhash_degisim"}]
    if len(oncelikli) >= tavan:
        return _duzgun_ornek(oncelikli, tavan)
    kalan = [p for p in adaylar if p not in set(oncelikli)]
    ek = _duzgun_ornek(kalan, tavan - len(oncelikli))
    return sorted(oncelikli + ek, key=lambda p: p.name)


def _duzgun_ornek(yollar: list[Path], n: int) -> list[Path]:
    if n <= 0:
        return []
    if len(yollar) <= n:
        return yollar
    if n == 1:
        return [yollar[len(yollar) // 2]]
    indeksler = {round(i * (len(yollar) - 1) / (n - 1)) for i in range(n)}
    return [yollar[i] for i in sorted(indeksler)]


def _kalici_logo_imzalari(yollar: list[Path], analizler: dict,
                           oran: float) -> set[tuple[int, ...]]:
    sayac: Counter = Counter()
    for p in yollar:
        gorulen = set()
        for ham in (analizler.get(p.name) or {}).get("boxes") or []:
            kutu = _kutu_dogrula(ham)
            if kutu is not None and _logo_adayi(kutu):
                gorulen.add(_kutu_imzasi(kutu))
        sayac.update(gorulen)
    esik = max(1, math.ceil(len(yollar) * max(0.0, min(1.0, oran))))
    return {imza for imza, adet in sayac.items() if adet >= esik}


def _kutu_dogrula(kutu) -> list[float] | None:
    if not isinstance(kutu, (list, tuple)) or len(kutu) != 4:
        return None
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in kutu):
        return None
    x1, y1, x2, y2 = (float(x) for x in kutu)
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        return None
    return [x1, y1, x2, y2]


def _logo_adayi(kutu: list[float]) -> bool:
    x1, y1, x2, y2 = kutu
    alan = (x2 - x1) * (y2 - y1)
    xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
    return alan <= 0.05 and (xm <= 0.20 or xm >= 0.80) and (ym <= 0.20 or ym >= 0.80)


def _kutu_imzasi(kutu: list[float]) -> tuple[int, ...]:
    # %2 koordinat nicemleme: sabit logodaki 1-2 piksellik detector titremesi
    # ayni imzaya dussun, farkli metin kutulari birlesmesin.
    return tuple(round(x * 50) for x in kutu)


def _y_merkez(kutu: list[float]) -> float:
    return (kutu[1] + kutu[3]) / 2
